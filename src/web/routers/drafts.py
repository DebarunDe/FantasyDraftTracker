"""Draft CRUD endpoints: create, list, get, delete, roster, export."""

import asyncio
import io
import logging
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.draft_manager.draft_initializer import DraftInitializer
from src.draft_manager.state_persistence import StatePersistence
from src.ui.export import DraftExporter
from src.web.schemas import (
    CreateDraftRequest,
    DraftSummaryResponse,
    SavedDraftMeta,
)
from src.web.serializers import draft_state_to_response, player_info_to_response
from src.web.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.post("", response_model=DraftSummaryResponse, status_code=201)
async def create_draft(body: CreateDraftRequest) -> DraftSummaryResponse:
    """Create a new draft from the provided league configuration."""
    try:
        initializer = DraftInitializer()
        draft_state = initializer.create_draft(
            league_size=body.league_size,
            scoring_format=body.scoring_format,
            roster_slots=body.roster_slots,
            team_names=body.team_names,
            human_team_id=body.human_team_id,
            draft_mode=body.draft_mode,
            data_year=body.data_year,
            pick_trades=[t.model_dump() for t in body.pick_trades],
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    session = SessionManager.create_session(draft_state)
    session.persistence.save_draft(draft_state)

    return draft_state_to_response(draft_state)


@router.get("", response_model=List[SavedDraftMeta])
async def list_drafts() -> List[SavedDraftMeta]:
    """Return metadata for all saved drafts, newest first."""
    persistence = StatePersistence()
    raw = persistence.list_saved_drafts()
    return [
        SavedDraftMeta(
            draft_id=d["draft_id"],
            start_time=d["start_time"],
            is_complete=d["is_complete"],
            current_round=d["current_round"],
            current_pick=d["current_pick"],
            league_size=d["league_size"],
            scoring_format=d["scoring_format"],
        )
        for d in raw
    ]


@router.get("/{draft_id}", response_model=DraftSummaryResponse)
async def get_draft(draft_id: str) -> DraftSummaryResponse:
    """Return the full draft state for an existing draft."""
    session = SessionManager.load_or_create(draft_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    return draft_state_to_response(session.draft_state)


@router.delete("/{draft_id}", status_code=204)
async def delete_draft(draft_id: str) -> None:
    """Delete a saved draft file and remove its session."""
    persistence = StatePersistence()
    deleted = persistence.delete_draft(draft_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    SessionManager.remove_session(draft_id)


@router.post("/{draft_id}/advance", status_code=202)
async def advance_draft(draft_id: str) -> dict:
    """Trigger the computer pick chain if the current team is a computer.

    Called by the frontend on initial load (and on resume) so that any
    leading or consecutive computer turns run automatically without waiting
    for the human to make a pick first.

    Returns immediately (202 Accepted); picks stream in via WebSocket.
    """
    session = SessionManager.load_or_create(draft_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    state = session.draft_state
    if (
        not state.is_complete
        and state.league_config.draft_mode == "simulation"
        and not state.get_current_team().is_human
        and not session.lock.locked()
    ):
        from src.web.tasks.computer_pick_task import computer_pick_chain

        asyncio.create_task(computer_pick_chain(draft_id))

    return {"status": "ok"}


@router.post("/{draft_id}/sim", status_code=202)
async def simulate_draft(draft_id: str) -> dict:
    """Instantly simulate all remaining picks (all teams, no delay).

    Mirrors the CLI 'sim' command. Only valid in simulation mode.
    """
    session = SessionManager.load_or_create(draft_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    state = session.draft_state
    if state.is_complete:
        raise HTTPException(status_code=409, detail="Draft is already complete")
    if state.league_config.draft_mode != "simulation":
        raise HTTPException(status_code=422, detail="'sim' is only available in simulation mode")
    if session.lock.locked():
        raise HTTPException(status_code=409, detail="A pick is already in progress")

    from src.web.tasks.computer_pick_task import fast_sim_chain

    asyncio.create_task(fast_sim_chain(draft_id))
    return {"status": "ok"}


@router.get("/{draft_id}/roster/{team_id}")
async def get_roster(draft_id: str, team_id: int):
    """Return a team's current roster with full player details."""
    session = SessionManager.load_or_create(draft_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    state = session.draft_state
    if team_id < 0 or team_id >= state.league_config.league_size:
        raise HTTPException(
            status_code=422,
            detail=f"team_id must be 0-{state.league_config.league_size - 1}",
        )

    scoring = state.league_config.scoring_format
    roster_raw = session.controller.get_team_roster(team_id)
    roster_response = {
        slot: [player_info_to_response(p, scoring) for p in players]
        for slot, players in roster_raw.items()
    }
    team = state.get_team(team_id)
    return {
        "team_id": team_id,
        "team_name": team.team_name,
        "is_human": team.is_human,
        "roster": roster_response,
    }


@router.get("/{draft_id}/export")
async def export_draft(draft_id: str) -> StreamingResponse:
    """Download the draft picks as a CSV file."""
    session = SessionManager.load_or_create(draft_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    state = session.draft_state
    exporter = DraftExporter()
    try:
        csv_path = exporter.export_to_csv(state, state.league_config.scoring_format)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    with open(csv_path, "r", encoding="utf-8") as f:
        content = f.read()

    return StreamingResponse(
        io.StringIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=draft_{draft_id[:8]}.csv"},
    )
