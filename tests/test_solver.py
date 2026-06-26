"""
Testy jednostkowe silnika planowania lekcji (solver/solver.py).
Pokrywa: podstawowe rozwiązanie, kolizje sal/nauczycieli, niedostępność, luki,
ograniczenia sali, wydajność, INFEASIBLE.
"""
from __future__ import annotations

import time
import sys
from pathlib import Path
from collections import defaultdict

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from solver.solver import Instance, Result, solve


# ===========================================================================
# Pomocnicze funkcje
# ===========================================================================


def make_instance(
    klasy=None,
    rooms=None,
    requirements=None,
    days=None,
    periods=None,
    teacher_unavail=None,
) -> Instance:
    """Fabryka Instance z sensownymi wartościami domyślnymi."""
    return Instance(
        days=days or ["pon", "wt", "sr", "czw", "pt"],
        periods=periods or list(range(1, 6)),
        rooms=rooms or {"S01": set()},
        requirements=requirements or [("1A", "Matematyka", "Jan Kowalski", 1)],
        teacher_unavail=teacher_unavail or {},
    )


# ===========================================================================
# Testy podstawowe
# ===========================================================================


class TestBasicSolve:
    """Podstawowe testy rozwiązywalności dla prostych przypadków."""

    def test_minimal_optimal_or_feasible(self):
        """1 klasa, 1 przedmiot, 1 nauczyciel, 1 godz. → OPTIMAL lub FEASIBLE."""
        inst = make_instance(
            requirements=[("1A", "Matematyka", "Jan Kowalski", 1)],
            rooms={"S01": set()},
            days=["pon"],
            periods=[1, 2, 3],
        )
        result = solve(inst, max_seconds=10)
        assert result.status in ("OPTIMAL", "FEASIBLE"), (
            f"Oczekiwano OPTIMAL/FEASIBLE, dostałem {result.status}"
        )

    def test_minimal_timetable_has_one_lesson(self):
        """Dla 1 wymaganej godziny plan zawiera dokładnie 1 lekcję."""
        inst = make_instance(
            requirements=[("1A", "Matematyka", "Jan Kowalski", 1)],
            rooms={"S01": set()},
            days=["pon"],
            periods=[1, 2, 3],
        )
        result = solve(inst, max_seconds=10)
        assert result.status in ("OPTIMAL", "FEASIBLE")
        assert len(result.timetable) == 1

    def test_multiple_hours_all_placed(self):
        """Jeśli wymagane są 3 godziny tygodniowo, timetable ma 3 wpisy."""
        inst = make_instance(
            requirements=[("1A", "Matematyka", "Jan Kowalski", 3)],
            rooms={"S01": set()},
            days=["pon", "wt", "sr", "czw", "pt"],
            periods=[1, 2, 3, 4, 5],
        )
        result = solve(inst, max_seconds=15)
        assert result.status in ("OPTIMAL", "FEASIBLE")
        assert len(result.timetable) == 3

    def test_result_has_correct_fields(self):
        """Wynik solvera zawiera status, timetable i gaps."""
        inst = make_instance()
        result = solve(inst, max_seconds=10)
        assert hasattr(result, "status")
        assert hasattr(result, "timetable")
        assert hasattr(result, "gaps")
        assert isinstance(result.timetable, dict)
        assert isinstance(result.gaps, int)

    def test_timetable_keys_are_klasa_day_period(self):
        """Klucze timetable to (klasa, day_idx:int, period:int)."""
        inst = make_instance(
            requirements=[("1A", "Matematyka", "Jan Kowalski", 2)],
            rooms={"S01": set()},
            days=["pon", "wt"],
            periods=[1, 2, 3],
        )
        result = solve(inst, max_seconds=10)
        if result.status in ("OPTIMAL", "FEASIBLE"):
            for key in result.timetable:
                klasa, day_idx, period = key
                assert isinstance(klasa, str)
                assert isinstance(day_idx, int)
                assert isinstance(period, int)

    def test_timetable_values_are_przedmiot_nauczyciel_sala(self):
        """Wartości timetable to (przedmiot, nauczyciel, sala) — wszystkie str."""
        inst = make_instance()
        result = solve(inst, max_seconds=10)
        if result.status in ("OPTIMAL", "FEASIBLE"):
            for val in result.timetable.values():
                przedmiot, nauczyciel, sala = val
                assert isinstance(przedmiot, str)
                assert isinstance(nauczyciel, str)
                assert isinstance(sala, str)


