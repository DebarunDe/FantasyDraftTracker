"""Dynamic VOR calculator that adjusts for draft state.

Builds on the static baseline VOR from the data pipeline by applying
positional scarcity and team roster need multipliers.
"""

import logging
from typing import Dict, List

from src.data_pipeline.config import VOR_BASELINE_COUNTS
from src.simulation_engine.config import POSITION_SCARCITY_WEIGHTS, ROSTER_NEED_WEIGHT
from src.simulation_engine.models import VORResult

logger = logging.getLogger(__name__)

FLEX_ELIGIBLE_POSITIONS = {"RB", "WR", "TE"}


class DynamicVORCalculator:
    """Calculate dynamic VOR based on current draft state.

    Adjusts each player's baseline VOR using two multipliers:

    * **Scarcity** — as more players at a position are drafted, remaining
      players at that position become more valuable.
    * **Roster need** — unfilled roster slots for a position boost VOR for
      that position on a per-team basis.

    The calculator is stateless: all data is passed in via method arguments.
    """

    def __init__(self, scoring_format: str):
        if scoring_format not in ("standard", "half_ppr", "full_ppr"):
            raise ValueError(
                f"Invalid scoring_format: {scoring_format!r}. "
                "Must be 'standard', 'half_ppr', or 'full_ppr'."
            )
        self.scoring_format = scoring_format

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_dynamic_vor(
        self,
        available_players: List[Dict],
        drafted_positions: Dict[str, int],
        roster_slots: Dict[str, int],
        team_roster: Dict[str, List],
    ) -> Dict[str, VORResult]:
        """Calculate dynamic VOR for all available players.

        Args:
            available_players: List of player dicts (from ``player_data``).
            drafted_positions: Number of players drafted at each position
                across the entire league, e.g. ``{"QB": 5, "RB": 18, ...}``.
            roster_slots: League roster slot counts,
                e.g. ``{"QB": 1, "RB": 2, ..., "FLEX": 1, "BENCH": 6}``.
            team_roster: Current team's roster mapping slot to list of
                player IDs, e.g. ``{"QB": ["qb1"], "RB": [], ...}``.

        Returns:
            Dict mapping ``player_id`` to :class:`VORResult`.
        """
        # Pre-compute position ranks among available players.
        position_ranks = self._compute_position_ranks(available_players)

        results: Dict[str, VORResult] = {}
        for player in available_players:
            player_id = player["player_id"]
            position = player["position"]

            base_vor = player.get("baseline_vor", {}).get(self.scoring_format, 0.0)

            scarcity = self._calculate_scarcity_multiplier(
                position,
                drafted_positions.get(position, 0),
            )

            need = self._calculate_need_multiplier(
                position,
                team_roster,
                roster_slots,
            )

            dynamic_vor = base_vor * scarcity * need

            results[player_id] = VORResult(
                player_id=player_id,
                base_vor=base_vor,
                dynamic_vor=dynamic_vor,
                scarcity_multiplier=scarcity,
                need_multiplier=need,
                position=position,
                position_rank=position_ranks.get(player_id, 0),
            )

        return results

    def calculate_from_draft_state(
        self,
        draft_state,
        team_id: int,
    ) -> Dict[str, VORResult]:
        """Convenience wrapper that extracts data from a DraftState.

        Args:
            draft_state: A :class:`DraftState` instance.
            team_id: The team to compute roster-need multipliers for.

        Returns:
            Dict mapping ``player_id`` to :class:`VORResult`.
        """
        available_players = [
            draft_state.get_player_info(pid)
            for pid in draft_state.available_players
        ]

        # Count drafted players by position across all teams.
        drafted_positions: Dict[str, int] = {}
        for team in draft_state.teams:
            for slot, player_ids in team.roster.items():
                if slot in ("FLEX", "BENCH"):
                    # Attribute FLEX/BENCH picks to their actual position.
                    for pid in player_ids:
                        player_info = draft_state.get_player_info(pid)
                        if not player_info or "position" not in player_info:
                            logger.warning(
                                "Could not determine position for player %s in %s slot",
                                pid, slot,
                            )
                            continue
                        drafted_positions[player_info["position"]] = (
                            drafted_positions.get(player_info["position"], 0) + 1
                        )
                else:
                    drafted_positions[slot] = (
                        drafted_positions.get(slot, 0) + len(player_ids)
                    )

        roster_slots = draft_state.league_config.roster_slots
        team_roster = draft_state.get_team(team_id).roster

        return self.calculate_dynamic_vor(
            available_players,
            drafted_positions,
            roster_slots,
            team_roster,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _calculate_scarcity_multiplier(
        self,
        position: str,
        drafted_count: int,
    ) -> float:
        """Scarcity multiplier based on league-wide drafted percentage.

        Formula::

            scarcity = 1 + (drafted_pct * position_weight)
            drafted_pct = drafted_count / total_startable

        When no players have been drafted the multiplier is 1.0.
        """
        total_startable = VOR_BASELINE_COUNTS.get(position, 1)
        drafted_pct = min(drafted_count / total_startable, 1.0)
        weight = POSITION_SCARCITY_WEIGHTS.get(position, 1.0)
        return 1.0 + (drafted_pct * weight)

    def _calculate_need_multiplier(
        self,
        position: str,
        team_roster: Dict[str, List],
        roster_slots: Dict[str, int],
    ) -> float:
        """Roster-need multiplier for a single team.

        Formula::

            need = 1 + (empty_slots / total_slots) * ROSTER_NEED_WEIGHT

        For FLEX-eligible positions (RB, WR, TE) the FLEX slot is included
        in both the filled and total counts.
        """
        filled, total = self._count_position_slots(position, team_roster, roster_slots)
        if total == 0:
            return 1.0
        empty = max(total - filled, 0)
        return 1.0 + (empty / total) * ROSTER_NEED_WEIGHT

    @staticmethod
    def _count_position_slots(
        position: str,
        team_roster: Dict[str, List],
        roster_slots: Dict[str, int],
    ) -> tuple:
        """Count filled and total slots for a position, including FLEX.

        Returns:
            ``(filled, total)`` tuple.
        """
        filled = len(team_roster.get(position, []))
        total = roster_slots.get(position, 0)

        if position in FLEX_ELIGIBLE_POSITIONS:
            filled += len(team_roster.get("FLEX", []))
            total += roster_slots.get("FLEX", 0)

        return filled, total

    def _compute_position_ranks(
        self,
        available_players: List[Dict],
    ) -> Dict[str, int]:
        """Rank available players within their position by baseline VOR.

        Returns:
            Dict mapping ``player_id`` to 1-based rank within position.
        """
        # Group by position.
        by_position: Dict[str, List[Dict]] = {}
        for player in available_players:
            pos = player["position"]
            by_position.setdefault(pos, []).append(player)

        ranks: Dict[str, int] = {}
        for pos, players in by_position.items():
            sorted_players = sorted(
                players,
                key=lambda p: p.get("baseline_vor", {}).get(self.scoring_format, 0.0),
                reverse=True,
            )
            for rank, p in enumerate(sorted_players, start=1):
                ranks[p["player_id"]] = rank

        return ranks
