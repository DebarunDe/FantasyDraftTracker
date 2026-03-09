"""Data models for the simulation engine."""

from dataclasses import dataclass


@dataclass
class VORResult:
    """Result of dynamic VOR calculation for a single player."""

    player_id: str
    base_vor: float
    dynamic_vor: float
    scarcity_multiplier: float
    need_multiplier: float
    position: str
    position_rank: int  # Rank among available players at this position (1-based)
    tier: int = 0  # Tier within position (1 = top tier, 2 = second tier, etc.)
    is_tier_boundary: bool = False  # True if this is the last player in a tier
    uncertainty: float = 0.0  # Position uncertainty factor (0.0-1.0)


@dataclass
class Recommendation:
    """A single pick recommendation with reasoning for the human drafter."""

    player_id: str
    player_name: str
    position: str
    team: str
    projected_points: float
    dynamic_vor: float
    base_vor: float
    rank: int  # 1-based recommendation rank
    reasoning: str  # Human-readable explanation
    tier: int = 1
    is_tier_boundary: bool = False
    scarcity_multiplier: float = 1.0
    need_multiplier: float = 1.0
    # Monte Carlo fields (populated when MC simulator is active)
    mc_expected_score: float = 0.0  # Expected starting-lineup pts from simulations
    mc_delta: float = 0.0  # Expected pts advantage over the next-best MC pick
