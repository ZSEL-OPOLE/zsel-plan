"""iCal (RFC 5545) export for timetable data."""

from __future__ import annotations
import uuid
from datetime import date, timedelta

# Godziny startowe/końcowe per numer lekcji (Zał. Organiz. ZSEL Opole)
PERIOD_TIMES: dict[int, tuple[str, str]] = {
    1: ("0800", "0845"),
    2: ("0855", "0940"),
    3: ("0950", "1035"),
    4: ("1050", "1135"),
    5: ("1155", "1240"),
    6: ("1250", "1335"),
    7: ("1345", "1430"),
    8: ("1440", "1525"),
    9: ("1535", "1620"),
}

DAY_NAMES_PL = ["pon", "wt", "sr", "czw", "pt"]
RRULE_DAYS = ["MO", "TU", "WE", "TH", "FR"]


def _next_weekday(d: date, weekday: int) -> date:
    """Return `d` or the next date with the given weekday (0=Mon)."""
    diff = (weekday - d.weekday()) % 7
    return d + timedelta(days=diff)


def _escape(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


def build_ical(
    lekcje: list[dict],
    *,
    filter_by: str | None = None,
    filter_field: str = "klasa",
    school_year_start: date | None = None,
    school_year_end: date | None = None,
) -> str:
    """
    Build an iCal calendar from a list of lesson dicts.

    Each lesson dict: {klasa, dzien, dzien_idx, okres, przedmiot, nauczyciel, sala}

    filter_by / filter_field: optionally filter to one class or teacher.
    school_year_start: first Monday of school year (default: nearest coming Monday).
    school_year_end: last day of school year (default: start + 40 weeks).
    """
    today = date.today()
    if school_year_start is None:
        school_year_start = _next_weekday(today, 0)  # nearest Monday
    if school_year_end is None:
        school_year_end = school_year_start + timedelta(weeks=40)

    until_str = school_year_end.strftime("%Y%m%dT235959Z")

    if filter_by is not None:
        lekcje = [lesson for lesson in lekcje if lesson.get(filter_field) == filter_by]

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ZSEL Opole//Plan Lekcji//PL",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-TIMEZONE:Europe/Warsaw",
    ]
    if filter_by:
        lines.append(f"X-WR-CALNAME:{_escape(filter_by)} — Plan lekcji")
    else:
        lines.append("X-WR-CALNAME:Plan lekcji ZSEL")

    for lesson in lekcje:
        day_idx = lesson["dzien_idx"]
        okres = lesson["okres"]
        if okres not in PERIOD_TIMES:
            continue
        t_start, t_end = PERIOD_TIMES[okres]

        # First occurrence = school_year_start (Monday) + day_idx days
        dtstart_date = school_year_start + timedelta(days=day_idx)
        dtstart = dtstart_date.strftime("%Y%m%d") + f"T{t_start}00"
        dtend = dtstart_date.strftime("%Y%m%d") + f"T{t_end}00"

        rrule_day = RRULE_DAYS[day_idx]
        rrule = f"FREQ=WEEKLY;BYDAY={rrule_day};UNTIL={until_str}"

        summary_parts = [lesson["przedmiot"]]
        if filter_field != "klasa":
            summary_parts.append(lesson["klasa"])
        summary_parts.append(lesson["sala"])
        summary = " / ".join(summary_parts)

        desc_parts = []
        if filter_field != "nauczyciel":
            desc_parts.append(f"Nauczyciel: {lesson['nauczyciel']}")
        desc_parts.append(f"Klasa: {lesson['klasa']}")
        desc_parts.append(f"Sala: {lesson['sala']}")
        desc = "\\n".join(desc_parts)

        uid = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{lesson['klasa']}-{lesson['przedmiot']}-{lesson['nauczyciel']}-{day_idx}-{okres}",
            )
        )

        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}@zsel.opole.pl",
            f"DTSTART;TZID=Europe/Warsaw:{dtstart}",
            f"DTEND;TZID=Europe/Warsaw:{dtend}",
            f"RRULE:{rrule}",
            f"SUMMARY:{_escape(summary)}",
            f"DESCRIPTION:{desc}",
            f"LOCATION:{_escape(lesson['sala'])}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    # RFC 5545: lines fold at 75 octets
    return _fold("\r\n".join(lines))


def _fold(text: str) -> str:
    """RFC 5545 line folding: lines > 75 chars get folded with CRLF+SPACE."""
    result = []
    for line in text.split("\r\n"):
        encoded = line.encode("utf-8")
        if len(encoded) <= 75:
            result.append(line)
            continue
        # fold
        chunks = []
        while len(encoded) > 75:
            # cut at 75 bytes (careful with multibyte)
            cut = encoded[:75]
            while len(cut) > 0 and (cut[-1] & 0xC0) == 0x80:  # UTF-8 continuation
                cut = cut[:-1]
            chunks.append(cut.decode("utf-8"))
            encoded = encoded[len(cut) :]
        if encoded:
            chunks.append(encoded.decode("utf-8"))
        result.append(("\r\n ").join(chunks))
    return "\r\n".join(result)
