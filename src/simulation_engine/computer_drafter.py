"""Computer drafter for AI opponents using ADP-blended composite scoring.

Design principle:
    Human recommendations use pure dynamic VOR (strategically optimal).
    Computer opponents use ADP-blended composite scoring so they behave like
    real fantasy drafters, making simulations more realistic and competitive.

Signal split:
    - VOR signal: dynamic VOR rank (1 = highest VOR among available players)
    - ADP signal: player['overall_rank'] (FantasyPros ECR, lower = better)

Both signals are normalized to [0, 1] via rank fusion before blending, so
neither dominates by magnitude (raw VOR ranges -100 to +200; overall_rank
is an integer 1-N).

Strategies:
    vor_only   — adp_weight=0.0 — pure VOR, mathematically optimal, RB-heavy
    balanced   — adp_weight=0.4 — 60% VOR + 40% ADP, realistic distributions
    consensus  — adp_weight=0.7 — 30% VOR + 70% ADP, follows expert consensus
    contrarian — adp_weight=0.0 + noise=0.15 — exploits ADP inefficiencies
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

import numpy as np

from src.simulation_engine.config import (
    ADP_BLEND_STRATEGIES,
    COMPUTER_ADP_WEIGHT,
)
from src.simulation_engine.models import VORResult

if TYPE_CHECKING:
    from src.draft_manager.draft_state import DraftState
    from src.simulation_engine.vor_calculator import DynamicVORCalculator


class ComputerDrafter:
    """Makes ADP-blended draft picks for AI teams.

    Uses rank fusion to combine dynamic VOR and ADP (overall_rank) signals.
    The adp_weight controls the blend: 0.0 = pure VOR, 1.0 = pure ADP.
    """

    def __init__(
        self,
        vor_calculator: DynamicVORCalculator,
        strategy: str = "balanced",
        adp_weight: Optional[float] = None,
    ) -> None:
        """
        Args:
            vor_calculator: Initialized DynamicVORCalculator to compute VOR ranks.
            strategy: One of "vor_only", "balanced", "consensus", "contrarian".
            adp_weight: Explicit blend weight; overrides the strategy default when
                        provided (0.0 = pure VOR, 1.0 = pure ADP).
        """
        if strategy not in ADP_BLEND_STRATEGIES and adp_weight is None:
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Valid options: {list(ADP_BLEND_STRATEGIES.keys())}"
            )
        self.vor_calculator = vor_calculator
        self.strategy = strategy
        # Explicit adp_weight overrides the strategy default
        if adp_weight is not None:
            self.adp_weight = adp_weight
        else:
            self.adp_weight = ADP_BLEND_STRATEGIES.get(strategy, COMPUTER_ADP_WEIGHT)
        # contrarian uses ±15% noise on top of pure VOR to exploit ADP inefficiencies
        self.noise_factor = 0.15 if strategy == "contrarian" else 0.0

    def make_pick(
        self,
        draft_state: DraftState,
        available_players: List[Dict],
        team_id: int,
    ) -> str:
        """Make a pick for a computer team using the configured strategy.

        Args:
            draft_state: Current DraftState (used by VOR calculator).
            available_players: List of available player dicts from DraftController.
            team_id: The team making the pick.

        Returns:
            player_id of the chosen pick.
        """
        if not available_players:
            raise ValueError("No available players to pick from")

        vor_results = self.vor_calculator.calculate_from_draft_state(
            draft_state, team_id
        )
        scores = self._compute_blended_scores(available_players, vor_results)

        if not scores:
            # Fallback: return first available player (should never happen)
            return available_players[0]["player_id"]

        return max(scores, key=scores.get)

    def _compute_blended_scores(
        self,
        available_players: List[Dict],
        vor_results: Dict[str, VORResult],
    ) -> Dict[str, float]:
        """Compute composite score for each available player.

        Uses rank fusion: both VOR and ADP are normalized to [0, 1] before
        blending so neither signal dominates by magnitude.

        Formula:
            vor_score  = 1 - (vor_rank - 1) / total_players   # 1.0 = best VOR
            adp_score  = 1 - (adp_rank - 1) / total_players   # 1.0 = best ADP
            composite  = (1 - adp_weight) * vor_score + adp_weight * adp_score

        For "contrarian" strategy, ±noise is added after blending.

        Returns:
            Dict mapping player_id → composite score (higher = better pick).
        """
        total = len(available_players)
        if total == 0:
            return {}

        # Build VOR rank: sort by dynamic_vor descending → rank 1 = best VOR
        vor_rank_map = self._rank_by_vor(vor_results)

        scores: Dict[str, float] = {}
        for player in available_players:
            pid = player["player_id"]

            vor_rank = vor_rank_map.get(pid, total)
            vor_score = 1.0 - (vor_rank - 1) / total

            # ADP signal: overall_rank (FantasyPros ECR, lower = better draft slot)
            # Fall back to total (worst rank) if field is missing or zero
            adp_rank = player.get("overall_rank") or total
            adp_score = 1.0 - (adp_rank - 1) / total

            composite = (
                (1.0 - self.adp_weight) * vor_score
                + self.adp_weight * adp_score
            )

            # contrarian: add uniform noise to exploit ADP inefficiencies
            if self.noise_factor > 0:
                noise = np.random.uniform(-self.noise_factor, self.noise_factor)
                composite = max(0.0, composite + noise)

            scores[pid] = composite

        return scores

    @staticmethod
    def _rank_by_vor(vor_results: Dict[str, VORResult]) -> Dict[str, int]:
        """Return a dict mapping player_id to 1-based VOR rank (1 = highest VOR)."""
        sorted_ids = sorted(
            vor_results.keys(),
            key=lambda pid: vor_results[pid].dynamic_vor,
            reverse=True,
        )
        return {pid: rank for rank, pid in enumerate(sorted_ids, start=1)}
