"""
Testy integracyjne FastAPI dla zsel-plan (api/main.py).
Pokrywa: /health, /api/plan/solve, /api/plan/ical, filtry, CORS, /docs.
Używa FastAPI TestClient — bez zewnętrznych wywołań sieciowych.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Resetuj globalny stan aplikacji przed importem
import api.main as _main_module  # noqa: E402

_main_module._last_plan = None
_main_module._last_days = []

from api.main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Pomocnik: wywołaj solve i zwróć wynik
# ---------------------------------------------------------------------------


def _solve_minimal(
    days=None,
    periods=None,
    rooms=None,
    requirements=None,
    teacher_unavail=None,
    max_seconds=15,
):
    """Wywołaj POST /api/plan/solve z minimalnym payloadem."""
    payload = {
        "days": days or ["pon", "wt", "sr"],
        "periods": periods or [1, 2, 3, 4, 5],
        "rooms": rooms if rooms is not None else {"S01": []},
        "requirements": requirements
        or [
            {
                "klasa": "1A",
                "przedmiot": "Matematyka",
                "nauczyciel": "Jan Kowalski",
                "godziny": 1,
            }
        ],
        "teacher_unavail": teacher_unavail or [],
        "max_seconds": max_seconds,
    }
    return client.post("/api/plan/solve", json=payload)


# ===========================================================================
# Testy /health
# ===========================================================================


class TestHealthEndpoint:
    """Testy endpointu /health."""

    def test_health_status_200(self):
        """GET /health → 200."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_body_has_status_ok(self):
        """GET /health → {"status": "ok", ...}."""
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_has_plan_loaded_field(self):
        """GET /health → zawiera pole plan_loaded."""
        resp = client.get("/health")
        data = resp.json()
        assert "plan_loaded" in data
        assert isinstance(data["plan_loaded"], bool)


# ===========================================================================
# Testy /docs
# ===========================================================================


class TestDocs:
    """Testy dostępności dokumentacji OpenAPI."""

    def test_docs_returns_200(self):
        """GET /docs → 200 (Swagger UI dostępne)."""
        resp = client.get("/docs")
        assert resp.status_code == 200


# ===========================================================================
# Testy POST /api/plan/solve
# ===========================================================================


