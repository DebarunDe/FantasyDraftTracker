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
