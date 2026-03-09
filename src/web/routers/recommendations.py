"""Recommendations endpoint: GET /api/drafts/{id}/recommendations."""

import asyncio
import logging
from functools import partial
from typing import List

from fastapi import APIRouter, HTTPException

from src.web.config import WEB_RECOMMENDATIONS_COUNT
from src.web.schemas import RecommendationResponse
from src.web.serializers import recommendation_to_response
from src.web.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drafts", tags=["recommendations"])


@router.get("/{draft_id}/recommendations", response_model=List[RecommendationResponse])
async def get_recommendations(draft_id: str) -> List[RecommendationResponse]:
    """Return top recommendations for the current team.

    The Monte Carlo simulator takes ~300ms, so the heavy computation runs
    in a thread-pool executor to avoid blocking the asyncio event loop.
    """
    session = SessionManager.load_or_create(draft_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    state = session.draft_state
    if state.is_complete:
        return []

    current_team = state.get_current_team()
    available = session.controller.get_draftable_players(current_team.team_id)

    loop = asyncio.get_event_loop()
    recommendations = await loop.run_in_executor(
        None,
        partial(
            session.recommender.recommend_picks,
            state,
            available,
            WEB_RECOMMENDATIONS_COUNT,
            current_team.team_id,
        ),
    )

    return [recommendation_to_response(r) for r in recommendations]