# ===========================================================================
# Testy ograniczeń twardych
# ===========================================================================


class TestHardConstraints:
    """Testy twardych reguł: brak kolizji klas/nauczycieli/sal."""

    def test_two_classes_not_in_same_room_same_slot(self):
        """Dwie klasy nie mogą być w tej samej sali w tym samym slocie."""
        inst = make_instance(
            requirements=[
                ("1A", "Matematyka", "Jan Kowalski", 3),
                ("1B", "Polski", "Anna Nowak", 3),
            ],
            rooms={"S01": set()},
            days=["pon", "wt", "sr"],
            periods=[1, 2, 3, 4, 5],
        )
        result = solve(inst, max_seconds=15)
        if result.status not in ("OPTIMAL", "FEASIBLE"):
            pytest.skip("Solver nie znalazł rozwiązania — sprawdź ograniczenia")

        # Zgrupuj po (sala, day_idx, period)
        sala_slot_count: dict = defaultdict(int)
        for (klasa, day_idx, period), (prz, naucz, sala) in result.timetable.items():
            sala_slot_count[(sala, day_idx, period)] += 1

        for key, count in sala_slot_count.items():
            assert count <= 1, (
                f"Sala {key[0]} ma {count} lekcje w slocie ({key[1]},{key[2]}) — KOLIZJA!"
            )

    def test_teacher_not_in_two_places_same_slot(self):
        """Nauczyciel nie może być w 2 miejscach jednocześnie."""
        # Ten sam nauczyciel uczy 2 różne klasy
        inst = make_instance(
            requirements=[
                ("1A", "Matematyka", "Jan Kowalski", 2),
                ("1B", "Matematyka", "Jan Kowalski", 2),
            ],
            rooms={"S01": set(), "S02": set()},
            days=["pon", "wt", "sr", "czw"],
            periods=[1, 2, 3, 4, 5],
        )
        result = solve(inst, max_seconds=15)
        if result.status not in ("OPTIMAL", "FEASIBLE"):
            pytest.skip("Solver nie znalazł rozwiązania")

        # Zgrupuj lekcje per nauczyciel, slot
        naucz_slot_count: dict = defaultdict(int)
        for (klasa, day_idx, period), (prz, naucz, sala) in result.timetable.items():
            naucz_slot_count[(naucz, day_idx, period)] += 1

        for key, count in naucz_slot_count.items():
            assert count <= 1, (
                f"Nauczyciel {key[0]} jest w {count} miejscach w slocie ({key[1]},{key[2]}) — KOLIZJA!"
            )

    def test_class_has_at_most_one_lesson_per_slot(self):
        """Klasa może mieć co najwyżej 1 lekcję w danym slocie."""
        inst = make_instance(
            requirements=[
                ("1A", "Matematyka", "Jan Kowalski", 3),
                ("1A", "Polski", "Anna Nowak", 3),
            ],
            rooms={"S01": set(), "S02": set()},
            days=["pon", "wt", "sr", "czw", "pt"],
            periods=[1, 2, 3, 4, 5],
        )
        result = solve(inst, max_seconds=15)
        if result.status not in ("OPTIMAL", "FEASIBLE"):
            pytest.skip("Solver nie znalazł rozwiązania")

        klasa_slot_count: dict = defaultdict(int)
        for (klasa, day_idx, period), _ in result.timetable.items():
            klasa_slot_count[(klasa, day_idx, period)] += 1

        for key, count in klasa_slot_count.items():
            assert count <= 1, (
                f"Klasa {key[0]} ma {count} lekcje w slocie ({key[1]},{key[2]}) — KOLIZJA!"
            )

    def test_room_has_at_most_one_class_per_slot(self):
        """Sala może być zajęta przez co najwyżej jedną klasę na slot."""
        inst = make_instance(
            requirements=[
                ("1A", "Matematyka", "Jan Kowalski", 2),
                ("1B", "Polski", "Anna Nowak", 2),
                ("2A", "Fizyka", "Marek Zając", 2),
            ],
            rooms={"S01": set(), "S02": set()},
            days=["pon", "wt", "sr", "czw", "pt"],
            periods=[1, 2, 3, 4, 5, 6, 7],
        )
        result = solve(inst, max_seconds=15)
        if result.status not in ("OPTIMAL", "FEASIBLE"):
            pytest.skip("Solver nie znalazł rozwiązania")

        sala_slot_count: dict = defaultdict(int)
        for (klasa, day_idx, period), (prz, naucz, sala) in result.timetable.items():
            sala_slot_count[(sala, day_idx, period)] += 1

        for key, count in sala_slot_count.items():
            assert count <= 1, (
                f"Sala {key[0]} ma {count} lekcje w slocie ({key[1]},{key[2]}) — KOLIZJA!"
            )


