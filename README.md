# zsel-plan — własny plan lekcji ZSEL (zamiast Optivum) + AI

Lokalny system układania planu. Rdzeń = solver constraintowy (OR-Tools CP-SAT). DZIAŁA.

## Szybki start (demo na danych ZSEL)
```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python demo/demo.py     # generuje OPTYMALNY plan 4 klas: 0 okienek, 0 kolizji
```

## Szybki start — API (lokalnie)
```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
PYTHONPATH=. uvicorn api.main:app --reload --port 8000
# Otwórz http://localhost:8000/docs
```

## Deploy (K8s / GitOps)
```bash
# 1. Zbuduj i wypchnij obraz do wewnętrznego registry:
kubectl port-forward svc/zot-registry -n registry 5000:5000 &
docker build -t localhost:5000/zsel/plan-lekcji:latest .
docker push localhost:5000/zsel/plan-lekcji:latest

# 2. Zastosuj manifest (lub przez ArgoCD):
kubectl apply -f ../../ekosystem/zsel-edu/plan/plan.yaml

# 3. Po uruchomieniu — załaduj plan (POST /api/plan/solve) i subskrybuj w Nextcloud:
python scripts/nc_subscribe_calendars.py \
  --nc-url https://dysk.zsel.opole.pl \
  --nc-user akadmin --nc-pass SECRET \
  --plan-url https://plan.zsel.opole.pl \
  --rok-start 2026-09-01
```

## Endpointy API
- `POST /api/plan/solve` — wygeneruj plan z wymagań (zwraca JSON + cachuje)
- `GET /api/plan/klasa/{klasa}` — tygodniowy plan klasy (JSON)
- `GET /api/plan/nauczyciel/{n}` — plan nauczyciela (JSON)
- `GET /api/plan/ical/klasa/{klasa}?rok_start=YYYY-MM-DD` — **iCal dla Nextcloud Calendar**
- `GET /api/plan/ical/nauczyciel/{n}` — iCal dla nauczyciela
- `GET /api/plan/ical/all` — cały plan szkoły (iCal)
- `GET /docs` — Swagger UI

## Struktura
- `solver/solver.py` — silnik CP-SAT (twarde+miękkie reguły). Rdzeń optymalizacji.
- `demo/demo.py` — demo na realnych klasach 1. roku ZSEL.
- `api/main.py` — FastAPI: /solve + /ical/* + /klasa/* endpointy.
- `api/ical.py` — generator RFC 5545 iCal z godzinami ZSEL, RRULE tygodniowe.
- `api/models.py` — Pydantic modele żądania/odpowiedzi.
- `scripts/nc_subscribe_calendars.py` — masowa subskrypcja CalDAV w Nextcloud.

## Reguły
Twarde: brak kolizji klasy/nauczyciela/sali, sala↔przedmiot, niedostępności, wszystkie godziny.
Miękkie (minimalizowane): okienka, ta sama lekcja >1×/dzień. Rozszerzalne o preferencje.

## AI
- LLM (Ollama) tłumaczy potrzeby po polsku → reguły/wagi solvera.
- Zastępstwa: solver szuka wolnego nauczyciela przedmiotu; LLM komunikuje.
- Q&A: TechBuddy RAG nad opublikowanym planem.

Projekt: ../../REPOS/PLAN-LEKCJI-DESIGN.md
# Built via GitHub Actions on zsel-general org-level runner (ARC v2)

