"""Available players endpoint: GET /api/drafts/{id}/players."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.web.config import AVAILABLE_PLAYERS_PAGE_SIZE
from src.web.schemas import PlayerResponse
from src.web.serializers import player_info_to_response
from src.web.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drafts", tags=["players"])

VALID_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DST"}
# RB/WR/TE can spill into FLEX; they remain draftable even with 0 dedicated slots.
_FLEX_ELIGIBLE = {"RB", "WR", "TE"}


def _league_valid_positions(roster_slots: dict) -> set:
    """Return positions that can be drafted in this league configuration."""
    return {pos for pos in VALID_POSITIONS if roster_slots.get(pos, 0) > 0 or pos in _FLEX_ELIGIBLE}


@router.get("/{draft_id}/players", response_model=List[PlayerResponse])
async def get_players(
    draft_id: str,
    position: Optional[str] = Query(None, description="Filter by position (QB/RB/WR/TE/K/DST)"),
    limit: int = Query(AVAILABLE_PLAYERS_PAGE_SIZE, ge=1, le=500),
    offset: int = Query(0, ge=0),
    name: Optional[str] = Query(
        None, description="Case-insensitive substring filter on player name"
    ),
) -> List[PlayerResponse]:
    """Return available players, optionally filtered by position, sorted by VOR.

    Positions excluded from this league (0 dedicated slots and not FLEX-eligible)
    are automatically omitted so they never appear in the Available panel.
    """
    session = SessionManager.load_or_create(draft_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    if position is not None:
        position = position.upper()
        if position not in VALID_POSITIONS:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid position '{position}'. Must be one of {sorted(VALID_POSITIONS)}",
            )

    state = session.draft_state
    scoring = state.league_config.scoring_format
    valid_positions = _league_valid_positions(state.league_config.roster_slots)

    # Caller requested an excluded position — nothing to return
    if position is not None and position not in valid_positions:
        return []

    players = session.controller.get_available_players(position=position)

    # Strip players whose positions are excluded from this league
    players = [p for p in players if p.get("position") in valid_positions]

    # Filter by name substring if provided
    if name:
        name_lower = name.lower()
        players = [p for p in players if name_lower in p.get("name", "").lower()]

    # Sort by baseline VOR for the current scoring format, descending
    players.sort(
        key=lambda p: (
            p.get("baseline_vor", {}).get(scoring, 0.0)
            if isinstance(p.get("baseline_vor"), dict)
            else 0.0
        ),
        reverse=True,
    )

    page = players[offset : offset + limit]
    return [player_info_to_response(p, scoring) for p in page]
