"""Demo: własny plan lekcji ZSEL na realnych klasach 1. roku. Uruchom: python demo/demo.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from solver.solver import Instance, solve

DAYS = ["pon", "wt", "sr", "czw", "pt"]
PERIODS = list(range(1, 9))  # 8 lekcji

# Sale: pusty zbiór = ogólna; z przedmiotami = pracownia dedykowana
ROOMS = {
    "11": {"pol"}, "15": {"pol"}, "52": {"mat"}, "49": {"mat"}, "47": {"fiz"},
    "17": {"ang"}, "45": {"ang"}, "41": {"niem"}, "22": {"hist"}, "16": {"rel"},
    "28": {"inf", "zaw_inf"}, "30": {"inf", "zaw_inf"}, "23": {"zaw_auto"},
    "39": {"zaw_el"}, "e1": {"zaw_el"}, "g1": {"wf"}, "g2": {"wf"},
    "21": set(), "24": set(),  # ogólne zapasowe
}

# (klasa, przedmiot, nauczyciel, godziny/tydzień) — realistyczny rozkład 1. roku
REQ = []
def add(kl, items):
    for prz, n, h in items: REQ.append((kl, prz, n, h))

add("1at", [("pol","Mansfeld",3),("mat","Kozicka",4),("ang","Dobosz",3),("niem","Dratwa",2),
            ("hist","Trusz",2),("fiz","Kowol",2),("inf","Stanisławska",2),("wf","Kaleta",3),
            ("rel","Kubis",1),("zaw_mech","Chwaliński",4)])
add("1bt", [("pol","Czerkawska",3),("mat","Natalli",4),("ang","Kmieć",3),("niem","Lisowska",2),
            ("hist","Dzionek",2),("fiz","Myśluk",2),("inf","Moch",2),("wf","Rączka",3),
            ("rel","Kubis",1),("zaw_el","Blozik",4)])
add("1ct", [("pol","Peczeniuk",3),("mat","Wojdyła",4),("ang","Rogala",3),("niem","Łomny",2),
            ("hist","Trusz",2),("fiz","Kowol",2),("inf","Nicpoń",2),("wf","Stykała",3),
            ("rel","Kubis",1),("zaw_inf","Dworaczyk",4)])
add("1dt", [("pol","Święs",3),("mat","Turek",4),("ang","Sukiennik",3),("niem","Suwalska",2),
            ("hist","Dzionek",2),("fiz","Myśluk",2),("inf","Rapiński",2),("wf","Skowron",3),
            ("rel","Kubis",1),("zaw_inf","Żminkowski",4)])

# przykładowa niedostępność: ks. Kubis (religia) tylko pon-wt
UNAVAIL = {"Kubis": {(d, p) for d in ["sr","czw","pt"] for p in PERIODS}}

inst = Instance(days=DAYS, periods=PERIODS, rooms=ROOMS, requirements=REQ, teacher_unavail=UNAVAIL)
print(f">>> Generuję plan: {len(REQ)} przedmioto-klas, {sum(r[3] for r in REQ)} godzin/tydzień, "
      f"{len({r[2] for r in REQ})} nauczycieli, {len(ROOMS)} sal...")
res = solve(inst, max_seconds=30)
print(f">>> Status: {res.status} | suma okienek (minimalizowane): {res.gaps}\n")

if res.timetable:
    for kl in ["1at","1bt","1ct","1dt"]:
        print(f"=== {kl} ===")
        print("godz | " + " | ".join(f"{d:^14}" for d in DAYS))
        for p in PERIODS:
            row = []
            for di, d in enumerate(DAYS):
                cell = res.timetable.get((kl, di, p))
                row.append(f"{cell[0]+'/'+cell[1][:4]+'/'+cell[2]:^14}" if cell else " "*14)
            print(f"  {p}  | " + " | ".join(row))
        print()
    # walidacja: zero kolizji nauczyciel/sala
    seen_t, seen_r, clash = set(), set(), 0
    for (kl,d,p),(prz,n,r) in res.timetable.items():
        if (n,d,p) in seen_t: clash+=1
        if (r,d,p) in seen_r: clash+=1
        seen_t.add((n,d,p)); seen_r.add((r,d,p))
    print(f">>> Walidacja kolizji nauczyciel/sala: {clash} (0 = poprawny plan)")
