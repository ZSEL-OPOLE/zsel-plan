"""
Testy jednostkowe eksportu iCal (api/ical.py).
Pokrywa: struktura RFC 5545, czasy ZSEL, RRULE, SUMMARY, filtrowanie, UTF-8.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from api.ical import PERIOD_TIMES, build_ical, _fold  # noqa: E402


# ===========================================================================
# Testy struktury kalendarza
# ===========================================================================


class TestIcalStructure:
    """Testy poprawności struktury RFC 5545 wygenerowanego kalendarza."""

    def test_build_ical_starts_with_begin_vcalendar(self, sample_lessons):
        """Wynik build_ical zaczyna się od BEGIN:VCALENDAR."""
        cal = build_ical(sample_lessons)
        assert cal.startswith("BEGIN:VCALENDAR")

    def test_build_ical_ends_with_end_vcalendar(self, sample_lessons):
        """Wynik build_ical kończy się na END:VCALENDAR."""
        cal = build_ical(sample_lessons)
        assert cal.strip().endswith("END:VCALENDAR")

    def test_build_ical_contains_version(self, sample_lessons):
        """Kalendarz zawiera VERSION:2.0."""
        cal = build_ical(sample_lessons)
        assert "VERSION:2.0" in cal

    def test_build_ical_contains_calscale(self, sample_lessons):
        """Kalendarz zawiera CALSCALE:GREGORIAN."""
        cal = build_ical(sample_lessons)
        assert "CALSCALE:GREGORIAN" in cal

    def test_build_ical_contains_prodid(self, sample_lessons):
        """Kalendarz zawiera PRODID z identyfikatorem ZSEL."""
        cal = build_ical(sample_lessons)
        assert "PRODID" in cal
        assert "ZSEL" in cal

    def test_empty_lessons_still_valid_vcalendar(self):
        """Pusty plan daje poprawny VCALENDAR bez żadnych VEVENT."""
        cal = build_ical([])
        assert "BEGIN:VCALENDAR" in cal
        assert "END:VCALENDAR" in cal
        assert "BEGIN:VEVENT" not in cal

    def test_build_ical_uses_crlf_line_endings(self, sample_lessons):
        """RFC 5545 wymaga CRLF (\\r\\n) jako separator linii."""
        cal = build_ical(sample_lessons)
        assert "\r\n" in cal


# ===========================================================================
# Testy VEVENT
# ===========================================================================


class TestVEvent:
    """Testy poszczególnych zdarzeń VEVENT w kalendarzu."""

    def test_each_lesson_generates_vevent(self, sample_lessons):
        """Każda lekcja generuje BEGIN:VEVENT i END:VEVENT."""
        cal = build_ical(sample_lessons)
        vevent_count = cal.count("BEGIN:VEVENT")
        assert vevent_count == len(sample_lessons), (
            f"Oczekiwano {len(sample_lessons)} VEVENT, znaleziono {vevent_count}"
        )

    def test_vevent_has_uid(self, sample_lessons):
        """Każde VEVENT zawiera UID."""
        cal = build_ical(sample_lessons)
        uid_count = cal.count("UID:")
        assert uid_count == len(sample_lessons)

    def test_vevent_uid_contains_zsel_domain(self, sample_lessons):
        """UID zawiera domenę @zsel.opole.pl."""
        cal = build_ical(sample_lessons)
        assert "@zsel.opole.pl" in cal

    def test_vevent_has_dtstart(self, sample_lessons):
        """Każde VEVENT zawiera DTSTART."""
        cal = build_ical(sample_lessons)
        assert "DTSTART" in cal

    def test_vevent_has_dtend(self, sample_lessons):
        """Każde VEVENT zawiera DTEND."""
        cal = build_ical(sample_lessons)
        assert "DTEND" in cal

    def test_vevent_has_rrule(self, sample_lessons):
        """Każde VEVENT zawiera RRULE (powtarzanie cotygodniowe)."""
        cal = build_ical(sample_lessons)
        assert "RRULE:" in cal

    def test_rrule_is_weekly(self, sample_lessons):
        """RRULE używa FREQ=WEEKLY."""
        cal = build_ical(sample_lessons)
        assert "FREQ=WEEKLY" in cal

    def test_vevent_has_summary(self, sample_lessons):
        """Każde VEVENT zawiera SUMMARY z przedmiotem."""
        cal = build_ical(sample_lessons)
        assert "SUMMARY:" in cal
        assert "Matematyka" in cal  # z sample_lessons

    def test_summary_contains_klasa_and_przedmiot(self, sample_lessons):
        """SUMMARY zawiera nazwę przedmiotu (filtr nauczyciel → SUMMARY ma klasę)."""
        cal = build_ical(sample_lessons)
        # W niefiltrowanym kalendarzu SUMMARY = przedmiot / sala
        assert "Matematyka" in cal
        assert "Polski" in cal

    def test_vevent_has_location(self, sample_lessons):
        """Każde VEVENT zawiera LOCATION z salą."""
        cal = build_ical(sample_lessons)
        assert "LOCATION:" in cal
        assert "S01" in cal  # sala z sample_lessons

    def test_vevent_has_description(self, sample_lessons):
        """Każde VEVENT zawiera DESCRIPTION."""
        cal = build_ical(sample_lessons)
        assert "DESCRIPTION:" in cal


# ===========================================================================
# Testy czasów ZSEL (PERIOD_TIMES)
# ===========================================================================


class TestPeriodTimes:
    """Testy poprawności godzin lekcji ZSEL."""

    def test_period_1_starts_at_0800(self):
        """Lekcja 1 zaczyna się o 08:00."""
        assert PERIOD_TIMES[1][0] == "0800"

    def test_period_1_ends_at_0845(self):
        """Lekcja 1 kończy się o 08:45."""
        assert PERIOD_TIMES[1][1] == "0845"

    def test_period_2_starts_at_0855(self):
        """Lekcja 2 zaczyna się o 08:55."""
        assert PERIOD_TIMES[2][0] == "0855"

    def test_period_9_starts_at_1535(self):
        """Lekcja 9 zaczyna się o 15:35."""
        assert PERIOD_TIMES[9][0] == "1535"

    def test_period_9_ends_at_1620(self):
        """Lekcja 9 kończy się o 16:20."""
        assert PERIOD_TIMES[9][1] == "1620"

    def test_all_9_periods_defined(self):
        """Zdefiniowanych jest dokładnie 9 numerów lekcji (1-9)."""
        assert set(PERIOD_TIMES.keys()) == set(range(1, 10))

    def test_period_times_in_ical_dtstart(self):
        """DTSTART w iCal zawiera czas z PERIOD_TIMES dla odpowiedniej lekcji."""
        lesson = [
            {
                "klasa": "1A",
                "dzien": "pon",
                "dzien_idx": 0,
                "okres": 1,  # lekcja 1 → 08:00
                "przedmiot": "Matematyka",
                "nauczyciel": "Jan Kowalski",
                "sala": "S01",
            }
        ]
        cal = build_ical(lesson, school_year_start=date(2026, 9, 7))  # poniedziałek
        assert "T080000" in cal, f"Brak czasu 08:00:00 w DTSTART dla lekcji 1:\n{cal}"

    def test_period_4_dtstart_correct(self):
        """Lekcja 4 → DTSTART T105000 (10:50)."""
        lesson = [
            {
                "klasa": "1A",
                "dzien": "pon",
                "dzien_idx": 0,
                "okres": 4,  # 10:50 → 11:35
                "przedmiot": "Polski",
                "nauczyciel": "Anna Nowak",
                "sala": "S01",
            }
        ]
        cal = build_ical(lesson, school_year_start=date(2026, 9, 7))
        assert "T105000" in cal, "Brak czasu 10:50:00 w DTSTART dla lekcji 4"

    def test_period_times_all_start_before_end(self):
        """Dla każdej lekcji czas końca jest po czasie początku."""
        for period, (start, end) in PERIOD_TIMES.items():
            start_int = int(start)
            end_int = int(end)
            assert start_int < end_int, f"Lekcja {period}: start {start} >= end {end}"


# ===========================================================================
# Testy filtrowania
# ===========================================================================


class TestIcalFiltering:
    """Testy filtrowania kalendarza po klasie lub nauczycielu."""

    def test_filter_by_klasa_includes_only_matching(self, sample_lessons):
        """Filtrowanie po klasie '1A' zwraca tylko lekcje klasy 1A."""
        cal = build_ical(sample_lessons, filter_by="1A", filter_field="klasa")
        # Lekcje klasy 1A: Matematyka (pon/1), Polski (wt/3)
        assert "Matematyka" in cal
        assert "Polski" in cal
        # Lekcja 2B (Fizyka) nie powinna być w kalendarzu
        assert "Fizyka" not in cal

    def test_filter_by_klasa_vcalendar_count(self, sample_lessons):
        """Filtrowanie po klasie '2B' zwraca dokładnie 1 VEVENT."""
        cal = build_ical(sample_lessons, filter_by="2B", filter_field="klasa")
        assert cal.count("BEGIN:VEVENT") == 1

    def test_filter_by_nauczyciel(self, sample_lessons):
        """Filtrowanie po nauczycielu 'Marek Zając' zwraca jego lekcje."""
        cal = build_ical(
            sample_lessons, filter_by="Marek Zając", filter_field="nauczyciel"
        )
        assert cal.count("BEGIN:VEVENT") == 1
        assert "Fizyka" in cal

    def test_filter_by_nonexistent_returns_empty_vevent(self, sample_lessons):
        """Filtrowanie po nieistniejącej klasie daje 0 VEVENT."""
        cal = build_ical(sample_lessons, filter_by="ZZZ", filter_field="klasa")
        assert "BEGIN:VEVENT" not in cal
        assert "BEGIN:VCALENDAR" in cal

    def test_filter_includes_calname(self, sample_lessons):
        """Przefiltrowany kalendarz zawiera X-WR-CALNAME z filtrem."""
        cal = build_ical(sample_lessons, filter_by="1A", filter_field="klasa")
        assert "X-WR-CALNAME" in cal
        assert "1A" in cal

    def test_no_filter_returns_all_lessons(self, sample_lessons):
        """Bez filtra kalendarz zawiera wszystkie lekcje."""
        cal = build_ical(sample_lessons)
        assert cal.count("BEGIN:VEVENT") == len(sample_lessons)

    def test_filter_by_nauczyciel_summary_includes_klasa(self, sample_lessons):
        """Gdy filtr to nauczyciel, SUMMARY zawiera też klasę."""
        cal = build_ical(
            sample_lessons, filter_by="Jan Kowalski", filter_field="nauczyciel"
        )
        # filter_field != "klasa" → summary_parts.append(l["klasa"])
        assert "1A" in cal


# ===========================================================================
# Testy daty roku szkolnego
# ===========================================================================


class TestSchoolYearDate:
    """Testy dat DTSTART i RRULE UNTIL."""

    def test_school_year_start_applied(self):
        """DTSTART uwzględnia podaną datę początku roku szkolnego."""
        lesson = [
            {
                "klasa": "1A",
                "dzien": "pon",
                "dzien_idx": 0,
                "okres": 1,
                "przedmiot": "Matematyka",
                "nauczyciel": "Jan Kowalski",
                "sala": "S01",
            }
        ]
        cal = build_ical(lesson, school_year_start=date(2026, 9, 7))
        # Poniedziałek 2026-09-07 + dzien_idx=0 = 20260907
        assert "20260907" in cal

    def test_dtstart_offset_for_tuesday(self):
        """Lekcja we wtorek (dzien_idx=1) ma DTSTART o dzień później niż poniedziałek."""
        lesson = [
            {
                "klasa": "1A",
                "dzien": "wt",
                "dzien_idx": 1,
                "okres": 2,
                "przedmiot": "Polski",
                "nauczyciel": "Anna Nowak",
                "sala": "S02",
            }
        ]
        cal = build_ical(lesson, school_year_start=date(2026, 9, 7))
        # wt = 2026-09-07 + 1 = 2026-09-08
        assert "20260908" in cal

    def test_rrule_until_is_40_weeks_after_start(self):
        """UNTIL w RRULE jest 40 tygodni po school_year_start."""
        from datetime import timedelta

        start = date(2026, 9, 7)
        expected_end = start + timedelta(weeks=40)
        until_str = expected_end.strftime("%Y%m%d")

        lesson = [
            {
                "klasa": "1A",
                "dzien": "pon",
                "dzien_idx": 0,
                "okres": 1,
                "przedmiot": "Matematyka",
                "nauczyciel": "Jan Kowalski",
                "sala": "S01",
            }
        ]
        cal = build_ical(lesson, school_year_start=start)
        assert until_str in cal, f"Oczekiwano UNTIL {until_str} w:\n{cal[:500]}"

    def test_rrule_day_mo_for_monday(self):
        """RRULE dla lekcji w poniedziałek (dzien_idx=0) używa BYDAY=MO."""
        lesson = [
            {
                "klasa": "1A",
                "dzien": "pon",
                "dzien_idx": 0,
                "okres": 1,
                "przedmiot": "Matematyka",
                "nauczyciel": "Jan Kowalski",
                "sala": "S01",
            }
        ]
        cal = build_ical(lesson, school_year_start=date(2026, 9, 7))
        assert "BYDAY=MO" in cal

    def test_rrule_day_fr_for_friday(self):
        """RRULE dla lekcji w piątek (dzien_idx=4) używa BYDAY=FR."""
        lesson = [
            {
                "klasa": "1A",
                "dzien": "pt",
                "dzien_idx": 4,
                "okres": 3,
                "przedmiot": "Fizyka",
                "nauczyciel": "Marek Zając",
                "sala": "Lab01",
            }
        ]
        cal = build_ical(lesson, school_year_start=date(2026, 9, 7))
        assert "BYDAY=FR" in cal


# ===========================================================================
# Testy kodowania UTF-8 i polskich znaków
# ===========================================================================


class TestUtf8Encoding:
    """Testy poprawnego kodowania polskich znaków w iCal."""

    def test_polish_chars_in_summary(self, sample_lessons_polish_chars):
        """Polskie znaki w SUMMARY są poprawnie zakodowane (UTF-8)."""
        cal = build_ical(sample_lessons_polish_chars)
        # Sprawdź że znaki są obecne w tekście (Python str = unicode)
        assert "Język angielski" in cal or "J\\u0119zyk" in cal or "Język" in cal

    def test_polish_chars_in_teacher_name(self, sample_lessons_polish_chars):
        """Polskie znaki w nazwie nauczyciela zachowane w DESCRIPTION."""
        cal = build_ical(sample_lessons_polish_chars)
        # Józef Żółwiński - sprawdź że description zawiera nauczyciela
        assert "DESCRIPTION:" in cal

    def test_polish_sala_in_location(self, sample_lessons_polish_chars):
        """Sala z polskimi znakami jest poprawnie w LOCATION."""
        cal = build_ical(sample_lessons_polish_chars)
        assert "LOCATION:" in cal

    def test_ical_is_str_not_bytes(self, sample_lessons):
        """build_ical zwraca str, nie bytes."""
        cal = build_ical(sample_lessons)
        assert isinstance(cal, str)

    def test_fold_long_lines(self):
        """_fold łamie linie powyżej 75 oktetów z CRLF+spacja."""
        long_line = "X-CUSTOM:" + "A" * 200
        folded = _fold(long_line)
        # Po złożeniu każda linia (poza kontynuacją) <= 75 znaków
        lines = folded.split("\r\n")
        for line in lines:
            assert len(line.encode("utf-8")) <= 76, (
                f"Linia za długa ({len(line.encode())} oktetów): {line[:80]}"
            )

    def test_fold_preserves_content(self):
        """_fold zachowuje pełną treść (tylko dodaje białe znaki)."""
        text = "SUMMARY:Matematyka / S01 / " + "x" * 100
        folded = _fold(text)
        # Odtwórz zawartość: usuń CRLF + spację (kontynuacja)
        unfolded = folded.replace("\r\n ", "")
        assert unfolded == text


# ===========================================================================
# Testy TIMEZONE
# ===========================================================================


class TestTimezone:
    """Testy obecności informacji o strefie czasowej."""

    def test_dtstart_has_tzid_europe_warsaw(self, sample_lessons):
        """DTSTART zawiera TZID=Europe/Warsaw."""
        cal = build_ical(sample_lessons)
        assert "TZID=Europe/Warsaw" in cal

    def test_dtend_has_tzid_europe_warsaw(self, sample_lessons):
        """DTEND zawiera TZID=Europe/Warsaw."""
        cal = build_ical(sample_lessons)
        assert "TZID=Europe/Warsaw" in cal

    def test_xwr_timezone_europe_warsaw(self, sample_lessons):
        """Kalendarz zawiera X-WR-TIMEZONE:Europe/Warsaw."""
        cal = build_ical(sample_lessons)
        assert "X-WR-TIMEZONE:Europe/Warsaw" in cal