class TestSolveEndpoint:
    """Testy głównego endpointu solvera."""

    def test_solve_minimal_payload_200(self):
        """POST /api/plan/solve z minimalnym payloadem → 200."""
        resp = _solve_minimal()
        assert resp.status_code == 200

    def test_solve_response_has_status(self):
        """Odpowiedź solve zawiera pole 'status'."""
        resp = _solve_minimal()
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_solve_response_has_lekcje(self):
        """Odpowiedź solve zawiera pole 'lekcje'."""
        resp = _solve_minimal()
        assert resp.status_code == 200
        data = resp.json()
        assert "lekcje" in data

    def test_solve_response_has_gaps(self):
        """Odpowiedź solve zawiera pole 'gaps'."""
        resp = _solve_minimal()
        assert resp.status_code == 200
        data = resp.json()
        assert "gaps" in data
        assert isinstance(data["gaps"], int)

    def test_solve_lekcje_not_empty(self):
        """Lista lekcji nie jest pusta dla wykonalnego planu."""
        resp = _solve_minimal()
        assert resp.status_code == 200
        lekcje = resp.json()["lekcje"]
        assert len(lekcje) >= 1

    def test_solve_lesson_has_required_fields(self):
        """Każda lekcja zawiera: klasa, dzien, przedmiot, nauczyciel, sala, okres, dzien_idx."""
        resp = _solve_minimal()
        assert resp.status_code == 200
        for lekcja in resp.json()["lekcje"]:
            assert "klasa" in lekcja, f"Brak 'klasa' w lekcji: {lekcja}"
            assert "dzien" in lekcja, f"Brak 'dzien' w lekcji: {lekcja}"
            assert "przedmiot" in lekcja, f"Brak 'przedmiot' w lekcji: {lekcja}"
            assert "nauczyciel" in lekcja, f"Brak 'nauczyciel' w lekcji: {lekcja}"
            assert "sala" in lekcja, f"Brak 'sala' w lekcji: {lekcja}"
            assert "okres" in lekcja, f"Brak 'okres' w lekcji: {lekcja}"
            assert "dzien_idx" in lekcja, f"Brak 'dzien_idx' w lekcji: {lekcja}"

    def test_solve_lesson_klasa_matches_request(self):
        """Klasa w wynikach odpowiada klasie z requesta."""
        resp = _solve_minimal(
            requirements=[
                {
                    "klasa": "2C",
                    "przedmiot": "Fizyka",
                    "nauczyciel": "Marek Zając",
                    "godziny": 1,
                }
            ]
        )
        assert resp.status_code == 200
        for lekcja in resp.json()["lekcje"]:
            assert lekcja["klasa"] == "2C"

    def test_solve_status_optimal_or_feasible(self):
        """Dla wykonalnego problemu status to OPTIMAL lub FEASIBLE."""
        resp = _solve_minimal()
        assert resp.status_code == 200
        status = resp.json()["status"]
        assert status in ("OPTIMAL", "FEASIBLE"), f"Nieoczekiwany status: {status}"

    def test_solve_two_classes_correct_count(self):
        """Dla 2 klas × 1 godzina = 2 lekcje w planie."""
        resp = _solve_minimal(
            rooms={"S01": [], "S02": []},
            requirements=[
                {
                    "klasa": "1A",
                    "przedmiot": "Matematyka",
                    "nauczyciel": "Jan Kowalski",
                    "godziny": 1,
                },
                {
                    "klasa": "1B",
                    "przedmiot": "Polski",
                    "nauczyciel": "Anna Nowak",
                    "godziny": 1,
                },
            ],
        )
        assert resp.status_code == 200
        lekcje = resp.json()["lekcje"]
        assert len(lekcje) == 2

    def test_solve_impossible_constraints_422(self):
        """Niemożliwy plan (0 dostępnych slotów dla nauczyciela) → 422."""
        # Jedyny dzień = pon, sloty = [1], nauczyciel niedostępny w pon/1
        resp = _solve_minimal(
            days=["pon"],
            periods=[1],
            rooms={"S01": []},
            requirements=[
                {
                    "klasa": "1A",
                    "przedmiot": "Matematyka",
                    "nauczyciel": "Jan Kowalski",
                    "godziny": 1,
                }
            ],
            teacher_unavail=[{"nauczyciel": "Jan Kowalski", "sloty": [["pon", 1]]}],
        )
        assert resp.status_code == 422

    def test_solve_422_has_detail_message(self):
        """Odpowiedź 422 zawiera opis problemu w 'detail'."""
        resp = _solve_minimal(
            days=["pon"],
            periods=[1],
            rooms={"S01": []},
            requirements=[
                {
                    "klasa": "1A",
                    "przedmiot": "Matematyka",
                    "nauczyciel": "Jan Kowalski",
                    "godziny": 1,
                }
            ],
            teacher_unavail=[{"nauczyciel": "Jan Kowalski", "sloty": [["pon", 1]]}],
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data

    def test_solve_missing_rooms_field_422(self):
        """Brak wymaganego pola 'rooms' → 422 (walidacja Pydantic)."""
        resp = client.post(
            "/api/plan/solve",
            json={
                "requirements": [
                    {"klasa": "1A", "przedmiot": "Mat", "nauczyciel": "X", "godziny": 1}
                ]
            },
        )
        assert resp.status_code == 422

    def test_solve_missing_requirements_field_422(self):
        """Brak wymaganego pola 'requirements' → 422."""
        resp = client.post("/api/plan/solve", json={"rooms": {"S01": []}})
        assert resp.status_code == 422

    def test_solve_with_teacher_unavail(self):
        """Plan z teacher_unavail zwraca wynik bez naruszenia ograniczeń."""
        resp = _solve_minimal(
            days=["pon", "wt", "sr"],
            periods=[1, 2, 3, 4, 5],
            rooms={"S01": []},
            requirements=[
                {
                    "klasa": "1A",
                    "przedmiot": "Matematyka",
                    "nauczyciel": "Jan Kowalski",
                    "godziny": 1,
                }
            ],
            teacher_unavail=[{"nauczyciel": "Jan Kowalski", "sloty": [["pon", 1]]}],
        )
        assert resp.status_code == 200
        lekcje = resp.json()["lekcje"]
        for lekcja in lekcje:
            if lekcja["nauczyciel"] == "Jan Kowalski":
                assert not (lekcja["dzien"] == "pon" and lekcja["okres"] == 1), (
                    "Nauczyciel ma lekcję w niedostępnym slocie!"
                )


# ===========================================================================
# Testy GET /api/plan/ical/*
# ===========================================================================


class TestIcalEndpoints:
    """Testy endpointów eksportu iCal."""

    def _ensure_plan(self):
        """Upewnij się że plan jest załadowany w pamięci aplikacji."""
        resp = _solve_minimal(
            days=["pon", "wt"],
            periods=[1, 2, 3, 4, 5],
            rooms={"S01": [], "S02": []},
            requirements=[
                {
                    "klasa": "1A",
                    "przedmiot": "Matematyka",
                    "nauczyciel": "Jan Kowalski",
                    "godziny": 2,
                },
                {
                    "klasa": "2B",
                    "przedmiot": "Polski",
                    "nauczyciel": "Anna Nowak",
                    "godziny": 2,
                },
            ],
        )
        assert resp.status_code == 200, f"Solve nie powiodło się: {resp.json()}"
        return resp.json()["lekcje"]

    def test_ical_all_returns_200_after_solve(self):
        """GET /api/plan/ical/all → 200 po załadowaniu planu."""
        self._ensure_plan()
        resp = client.get("/api/plan/ical/all")
        assert resp.status_code == 200

    def test_ical_all_content_type_calendar(self):
        """GET /api/plan/ical/all → Content-Type: text/calendar."""
        self._ensure_plan()
        resp = client.get("/api/plan/ical/all")
        assert "text/calendar" in resp.headers["content-type"]

    def test_ical_all_starts_with_begin_vcalendar(self):
        """Odpowiedź iCal zaczyna się od BEGIN:VCALENDAR."""
        self._ensure_plan()
        resp = client.get("/api/plan/ical/all")
        assert resp.text.startswith("BEGIN:VCALENDAR")

    def test_ical_all_ends_with_end_vcalendar(self):
        """Odpowiedź iCal kończy się na END:VCALENDAR."""
        self._ensure_plan()
        resp = client.get("/api/plan/ical/all")
        assert resp.text.strip().endswith("END:VCALENDAR")

    def test_ical_no_plan_404(self):
        """GET /api/plan/ical/all bez załadowanego planu → 404."""
        # Zresetuj globalny stan
        import api.main as m

        original = m._last_plan
        m._last_plan = None
        try:
            resp = client.get("/api/plan/ical/all")
            assert resp.status_code == 404
        finally:
            m._last_plan = original

    def test_ical_klasa_filter_returns_200(self):
        """GET /api/plan/ical/klasa/1A → 200."""
        self._ensure_plan()
        resp = client.get("/api/plan/ical/klasa/1A")
        assert resp.status_code == 200

    def test_ical_klasa_filter_content_type(self):
        """GET /api/plan/ical/klasa/1A → text/calendar."""
        self._ensure_plan()
        resp = client.get("/api/plan/ical/klasa/1A")
        assert "text/calendar" in resp.headers["content-type"]

    def test_ical_klasa_filter_vcalendar_structure(self):
        """GET /api/plan/ical/klasa/1A → poprawna struktura iCal."""
        self._ensure_plan()
        resp = client.get("/api/plan/ical/klasa/1A")
        assert "BEGIN:VCALENDAR" in resp.text
        assert "END:VCALENDAR" in resp.text

    def test_ical_nauczyciel_filter_returns_200(self):
        """GET /api/plan/ical/nauczyciel/Jan Kowalski → 200."""
        self._ensure_plan()
        resp = client.get("/api/plan/ical/nauczyciel/Jan Kowalski")
        assert resp.status_code == 200

    def test_ical_no_plan_klasa_404(self):
        """GET /api/plan/ical/klasa/1A bez planu → 404."""
        import api.main as m

        original = m._last_plan
        m._last_plan = None
        try:
            resp = client.get("/api/plan/ical/klasa/1A")
            assert resp.status_code == 404
        finally:
            m._last_plan = original

    def test_ical_no_plan_nauczyciel_404(self):
        """GET /api/plan/ical/nauczyciel/X bez planu → 404."""
        import api.main as m

        original = m._last_plan
        m._last_plan = None
        try:
            resp = client.get("/api/plan/ical/nauczyciel/X")
            assert resp.status_code == 404
        finally:
            m._last_plan = original

    def test_ical_with_rok_start_param(self):
        """GET /api/plan/ical/all?rok_start=2026-09-01 → 200."""
        self._ensure_plan()
        resp = client.get("/api/plan/ical/all?rok_start=2026-09-01")
        assert resp.status_code == 200
        assert "BEGIN:VCALENDAR" in resp.text

    def test_ical_klasa_with_rok_start_param(self):
        """GET /api/plan/ical/klasa/1A?rok_start=2026-09-01 → 200."""
        self._ensure_plan()
        resp = client.get("/api/plan/ical/klasa/1A?rok_start=2026-09-01")
        assert resp.status_code == 200


# ===========================================================================
# Testy filtrowania (/api/plan/klasy, /api/plan/nauczyciele, itp.)
# ===========================================================================


class TestFilterEndpoints:
    """Testy endpointów filtrujących plan."""

    def _load_plan(self):
        return _solve_minimal(
            days=["pon", "wt"],
            periods=[1, 2, 3, 4, 5],
            rooms={"S01": [], "S02": []},
            requirements=[
                {
                    "klasa": "1A",
                    "przedmiot": "Matematyka",
                    "nauczyciel": "Jan Kowalski",
                    "godziny": 2,
                },
                {
                    "klasa": "2B",
                    "przedmiot": "Polski",
                    "nauczyciel": "Anna Nowak",
                    "godziny": 1,
                },
            ],
        )

    def test_list_klasy_200(self):
        """GET /api/plan/klasy → 200 po załadowaniu planu."""
        self._load_plan()
        resp = client.get("/api/plan/klasy")
        assert resp.status_code == 200

    def test_list_klasy_contains_correct_classes(self):
        """GET /api/plan/klasy zawiera klasy z requesta."""
        self._load_plan()
        resp = client.get("/api/plan/klasy")
        klasy = resp.json()
        assert "1A" in klasy
        assert "2B" in klasy

    def test_list_nauczyciele_200(self):
        """GET /api/plan/nauczyciele → 200."""
        self._load_plan()
        resp = client.get("/api/plan/nauczyciele")
        assert resp.status_code == 200

    def test_list_nauczyciele_contains_correct_teachers(self):
        """GET /api/plan/nauczyciele zawiera nauczycieli z requesta."""
        self._load_plan()
        resp = client.get("/api/plan/nauczyciele")
        naucz = resp.json()
        assert "Jan Kowalski" in naucz
        assert "Anna Nowak" in naucz

    def test_get_plan_klasa_returns_only_that_class(self):
        """GET /api/plan/klasa/1A zwraca tylko lekcje dla klasy 1A."""
        self._load_plan()
        resp = client.get("/api/plan/klasa/1A")
        assert resp.status_code == 200
        for lekcja in resp.json():
            assert lekcja["klasa"] == "1A", (
                f"Lekcja klasy {lekcja['klasa']} w wynikach dla 1A"
            )

    def test_get_plan_nauczyciel_returns_only_that_teacher(self):
        """GET /api/plan/nauczyciel/Jan Kowalski zwraca tylko jego lekcje."""
        self._load_plan()
        resp = client.get("/api/plan/nauczyciel/Jan Kowalski")
        assert resp.status_code == 200
        for lekcja in resp.json():
            assert lekcja["nauczyciel"] == "Jan Kowalski"

    def test_get_plan_nonexistent_klasa_404(self):
        """GET /api/plan/klasa/ZZZ → 404 gdy klasa nie istnieje."""
        self._load_plan()
        resp = client.get("/api/plan/klasa/ZZZ_nieistniejaca")
        assert resp.status_code == 404

    def test_get_plan_nonexistent_nauczyciel_404(self):
        """GET /api/plan/nauczyciel/X → 404 gdy nauczyciel nie istnieje."""
        self._load_plan()
        resp = client.get("/api/plan/nauczyciel/Nieistniejacy_Nauczyciel")
        assert resp.status_code == 404

    def test_klasy_no_plan_404(self):
        """GET /api/plan/klasy bez planu → 404."""
        import api.main as m

        original = m._last_plan
        m._last_plan = None
        try:
            resp = client.get("/api/plan/klasy")
            assert resp.status_code == 404
        finally:
            m._last_plan = original


# ===========================================================================
# Testy CORS
# ===========================================================================


class TestCORS:
    """Testy nagłówków CORS."""

    def test_cors_options_health(self):
        """OPTIONS /health zwraca nagłówki CORS Allow-Origin."""
        resp = client.options(
            "/health", headers={"Origin": "https://portal.zsel.opole.pl"}
        )
        # FastAPI z CORSMiddleware powinno odpowiedzieć 200 lub 204
        assert resp.status_code in (200, 204)

    def test_cors_get_allows_all_origins(self):
        """GET /health z nagłówkiem Origin zwraca Access-Control-Allow-Origin."""
        resp = client.get("/health", headers={"Origin": "https://app.example.com"})
        assert resp.status_code == 200
        # TestClient z CORSMiddleware powinien dodać nagłówek
        cors_header = resp.headers.get("access-control-allow-origin")
        assert cors_header is not None, "Brak nagłówka Access-Control-Allow-Origin"