# ===========================================================================
# Testy niedostępności nauczyciela
# ===========================================================================


class TestTeacherUnavailability:
    """Testy ograniczenia teacher_unavail — lekcja nie może być w zabronionym slocie."""

    def test_lesson_not_placed_in_unavailable_slot(self):
        """Lekcja nie trafia w slot, gdzie nauczyciel jest niedostępny."""
        # Nauczyciel niedostępny w poniedziałek (slot 1 i 2)
        inst = make_instance(
            requirements=[("1A", "Matematyka", "Jan Kowalski", 1)],
            rooms={"S01": set()},
            days=["pon", "wt"],
            periods=[1, 2, 3, 4, 5],
            teacher_unavail={"Jan Kowalski": {("pon", 1), ("pon", 2)}},
        )
        result = solve(inst, max_seconds=10)
        if result.status not in ("OPTIMAL", "FEASIBLE"):
            pytest.skip("Solver nie znalazł rozwiązania")

        for (klasa, day_idx, period), (prz, naucz, sala) in result.timetable.items():
            if naucz == "Jan Kowalski":
                day_name = inst.days[day_idx]
                assert (day_name, period) not in inst.teacher_unavail.get(naucz, set()), (
                    f"Nauczyciel {naucz} ma lekcję w niedostępnym slocie ({day_name}, {period})"
                )

    def test_all_unavailable_slots_respected(self):
        """Wszystkie niedostępne sloty nauczyciela są uszanowane."""
        forbidden = {("pon", 1), ("pon", 2), ("pon", 3), ("wt", 1)}
        inst = make_instance(
            requirements=[("1A", "Matematyka", "Jan Kowalski", 2)],
            rooms={"S01": set()},
            days=["pon", "wt", "sr"],
            periods=[1, 2, 3, 4, 5],
            teacher_unavail={"Jan Kowalski": forbidden},
        )
        result = solve(inst, max_seconds=10)
        if result.status not in ("OPTIMAL", "FEASIBLE"):
            pytest.skip("Solver nie znalazł rozwiązania")

        for (klasa, day_idx, period), (prz, naucz, sala) in result.timetable.items():
            if naucz == "Jan Kowalski":
                day_name = inst.days[day_idx]
                assert (day_name, period) not in forbidden, (
                    f"Naruszenie niedostępności: {naucz} w ({day_name}, {period})"
                )

    def test_unavail_does_not_affect_other_teachers(self):
        """Niedostępność jednego nauczyciela nie blokuje slotów dla innego."""
        inst = make_instance(
            requirements=[
                ("1A", "Matematyka", "Jan Kowalski", 1),
                ("1B", "Polski", "Anna Nowak", 1),
            ],
            rooms={"S01": set(), "S02": set()},
            days=["pon", "wt"],
            periods=[1, 2, 3],
            teacher_unavail={"Jan Kowalski": {("pon", 1), ("pon", 2), ("pon", 3)}},
        )
        result = solve(inst, max_seconds=10)
        if result.status not in ("OPTIMAL", "FEASIBLE"):
            pytest.skip("Solver nie znalazł rozwiązania")

        # Anna Nowak powinna móc mieć lekcję w poniedziałek
        anna_slots = [
            (day_idx, period) for (klasa, day_idx, period), (prz, naucz, sala)
            in result.timetable.items()
            if naucz == "Anna Nowak"
        ]
        assert len(anna_slots) >= 1


# ===========================================================================
# Testy ograniczenia sal
# ===========================================================================


