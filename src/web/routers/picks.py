"""Pick execution endpoint: POST /api/drafts/{id}/picks."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from src.draft_manager.draft_rules import ValidationError
from src.web.schemas import MakePickRequest, PickResponse
from src.web.serializers import _reach_label, draft_state_to_response
from src.web.session_manager import SessionManager
from src.web.websocket.connection_manager import manager
from src.web.websocket.events import build_pick_made_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drafts", tags=["picks"])


@router.post("/{draft_id}/picks", response_model=PickResponse)
async def make_pick(draft_id: str, body: MakePickRequest) -> PickResponse:
    """Execute a human (or manual-tracker) pick and spawn computer chain if needed."""
    session = SessionManager.load_or_create(draft_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    state = session.draft_state
    if state.is_complete:
        raise HTTPException(status_code=409, detail="Draft is already complete")

    async with session.lock:
        try:
            pick = session.controller.make_pick(body.team_id, body.player_id)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        try:
            session.persistence.save_draft(state)
        except OSError as exc:
            logger.warning("Auto-save failed for draft %s: %s", draft_id, exc)

    info = state.player_data.get(pick.player_id, {})
    overall_rank = info.get("overall_rank")
    delta = (pick.pick_number - overall_rank) if overall_rank else None

    pick_resp = PickResponse(
        pick_number=pick.pick_number,
        round=pick.round,
        team_id=pick.team_id,
        player_id=pick.player_id,
        player_name=info.get("name", pick.player_id),
        position=info.get("position", ""),
        nfl_team=info.get("team", ""),
        slot=pick.slot,
        timestamp=pick.timestamp,
        reach_delta=delta,
        reach_label=_reach_label(delta) if delta is not None else "",
    )

    # Broadcast pick to all connected WebSocket clients
    await manager.broadcast(
        draft_id,
        build_pick_made_event(pick_resp, draft_state_to_response(state)),
    )

    # Spawn computer chain if simulation mode and next team is a computer
    if (
        not state.is_complete
        and state.league_config.draft_mode == "simulation"
        and not state.get_current_team().is_human
    ):
        from src.web.tasks.computer_pick_task import computer_pick_chain

        asyncio.create_task(computer_pick_chain(draft_id))

    return pick_resp
