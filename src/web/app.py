"""FastAPI application factory for the Fantasy Draft Tracker web API.

Entry point:
    uvicorn src.web.app:app --reload

After `npm run build` in frontend/, the built assets are served from
frontend/dist/ at the root path so a single uvicorn process handles both
the API and the React SPA.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.web.routers import drafts, picks, players, recommendations
from src.web.websocket import draft_ws

app = FastAPI(
    title="Fantasy Draft Tracker API",
    version="1.0.0",
    description="REST + WebSocket API for the Fantasy Draft Tracker.",
)

# Allow the Vite dev server (default :5173) to call the API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # alternate dev port
        "http://localhost:8000",  # production (same origin)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routers
app.include_router(drafts.router)
app.include_router(picks.router)
app.include_router(players.router)
app.include_router(recommendations.router)

# WebSocket endpoint
app.include_router(draft_ws.router)


@app.get("/api/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


# Serve the built React frontend (Phase 8).
# Mount only if the dist/ directory exists so the API still starts during
# frontend development without a prior `npm run build`.
_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    # Serve index.html for all non-API routes (SPA client-side routing)
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
