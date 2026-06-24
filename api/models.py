from __future__ import annotations
from pydantic import BaseModel


class RequirementIn(BaseModel):
    klasa: str
    przedmiot: str
    nauczyciel: str
    godziny: int


class TeacherUnavailIn(BaseModel):
    nauczyciel: str
    sloty: list[tuple[str, int]]  # [("pon", 1), ...]


class SolveRequest(BaseModel):
    days: list[str] = ["pon", "wt", "sr", "czw", "pt"]
    periods: list[int] = list(range(1, 10))
    rooms: dict[str, list[str]]  # sala -> lista dozwolonych przedmiotów ([] = dowolne)
    requirements: list[RequirementIn]
    teacher_unavail: list[TeacherUnavailIn] = []
    max_seconds: int = 60


class LessonOut(BaseModel):
    klasa: str
    dzien: str
    dzien_idx: int
    okres: int
    przedmiot: str
    nauczyciel: str
    sala: str


class SolveResponse(BaseModel):
    status: str
    gaps: int
    lekcje: list[LessonOut]
