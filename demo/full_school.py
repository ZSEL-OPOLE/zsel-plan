"""Skala: generuje plan dla CAŁEJ szkoły z seedu (klasy + plan godzin + kadra). Dowód wydajności solvera."""
import sys, os, yaml, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from solver.solver import Instance, solve

SEED = os.path.join(os.path.dirname(__file__), "..", "..", "..", "zsel-tozsamosc", "seed")
klasy = yaml.safe_load(open(os.path.join(SEED, "klasy.yaml")))
godz  = yaml.safe_load(open(os.path.join(SEED, "plan-godzin.yaml")))
kadra = yaml.safe_load(open(os.path.join(SEED, "kadra.yaml")))

DAYS = ["pon","wt","sr","czw","pt"]; PERIODS = list(range(1,10))  # 9 lekcji

# pula sal per przedmiot (z profilu sal) — reszta ogólna
ROOM_MAP = {
 "pol":["11","12","15"], "ang":["17","40","45","48"], "niem":["41","43","53"],
 "mat":["38","49","50","51","52"], "fiz":["47"], "chem":["46"], "biol":["44"],
 "hist":["22"], "geo":["21"], "wos":["22"], "rel":["16"], "inf":["9","25","28","30","31","42"],
 "wf":["g1","g2","g3","g4"], "dor":["5"], "edb":["16"], "biz":["39"], "ezdr":["44"],
 "zaw_el":["39","e1","e2"], "zaw_masz":["8"], "zaw_elektron":["e1","e2"],
 "zaw_inf":["9","25","28","30","31","42"], "zaw_tele":["26","27"],
 "zaw_mech":["8","23"], "zaw_auto":["23","24"],
}
GENERAL = ["20","19","18","14","13","10"]  # zapasowe ogólne (gdyby brakło)
ROOMS = {}
for prz, rs in ROOM_MAP.items():
    for r in rs: ROOMS.setdefault(r, set()).add(prz)
for r in GENERAL: ROOMS.setdefault(r, set())  # ogólne

# przydział nauczycieli: round-robin z puli przedmiotu, limit godzin/nauczyciel
load = collections.Counter()
pool_idx = collections.Counter()
def pick_teacher(subj, hours, cap=24):
    pool = kadra["nauczyciele"].get(subj) or kadra.get("wspomagajaca",{}).get(subj) or [f"{subj}-N"]
    for _ in range(len(pool)):
        t = pool[pool_idx[subj] % len(pool)]; pool_idx[subj]+=1
        if load[t] + hours <= cap:
            load[t]+=hours; return t
    t = pool[pool_idx[subj] % len(pool)]; pool_idx[subj]+=1; load[t]+=hours; return t

REQ=[]; total_h=0
def build(classes, ogkey, zawkey):
    global total_h
    for c in classes:
        rok=c["rok"]; og=godz[ogkey].get(rok,{})
        for subj,h in og.items():
            REQ.append((c["id"],subj,pick_teacher(subj,h),h)); total_h+=h
        zh=godz[zawkey].get(rok,0); zps=[]
        for z in c["zawod"]:
            zps += godz["zawod_przedmioty"].get(z,[])
        zps=list(dict.fromkeys(zps)) or ["zaw_el"]
        per=max(1,zh//len(zps)); rem=zh-per*len(zps)
        for i,zp in enumerate(zps):
            hh=per+(1 if i<rem else 0)
            if hh: REQ.append((c["id"],zp,pick_teacher(zp,hh),hh)); total_h+=hh

build(klasy["technikum"],"ogolne","zawodowe_h")
build(klasy["branzowa_1st"],"branzowa_ogolne","branzowa_zawodowe_h")
build(klasy["branzowa_2st"],"branzowa_ogolne","branzowa_zawodowe_h")

n_classes=len({r[0] for r in REQ}); n_teach=len({r[2] for r in REQ})
print(f">>> CAŁA SZKOŁA: {n_classes} oddziałów, {total_h} godzin/tydzień, {n_teach} nauczycieli, {len(ROOMS)} sal")
inst=Instance(days=DAYS,periods=PERIODS,rooms=ROOMS,requirements=REQ)
res=solve(inst,max_seconds=120)
print(f">>> Status: {res.status} | suma okienek: {res.gaps}")
if res.timetable:
    # walidacja kolizji
    st,sr,clash=set(),set(),0
    for (kl,d,p),(prz,n,r) in res.timetable.items():
        if (n,d,p) in st: clash+=1
        if (r,d,p) in sr: clash+=1
        st.add((n,d,p)); sr.add((r,d,p))
    placed=len(res.timetable)
    print(f">>> Umieszczono {placed}/{total_h} godzin | kolizje nauczyciel/sala: {clash}")
    # przykład jednej klasy
    ex=sorted({r[0] for r in REQ})[0]
    print(f"\n=== przykład: {ex} ===")
    for p in PERIODS:
        row=[res.timetable.get((ex,di,p)) for di in range(5)]
        print(f" {p} | "+" | ".join((f"{c[0][:6]:6}/{c[2]:>3}" if c else " "*10) for c in row))
