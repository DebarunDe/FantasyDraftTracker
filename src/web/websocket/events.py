"""Typed event builders for WebSocket server→client messages."""

from src.web.schemas import DraftSummaryResponse, PickResponse


def build_pick_made_event(pick: PickResponse, draft_state: DraftSummaryResponse) -> dict:
    return {
        "type": "pick_made",
        "pick": pick.model_dump(),
        "draft_state": {
            "current_pick": draft_state.current_pick,
            "current_round": draft_state.current_round,
            "current_team_id": draft_state.current_team_id,
            "is_complete": draft_state.is_complete,
            "completed_at": draft_state.completed_at,
            "all_picks": [p.model_dump() for p in draft_state.all_picks],
        },
    }


def build_computer_thinking_event(team_id: int, team_name: str, pick_number: int) -> dict:
    return {
        "type": "computer_thinking",
        "team_id": team_id,
        "team_name": team_name,
        "pick_number": pick_number,
    }


def build_draft_complete_event(summary: DraftSummaryResponse) -> dict:
    return {
        "type": "draft_complete",
        "summary": summary.model_dump(),
    }


def build_error_event(message: str) -> dict:
    return {"type": "error", "message": message}


def build_ping_event() -> dict:
    return {"type": "ping"}
