"""Pydantic request/response schemas for the Fantasy Draft Tracker web API."""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class PickTradeInput(BaseModel):
    from_team_id: int
    round: int
    to_team_id: int


class CreateDraftRequest(BaseModel):
    draft_mode: Literal["simulation", "manual_tracker"] = "simulation"
    league_size: int = 12
    scoring_format: Literal["standard", "half_ppr", "full_ppr"] = "half_ppr"
    roster_slots: Dict[str, int]
    team_names: List[str]
    human_team_id: int = 0
    data_year: int = 2025
    pick_trades: List[PickTradeInput] = []

    @field_validator("league_size")
    @classmethod
    def validate_league_size(cls, v: int) -> int:
        if v < 2 or v > 20 or v % 2 != 0:
            raise ValueError("league_size must be an even number between 2 and 20")
        return v


class MakePickRequest(BaseModel):
    team_id: int
    player_id: str


# ---------------------------------------------------------------------------
# Response bodies
# ---------------------------------------------------------------------------


class LeagueConfigResponse(BaseModel):
    league_id: str
    league_size: int
    scoring_format: str
    draft_type: str
    draft_mode: str
    data_year: int
    roster_slots: Dict[str, int]


class PickResponse(BaseModel):
    pick_number: int
    round: int
    team_id: int
    player_id: str
    player_name: str
    position: str
    nfl_team: str
    slot: Optional[str]
    timestamp: str
    # Reach/steal relative to overall_rank (pick_number - overall_rank)
    reach_delta: Optional[int] = None
    reach_label: str = ""  # "STEAL", "Value", "REACH", or ""


class TeamResponse(BaseModel):
    team_id: int
    team_name: str
    is_human: bool
    roster: Dict[str, List[str]]  # slot -> list of player_ids
    picks: List[str]  # ordered list of player_ids


class CurrentStateResponse(BaseModel):
    current_pick: int
    current_round: int
    current_team_id: int
    is_complete: bool
    completed_at: Optional[str] = None


class DraftSummaryResponse(BaseModel):
    draft_id: str
    league_config: LeagueConfigResponse
    draft_start_time: str
    current_pick: int
    current_round: int
    current_team_id: int
    is_complete: bool
    completed_at: Optional[str]
    draft_order: List[List[int]]
    pick_trades: List[Dict]
    teams: List[TeamResponse]
    all_picks: List[PickResponse]


class PlayerResponse(BaseModel):
    player_id: str
    name: str
    position: str
    nfl_team: str
    bye_week: Optional[int] = None
    projected_points: float
    baseline_vor: float
    overall_rank: Optional[int] = None


class RecommendationResponse(BaseModel):
    player_id: str
    player_name: str
    position: str
    nfl_team: str
    projected_points: float
    dynamic_vor: float
    base_vor: float
    rank: int
    reasoning: str
    tier: int
    is_tier_boundary: bool
    mc_expected_score: float
    mc_delta: float


class SavedDraftMeta(BaseModel):
    draft_id: str
    start_time: str
    is_complete: bool
    current_round: int
    current_pick: int
    league_size: int
    scoring_format: str


class RosterSlotResponse(BaseModel):
    slot: str
    players: List[PlayerResponse]


class ErrorResponse(BaseModel):
    detail: str
