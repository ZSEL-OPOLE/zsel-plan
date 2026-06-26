## Co zmienia ten PR?

<!-- Krótki opis zmiany -->

## Typ zmiany

- [ ] `feat` — nowa funkcjonalność solvera / API
- [ ] `fix` — naprawa błędu
- [ ] `chore` — maintenance, zależności
- [ ] `docs` — dokumentacja

## Checklist jakości

- [ ] Testy dodane / zaktualizowane (`tests/`)
- [ ] Coverage ≥ 60% — `pytest --cov-fail-under=60` przechodzi
- [ ] Ruff lint i format: `ruff check . && ruff format --check .`
- [ ] Solver testowany na przykładowym planie (test_solver.py)
- [ ] API testowane przez TestClient (test_api.py)
- [ ] iCal output poprawny (test_ical.py)

## Wpływ na deploy

- [ ] Wymaga aktualizacji `requirements.txt`
- [ ] Wymaga aktualizacji manifestu w gitops-infra (`06-apps/manifests/plan/`)
- [ ] Zmiana API — zaktualizować OpenAPI docs

## Jak przetestować?

```bash
PYTHONPATH=. pytest tests/ -v
```
