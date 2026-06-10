# CI Check

Run all CI steps locally and auto-fix any issues before pushing. Mirrors `.github/workflows/ci.yml` exactly.

## Steps

**1. Backend — auto-fix lint issues**
```bash
venv/bin/ruff check --fix src/ tests/
```
If this modifies files, note which ones were fixed.

**2. Backend — auto-fix formatting**
```bash
venv/bin/ruff format src/ tests/
```
If this modifies files, note which ones were reformatted.

**3. Backend — verify both checks now pass clean**
```bash
venv/bin/ruff check src/ tests/ && venv/bin/ruff format --check src/ tests/ && echo "ruff OK"
```
If either fails, investigate and fix before proceeding.

**4. Backend — run data pipeline**
```bash
venv/bin/python -m src.data_pipeline.run_update
```
Must complete without errors (generates `data/processed/players_2025.json`).

**5. Backend — run tests with coverage**
```bash
venv/bin/python -m pytest tests/ -m "not slow" --cov=src --cov-report=term-missing -q
```
All tests must pass. Report final count (e.g. "854 passed").

**6. Frontend — type check**
```bash
cd frontend && npm run typecheck
```

**7. Frontend — lint**
```bash
cd frontend && npm run lint
```
If lint errors are auto-fixable, run `npm run lint -- --fix` and note what changed.

**8. Frontend — tests**
```bash
cd frontend && npm run test:coverage
```

## Reporting

After all steps complete, summarize:
- Which files were auto-fixed (if any) and what kind of issues
- Final test counts (backend + frontend)
- Whether the branch is clean and ready to push

If any step fails and cannot be auto-fixed, describe the error clearly so the user can decide how to proceed.