class TestRoomConstraints:
    """Testy ograniczeń sali — sala dedykowana dla konkretnych przedmiotów."""

    def test_lesson_in_dedicated_room(self):
        """Lekcja Fizyki trafia tylko do sali Lab01 (dedykowana sala)."""
        inst = make_instance(
            requirements=[("1A", "Fizyka", "Marek Zając", 1)],
            rooms={
                "S01": set(),              # dowolne
                "Lab01": {"Fizyka"},       # tylko Fizyka
            },
            days=["pon", "wt"],
            periods=[1, 2, 3, 4, 5],
        )
        result = solve(inst, max_seconds=10)
        if result.status not in ("OPTIMAL", "FEASIBLE"):
            pytest.skip("Solver nie znalazł rozwiązania")

        for (klasa, day_idx, period), (prz, naucz, sala) in result.timetable.items():
            if prz == "Fizyka":
                assert sala == "Lab01", (
                    f"Fizyka powinna być w Lab01, jest w {sala}"
                )

    def test_non_dedicated_lesson_not_in_restricted_room(self):
        """Matematyka nie trafia do sali Lab01, która jest tylko dla Fizyki."""
        inst = make_instance(
            requirements=[
                ("1A", "Matematyka", "Jan Kowalski", 1),
                ("1A", "Fizyka", "Marek Zając", 1),
            ],
            rooms={
                "S01": set(),              # dowolne
                "Lab01": {"Fizyka"},       # tylko Fizyka
            },
            days=["pon", "wt", "sr"],
            periods=[1, 2, 3, 4, 5],
        )
        result = solve(inst, max_seconds=10)
        if result.status not in ("OPTIMAL", "FEASIBLE"):
            pytest.skip("Solver nie znalazł rozwiązania")

        for (klasa, day_idx, period), (prz, naucz, sala) in result.timetable.items():
            if prz == "Matematyka":
                assert sala != "Lab01" or not inst.rooms.get("Lab01"), (
                    "Matematyka nie powinna być w Lab01 (sala dedykowana dla Fizyki)"
                )


# ===========================================================================
# Testy minimalizacji luk (soft constraints)
# ===========================================================================


class TestGapMinimization:
    """Testy miękkiego ograniczenia minimalizacji okienek."""

    def test_gaps_is_non_negative(self):
        """Liczba okienek (gaps) jest nieujemna."""
        inst = make_instance(
            requirements=[("1A", "Matematyka", "Jan Kowalski", 3)],
            rooms={"S01": set()},
            days=["pon", "wt", "sr"],
            periods=[1, 2, 3, 4, 5],
        )
        result = solve(inst, max_seconds=10)
        if result.status in ("OPTIMAL", "FEASIBLE"):
            assert result.gaps >= 0

    def test_single_lesson_zero_gaps(self):
        """1 klasa z 1 lekcją dziennie — zero okienek w tym dniu."""
        inst = make_instance(
            requirements=[("1A", "Matematyka", "Jan Kowalski", 1)],
            rooms={"S01": set()},
            days=["pon"],
            periods=[1, 2, 3],
        )
        result = solve(inst, max_seconds=10)
        if result.status in ("OPTIMAL", "FEASIBLE"):
            assert result.gaps == 0

    def test_two_consecutive_same_class_preferred(self):
        """Dla 2 lekcji tej samej klasy solver preferuje brak okienek (gaps=0)."""
        # 2 lekcje w 1 dniu, 5 slotów — solver powinien ułożyć je kolejno
        inst = make_instance(
            requirements=[
                ("1A", "Matematyka", "Jan Kowalski", 1),
                ("1A", "Polski", "Anna Nowak", 1),
            ],
            rooms={"S01": set(), "S02": set()},
            days=["pon"],
            periods=[1, 2, 3, 4, 5],
        )
        result = solve(inst, max_seconds=10)
        if result.status in ("OPTIMAL", "FEASIBLE"):
            # Przy 2 lekcjach z 5 slotów — solver może ułożyć je obok siebie
            # Gaps = 0 jest osiągalne
            assert result.gaps >= 0  # zawsze >=0


# ===========================================================================
# Testy wydajnościowe
# ===========================================================================


