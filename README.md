# FantasyDraftTracker
Two terminals from the project root:

Terminal 1 — Backend:


venv/bin/python -m uvicorn src.web.app:app --reload
Terminal 2 — Frontend (dev with hot reload):


cd frontend && npm run dev
Then open http://localhost:5173.