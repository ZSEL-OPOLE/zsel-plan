"""
ZSEL — silnik własnego planu lekcji (OR-Tools CP-SAT).
Constraint solving = rdzeń "AI" optymalizacyjnej. LLM (osobno) tłumaczy potrzeby ludzi
("nie chcę okienek", "WF rano") na constraints/wagi tutaj.

Model:
  - Lekcja = (klasa, przedmiot, nauczyciel) powtórzona `godziny` razy w tygodniu.
  - Sloty = dni (pon-pt) × lekcje (1..N).
  - Zmienna: dla każdej instancji lekcji -> (slot, sala).

Twarde reguły (hard): brak kolizji klasy/nauczyciela/sali; sala zgodna z przedmiotem;
  każda godzina umieszczona; max 1 lekcja klasy/slot.
Miękkie (soft, minimalizowane): okienka klas, >1 ta sama lekcja dziennie, nierównomierność.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from ortools.sat.python import cp_model


@dataclass
class Instance:
    days: list[str]                      # ["pon","wt","sr","czw","pt"]
    periods: list[int]                   # [1..9]
    rooms: dict[str, set[str]]           # sala -> {przedmioty dozwolone} (pusty = dowolny)
    # wymagania: lista (klasa, przedmiot, nauczyciel, godziny_tygodniowo)
    requirements: list[tuple[str, str, str, int]]
    teacher_unavail: dict[str, set[tuple[str, int]]] = field(default_factory=dict)  # nauczyciel -> {(dzien,period) niedostępne}


@dataclass
class Result:
    status: str
    # plan: (klasa, dzien, period) -> (przedmiot, nauczyciel, sala)
    timetable: dict[tuple[str, int, int], tuple[str, str, str]] = field(default_factory=dict)
    gaps: int = 0


def solve(inst: Instance, max_seconds: int = 30) -> Result:
    m = cp_model.CpModel()
    D, P = range(len(inst.days)), inst.periods
    slots = [(d, p) for d in D for p in P]
    rooms = list(inst.rooms.keys())

    # rozwiń wymagania na pojedyncze godziny
    lessons = []  # (idx, klasa, przedmiot, nauczyciel)
    for (kl, prz, naucz, h) in inst.requirements:
        for _ in range(h):
            lessons.append((len(lessons), kl, prz, naucz))

    # zmienne: x[lekcja, slot, sala] = 1
    x = {}
    for (i, kl, prz, naucz) in lessons:
        allowed_rooms = [r for r in rooms if not inst.rooms[r] or prz in inst.rooms[r]]
        if not allowed_rooms:
            allowed_rooms = rooms  # brak dedykowanej sali -> dowolna
        for s, (d, p) in enumerate(slots):
            if (inst.days[d], p) in inst.teacher_unavail.get(naucz, set()):
                continue
            for r in allowed_rooms:
                x[(i, s, r)] = m.NewBoolVar(f"x_{i}_{s}_{r}")

    # każda godzina dokładnie raz
    for (i, *_rest) in lessons:
        m.AddExactlyOne(v for (ii, s, r), v in x.items() if ii == i)

    # klasa: max 1 lekcja na slot
    for kl in {l[1] for l in lessons}:
        for s in range(len(slots)):
            m.Add(sum(v for (i, ss, r), v in x.items()
                      if ss == s and lessons[i][1] == kl) <= 1)
    # nauczyciel: max 1 na slot
    for naucz in {l[3] for l in lessons}:
        for s in range(len(slots)):
            m.Add(sum(v for (i, ss, r), v in x.items()
                      if ss == s and lessons[i][3] == naucz) <= 1)
    # sala: max 1 na slot
    for r in rooms:
        for s in range(len(slots)):
            m.Add(sum(v for (i, ss, rr), v in x.items()
                      if ss == s and rr == r) <= 1)

    # soft: ten sam przedmiot max 1x dziennie per klasa (kara za nadmiar)
    penalties = []
    by_class_subj_day = {}
    for (i, kl, prz, naucz) in lessons:
        for s, (d, p) in enumerate(slots):
            for r in rooms:
                if (i, s, r) in x:
                    by_class_subj_day.setdefault((kl, prz, d), []).append(x[(i, s, r)])
    for key, vs in by_class_subj_day.items():
        over = m.NewIntVar(0, len(P), f"over_{key}")
        m.Add(over >= sum(vs) - 1)
        penalties.append(over)

    # soft: okienka klas — minimalizuj dziury między pierwszą a ostatnią lekcją
    gap_terms = []
    for kl in {l[1] for l in lessons}:
        for d in D:
            busy = {}
            for p_idx, p in enumerate(P):
                s = d * len(P) + p_idx
                b = m.NewBoolVar(f"busy_{kl}_{d}_{p}")
                m.Add(b == sum(v for (i, ss, r), v in x.items()
                               if ss == s and lessons[i][1] == kl))
                busy[p_idx] = b
            first = m.NewIntVar(0, len(P), f"first_{kl}_{d}")
            last = m.NewIntVar(-1, len(P)-1, f"last_{kl}_{d}")
            cnt = m.NewIntVar(0, len(P), f"cnt_{kl}_{d}")
            m.Add(cnt == sum(busy.values()))
            for p_idx in range(len(P)):
                m.Add(first <= p_idx).OnlyEnforceIf(busy[p_idx])
                m.Add(last >= p_idx).OnlyEnforceIf(busy[p_idx])
            span = m.NewIntVar(0, len(P), f"span_{kl}_{d}")
            m.Add(span >= last - first + 1 - (len(P)) * (1 - m.NewBoolVar(f"any_{kl}_{d}")))
            gap = m.NewIntVar(0, len(P), f"gap_{kl}_{d}")
            m.Add(gap >= span - cnt)
            gap_terms.append(gap)

    m.Minimize(10 * sum(gap_terms) + 5 * sum(penalties))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_seconds
    solver.parameters.num_search_workers = 8
    st = solver.Solve(m)
    status = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE",
              cp_model.INFEASIBLE: "INFEASIBLE", cp_model.UNKNOWN: "UNKNOWN"}.get(st, str(st))
    res = Result(status=status)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (i, s, r), v in x.items():
            if solver.Value(v):
                d, p = slots[s]
                kl, prz, naucz = lessons[i][1], lessons[i][2], lessons[i][3]
                res.timetable[(kl, d, p)] = (prz, naucz, r)
        res.gaps = int(solver.Value(sum(gap_terms))) if gap_terms else 0
    return res