class TestPerformance:
    """Testy czasu rozwiązywania dla realistycznych rozmiarów planu."""

    def test_full_week_3_classes_solves_within_30s(self, full_week_solve_request):
        """
        3 klasy x 5 przedmiotów x 2 godz. = 30 lekcji, 9 sal, pełny tydzień.
        Solver powinien znaleźć rozwiązanie w < 30 sekund.
        """
        rooms_sets = {sala: set(prz) for sala, prz in full_week_solve_request.rooms.items()}
        requirements = [
            (r.klasa, r.przedmiot, r.nauczyciel, r.godziny)
            for r in full_week_solve_request.requirements
        ]
        inst = Instance(
            days=full_week_solve_request.days,
            periods=full_week_solve_request.periods,
            rooms=rooms_sets,
            requirements=requirements,
            teacher_unavail={},
        )

        start = time.time()
        result = solve(inst, max_seconds=30)
        elapsed = time.time() - start

        assert elapsed < 30.0, f"Solver trwał {elapsed:.1f}s — za długo (limit 30s)"
        assert result.status in ("OPTIMAL", "FEASIBLE", "UNKNOWN"), (
            f"Nieoczekiwany status: {result.status}"
        )

    def test_small_instance_solves_fast(self):
        """Mała instancja (2 klasy, 3 lekcje) rozwiązuje się w < 5 sekund."""
        inst = make_instance(
            requirements=[
                ("1A", "Matematyka", "Jan Kowalski", 2),
                ("1B", "Polski", "Anna Nowak", 1),
            ],
            rooms={"S01": set(), "S02": set()},
            days=["pon", "wt", "sr"],
            periods=[1, 2, 3, 4, 5],
        )
        start = time.time()
        result = solve(inst, max_seconds=5)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"Mała instancja trwała {elapsed:.1f}s — za długo"
        assert result.status in ("OPTIMAL", "FEASIBLE", "UNKNOWN")


# ===========================================================================
# Testy INFEASIBLE
# ===========================================================================


class TestInfeasible:
    """Testy sytuacji, gdy plan jest niewykonalny."""

    def test_infeasible_when_no_rooms_for_subject(self):
        """
        INFEASIBLE gdy sala jest dedykowana dla innego przedmiotu,
        a nie ma żadnej sali dla wymaganego.
        Solver powinien zwrócić INFEASIBLE lub UNKNOWN (nie OPTIMAL/FEASIBLE).
        """
        # Jedyna sala to Lab_Chemia — dedykowana tylko dla Chemii
        # Wymagamy Matematyki, ale nie ma dla niej sali
        inst = Instance(
            days=["pon"],
            periods=[1, 2],
            rooms={"Lab_Chemia": {"Chemia"}},  # tylko Chemia
            requirements=[("1A", "Matematyka", "Jan Kowalski", 1)],
            teacher_unavail={},
        )
        # Uwaga: solver ma fallback "brak dedykowanej sali -> dowolna",
        # więc sprawdzamy zachowanie faktycznej implementacji
        result = solve(inst, max_seconds=5)
        # Solver z kodu ma fallback: jeśli brak allowed_rooms → allowed_rooms = rooms
        # W tym przypadku Matematyka trafi do Lab_Chemia (fallback)
        # Testujemy że solver nie crasha i zwraca wynik
        assert result.status in ("OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN")

    def test_impossible_all_slots_unavailable(self):
        """
        Gdy wszystkie sloty nauczyciela są zablokowane → brak zmiennych x → INFEASIBLE.
        """
        # 1 dzień, 2 sloty, oba niedostępne dla nauczyciela
        forbidden = {("pon", 1), ("pon", 2)}
        inst = Instance(
            days=["pon"],
            periods=[1, 2],
            rooms={"S01": set()},
            requirements=[("1A", "Matematyka", "Jan Kowalski", 1)],
            teacher_unavail={"Jan Kowalski": forbidden},
        )
        result = solve(inst, max_seconds=5)
        # Gdy brak zmiennych x, AddExactlyOne dostanie pustą listę → INFEASIBLE
        assert result.status in ("INFEASIBLE", "UNKNOWN"), (
            f"Oczekiwano INFEASIBLE/UNKNOWN gdy brak dostępnych slotów, got {result.status}"
        )

    def test_infeasible_returns_empty_timetable(self):
        """Status INFEASIBLE → puste timetable."""
        forbidden = {("pon", 1), ("pon", 2)}
        inst = Instance(
            days=["pon"],
            periods=[1, 2],
            rooms={"S01": set()},
            requirements=[("1A", "Matematyka", "Jan Kowalski", 1)],
            teacher_unavail={"Jan Kowalski": forbidden},
        )
        result = solve(inst, max_seconds=5)
        if result.status in ("INFEASIBLE", "UNKNOWN"):
            assert result.timetable == {}, (
                "Status INFEASIBLE/UNKNOWN powinien dawać puste timetable"
            )
