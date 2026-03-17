"""Helpers to convert internal domain objects to Pydantic response schemas."""

from typing import Dict

from src.draft_manager.draft_state import DraftState
from src.simulation_engine.models import Recommendation
from src.ui.config import reach_label
from src.web.schemas import (
    CurrentStateResponse,
    DraftSummaryResponse,
    LeagueConfigResponse,
    PickResponse,
    PlayerResponse,
    RecommendationResponse,
    TeamResponse,
)


def draft_state_to_response(state: DraftState) -> DraftSummaryResponse:
    """Serialize a DraftState to a DraftSummaryResponse."""
    player_data: Dict = state.player_data

    picks = []
    for pick in state.all_picks:
        info = player_data.get(pick.player_id, {})
        overall_rank = info.get("overall_rank")
        delta = (pick.pick_number - overall_rank) if overall_rank else None
        picks.append(
            PickResponse(
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
                reach_label=reach_label(delta) if delta is not None else "",
            )
        )

    teams = [
        TeamResponse(
            team_id=t.team_id,
            team_name=t.team_name,
            is_human=t.is_human,
            roster=t.roster,
            picks=t.picks,
        )
        for t in state.teams
    ]

    lc = state.league_config
    return DraftSummaryResponse(
        draft_id=state.draft_id,
        league_config=LeagueConfigResponse(
            league_id=lc.league_id,
            league_size=lc.league_size,
            scoring_format=lc.scoring_format,
            draft_type=lc.draft_type,
            draft_mode=lc.draft_mode,
            data_year=lc.data_year,
            roster_slots=lc.roster_slots,
            pick_clock_seconds=lc.pick_clock_seconds,
        ),
        draft_start_time=state.draft_start_time,
        current_pick=state.current_pick,
        current_round=state.current_round,
        current_team_id=state.current_team_id,
        is_complete=state.is_complete,
        completed_at=state.completed_at,
        draft_order=state.draft_order,
        pick_trades=state.pick_trades,
        teams=teams,
        all_picks=picks,
    )


def current_state_response(state: DraftState) -> CurrentStateResponse:
    return CurrentStateResponse(
        current_pick=state.current_pick,
        current_round=state.current_round,
        current_team_id=state.current_team_id,
        is_complete=state.is_complete,
        completed_at=state.completed_at,
    )


def player_info_to_response(info: Dict, scoring_format: str) -> PlayerResponse:
    """Convert a player_data dict to a PlayerResponse."""
    bye = info.get("bye_week")
    try:
        bye = int(bye) if bye is not None else None
    except (TypeError, ValueError):
        bye = None

    vor_map = info.get("baseline_vor", {})
    vor = vor_map.get(scoring_format, 0.0) if isinstance(vor_map, dict) else 0.0

    proj_map = info.get("projections", {})
    pts = proj_map.get(scoring_format, 0.0) if isinstance(proj_map, dict) else 0.0

    return PlayerResponse(
        player_id=info.get("player_id", ""),
        name=info.get("name", ""),
        position=info.get("position", ""),
        nfl_team=info.get("team", ""),
        bye_week=bye,
        projected_points=float(pts),
        baseline_vor=float(vor),
        overall_rank=info.get("overall_rank"),
    )


def recommendation_to_response(rec: Recommendation) -> RecommendationResponse:
    return RecommendationResponse(
        player_id=rec.player_id,
        player_name=rec.player_name,
        position=rec.position,
        nfl_team=rec.team,
        projected_points=rec.projected_points,
        dynamic_vor=rec.dynamic_vor,
        base_vor=rec.base_vor,
        rank=rec.rank,
        reasoning=rec.reasoning,
        tier=rec.tier,
        is_tier_boundary=rec.is_tier_boundary,
        mc_expected_score=rec.mc_expected_score,
        mc_delta=rec.mc_delta,
    )
