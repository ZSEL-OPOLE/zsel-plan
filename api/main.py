"""Plan lekcji ZSEL — FastAPI (OR-Tools CP-SAT solver + iCal export)."""

from __future__ import annotations
import sys
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

# Upewnij się, że solver jest w PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))
from solver.solver import Instance, solve as _solve
from api.models import LessonOut, SolveRequest, SolveResponse
from api.ical import build_ical

app = FastAPI(
    title="ZSEL Plan Lekcji API",
    description="OR-Tools CP-SAT solver dla tygodniowego planu lekcji + iCal export do Nextcloud Calendar",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# In-memory cache ostatniego wygenerowanego planu (produkacja: persistent store)
_last_plan: list[LessonOut] | None = None
_last_days: list[str] = []


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "plan_loaded": _last_plan is not None}


@app.post("/api/plan/solve", response_model=SolveResponse)
def solve_plan(req: SolveRequest) -> SolveResponse:
    """Wygeneruj plan lekcji z podanych wymagań."""
    global _last_plan, _last_days

    rooms_sets = {sala: set(prz) for sala, prz in req.rooms.items()}
    requirements = [
        (r.klasa, r.przedmiot, r.nauczyciel, r.godziny) for r in req.requirements
    ]
    unavail: dict[str, set[tuple[str, int]]] = {}
    for u in req.teacher_unavail:
        unavail[u.nauczyciel] = {(d, p) for d, p in u.sloty}

    inst = Instance(
        days=req.days,
        periods=req.periods,
        rooms=rooms_sets,
        requirements=requirements,
        teacher_unavail=unavail,
    )

    result = _solve(inst, max_seconds=req.max_seconds)

    if result.status not in ("OPTIMAL", "FEASIBLE"):
        raise HTTPException(
            status_code=422,
            detail=f"Solver zwrócił status: {result.status}. "
            "Sprawdź czy wymagania są wykonalne (liczba godzin, sale, dostępność).",
        )

    lekcje: list[LessonOut] = []
    for (klasa, day_idx, okres), (
        przedmiot,
        nauczyciel,
        sala,
    ) in result.timetable.items():
        lekcje.append(
            LessonOut(
                klasa=klasa,
                dzien=req.days[day_idx],
                dzien_idx=day_idx,
                okres=okres,
                przedmiot=przedmiot,
                nauczyciel=nauczyciel,
                sala=sala,
            )
        )

    _last_plan = lekcje
    _last_days = req.days

    return SolveResponse(status=result.status, gaps=result.gaps, lekcje=lekcje)


@app.get("/api/plan/klasy")
def list_klasy() -> list[str]:
    """Zwróć listę klas z załadowanego planu."""
    if not _last_plan:
        raise HTTPException(
            status_code=404,
            detail="Brak załadowanego planu. Najpierw POST /api/plan/solve",
        )
    return sorted({lesson.klasa for lesson in _last_plan})


@app.get("/api/plan/nauczyciele")
def list_nauczyciele() -> list[str]:
    """Zwróć listę nauczycieli z załadowanego planu."""
    if not _last_plan:
        raise HTTPException(
            status_code=404,
            detail="Brak załadowanego planu. Najpierw POST /api/plan/solve",
        )
    return sorted({lesson.nauczyciel for lesson in _last_plan})


@app.get("/api/plan/klasa/{klasa}")
def get_plan_klasa(klasa: str) -> list[LessonOut]:
    """Pobierz plan tygodniowy dla klasy."""
    if not _last_plan:
        raise HTTPException(status_code=404, detail="Brak załadowanego planu.")
    result = [lesson for lesson in _last_plan if lesson.klasa == klasa]
    if not result:
        raise HTTPException(
            status_code=404, detail=f"Klasa '{klasa}' nie istnieje w planie."
        )
    return sorted(result, key=lambda lesson: (lesson.dzien_idx, lesson.okres))


@app.get("/api/plan/nauczyciel/{nauczyciel}")
def get_plan_nauczyciel(nauczyciel: str) -> list[LessonOut]:
    """Pobierz plan tygodniowy dla nauczyciela."""
    if not _last_plan:
        raise HTTPException(status_code=404, detail="Brak załadowanego planu.")
    result = [lesson for lesson in _last_plan if lesson.nauczyciel == nauczyciel]
    if not result:
        raise HTTPException(
            status_code=404, detail=f"Nauczyciel '{nauczyciel}' nie istnieje w planie."
        )
    return sorted(result, key=lambda lesson: (lesson.dzien_idx, lesson.okres))


@app.get("/api/plan/ical/klasa/{klasa}")
def ical_klasa(
    klasa: str,
    rok_start: Annotated[
        str | None,
        Query(description="Pierwszy poniedziałek roku szkolnego, format YYYY-MM-DD"),
    ] = None,
) -> Response:
    """
    Pobierz plan klasy jako iCal (do importu w Nextcloud Calendar, Google Calendar itp.).
    URL możesz subskrybować w Nextcloud Calendar jako 'zewnętrzny kalendarz'.
    """
    if not _last_plan:
        raise HTTPException(status_code=404, detail="Brak załadowanego planu.")

    lekcje_raw = [lesson.model_dump() for lesson in _last_plan]
    start_date = date.fromisoformat(rok_start) if rok_start else None
    cal = build_ical(
        lekcje_raw, filter_by=klasa, filter_field="klasa", school_year_start=start_date
    )

    return Response(
        content=cal,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="plan-{klasa}.ics"'},
    )


@app.get("/api/plan/ical/nauczyciel/{nauczyciel}")
def ical_nauczyciel(
    nauczyciel: str,
    rok_start: Annotated[
        str | None,
        Query(description="Pierwszy poniedziałek roku szkolnego, format YYYY-MM-DD"),
    ] = None,
) -> Response:
    """Pobierz plan nauczyciela jako iCal."""
    if not _last_plan:
        raise HTTPException(status_code=404, detail="Brak załadowanego planu.")

    lekcje_raw = [lesson.model_dump() for lesson in _last_plan]
    start_date = date.fromisoformat(rok_start) if rok_start else None
    cal = build_ical(
        lekcje_raw,
        filter_by=nauczyciel,
        filter_field="nauczyciel",
        school_year_start=start_date,
    )

    return Response(
        content=cal,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="plan-{nauczyciel}.ics"'
        },
    )


@app.get("/api/plan/ical/all")
def ical_all(
    rok_start: Annotated[str | None, Query()] = None,
) -> Response:
    """Pobierz pełny plan szkoły jako iCal."""
    if not _last_plan:
        raise HTTPException(status_code=404, detail="Brak załadowanego planu.")

    lekcje_raw = [lesson.model_dump() for lesson in _last_plan]
    start_date = date.fromisoformat(rok_start) if rok_start else None
    cal = build_ical(lekcje_raw, school_year_start=start_date)

    return Response(
        content=cal,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="plan-szkola.ics"'},
    )

