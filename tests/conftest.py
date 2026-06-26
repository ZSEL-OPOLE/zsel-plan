"""
Współdzielone fixtures pytest dla testów zsel-plan.
Zawiera: minimalne i bardziej złożone SolveRequest, przykładowe lekcje, instancje solvera.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from api.models import RequirementIn, SolveRequest, TeacherUnavailIn
from api.ical import build_ical
from solver.solver import Instance


# ---------------------------------------------------------------------------
# Fixtures: minimalne dane do SolveRequest
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_solve_request() -> SolveRequest:
    """
    Minimalny poprawny SolveRequest: 1 klasa, 1 przedmiot, 1 nauczyciel,
    1 godzina tygodniowo, 1 sala (dowolne przedmioty).
    """
    return SolveRequest(
        days=["pon", "wt", "sr", "czw", "pt"],
        periods=list(range(1, 6)),  # lekcje 1-5 (mniej = szybsze testy)
        rooms={"S01": []},          # [] = dowolne przedmioty
        requirements=[
            RequirementIn(klasa="1A", przedmiot="Matematyka", nauczyciel="Jan Kowalski", godziny=1)
        ],
        teacher_unavail=[],
        max_seconds=10,
    )


@pytest.fixture()
def two_class_solve_request() -> SolveRequest:
    """
    SolveRequest z 2 klasami, 2 nauczycielami, 2 salami — do testów kolizji.
    Każda klasa ma 2 godziny tygodniowo.
    """
    return SolveRequest(
        days=["pon", "wt", "sr"],
        periods=list(range(1, 8)),
        rooms={
            "S01": [],
            "S02": [],
        },
        requirements=[
            RequirementIn(klasa="1A", przedmiot="Polski", nauczyciel="Anna Nowak", godziny=2),
            RequirementIn(klasa="1B", przedmiot="Historia", nauczyciel="Piotr Wiśniewski", godziny=2),
        ],
        teacher_unavail=[],
        max_seconds=10,
    )


@pytest.fixture()
def full_week_solve_request() -> SolveRequest:
    """
    SolveRequest na pełny tydzień (5 dni, lekcje 1-9) dla testów wydajnościowych.
    3 klasy, 5 przedmiotów (po 2 godz./tydz.), 9 sal.
    """
    rooms = {f"S{i:02d}": [] for i in range(1, 10)}  # S01..S09
    requirements = []
    klasy = ["1A", "2B", "3C"]
    przedmioty = [
        ("Matematyka", "Jan Kowalski"),
        ("Polski", "Anna Nowak"),
        ("Fizyka", "Marek Zając"),
        ("Historia", "Ewa Pawlak"),
        ("Angielski", "Tomasz Wiśniewski"),
    ]
    for klasa in klasy:
        for prz, naucz in przedmioty:
            requirements.append(
                RequirementIn(klasa=klasa, przedmiot=prz, nauczyciel=naucz, godziny=2)
            )
    return SolveRequest(
        days=["pon", "wt", "sr", "czw", "pt"],
        periods=list(range(1, 10)),
        rooms=rooms,
        requirements=requirements,
        teacher_unavail=[],
        max_seconds=30,
    )


@pytest.fixture()
def minimal_instance() -> Instance:
    """Minimalna Instance dla bezpośrednich testów solvera (bez FastAPI)."""
    return Instance(
        days=["pon", "wt"],
        periods=[1, 2, 3, 4, 5],
        rooms={"S01": set()},
        requirements=[("1A", "Matematyka", "Jan Kowalski", 1)],
        teacher_unavail={},
    )


# ---------------------------------------------------------------------------
# Fixtures: przykładowe dane lekcji do testów iCal
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_lessons() -> list[dict]:
    """Lista 3 lekcji tygodniowych do testów build_ical."""
    return [
        {
            "klasa": "1A",
            "dzien": "pon",
            "dzien_idx": 0,
            "okres": 1,
            "przedmiot": "Matematyka",
            "nauczyciel": "Jan Kowalski",
            "sala": "S01",
        },
        {
            "klasa": "1A",
            "dzien": "wt",
            "dzien_idx": 1,
            "okres": 3,
            "przedmiot": "Polski",
            "nauczyciel": "Anna Nowak",
            "sala": "S02",
        },
        {
            "klasa": "2B",
            "dzien": "sr",
            "dzien_idx": 2,
            "okres": 2,
            "przedmiot": "Fizyka",
            "nauczyciel": "Marek Zając",
            "sala": "Lab01",
        },
    ]


@pytest.fixture()
def sample_lessons_polish_chars() -> list[dict]:
    """Lekcje z polskimi znakami w nazwach — test kodowania UTF-8."""
    return [
        {
            "klasa": "3Ą",
            "dzien": "czw",
            "dzien_idx": 3,
            "okres": 4,
            "przedmiot": "Język angielski",
            "nauczyciel": "Józef Żółwiński",
            "sala": "Aula główna",
        },
    ]
