"""Dynamic VOR calculator that adjusts for draft state.

Builds on the static baseline VOR from the data pipeline by applying
positional scarcity and team roster need multipliers.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from src.data_pipeline.config import calculate_baseline_count
from src.simulation_engine.config import (
    POSITION_SCARCITY_WEIGHTS,
    ROSTER_NEED_WEIGHT,
    ROSTER_FILLED_PENALTY,
    ROSTER_EXCESS_PENALTY,
    NEED_NORMALIZATION,
    POSITION_HARD_CAPS,
    POSITION_UNCERTAINTY,
    EARLY_ROUND_THRESHOLD,
    LATE_ROUND_THRESHOLD,
    TIER_GAP_THRESHOLD,
    TIER_URGENCY_WEIGHT,
)
from src.simulation_engine.models import VORResult

logger = logging.getLogger(__name__)

FLEX_ELIGIBLE_POSITIONS = {"RB", "WR", "TE"}


class DynamicVORCalculator:
    """Calculate dynamic VOR based on current draft state.

    Adjusts each player's baseline VOR using multiple factors:

    * **Scarcity** — as more players at a position are drafted, remaining
      players at that position become more valuable.
    * **Roster need** — unfilled starting slots boost VOR; filled starting
      slots penalize VOR to discourage drafting excess players at positions
      where the team is already stocked (especially K/DST).
    * **Uncertainty** — position-specific predictability (RBs have high variance,
      QBs/TEs are more consistent). Late rounds favor high-upside RBs.
    * **Tiers** — detect VOR gaps to identify tier boundaries within positions.

    The calculator is stateless: all data is passed in via method arguments.
    """

    def __init__(self, scoring_format: str, league_size: int = 12):
        if scoring_format not in ("standard", "half_ppr", "full_ppr"):
            raise ValueError(
                f"Invalid scoring_format: {scoring_format!r}. "
                "Must be 'standard', 'half_ppr', or 'full_ppr'."
            )
        self.scoring_format = scoring_format
        self.league_size = league_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_dynamic_vor(
        self,
        available_players: List[Dict],
        drafted_positions: Dict[str, int],
        roster_slots: Dict[str, int],
        team_roster: Dict[str, List],
        current_round: int = 1,
        player_positions: Optional[Dict[str, str]] = None,
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
            current_round: Current draft round (for uncertainty adjustments).
            player_positions: Optional mapping of player_id -> position for all
                players (drafted and available) to accurately count bench depth.

        Returns:
            Dict mapping ``player_id`` to :class:`VORResult`.
        """
        # Pre-compute position ranks and tiers among available players
        position_ranks = self._compute_position_ranks(available_players)
        position_tiers = self._detect_tiers(available_players)

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
                player_positions,
            )

            # Get tier information
            tier_info = position_tiers.get(position, {}).get(player_id, {})
            tier = tier_info.get("tier", 1)
            is_tier_boundary = tier_info.get("is_boundary", False)
            tier_gap = tier_info.get("tier_gap", 0.0)
            tier_size = max(1, tier_info.get("tier_size", 1))

            # Tier urgency boost: rewards unique elite players.
            # urgency = 1 + (gap_to_next_tier × (1/tier_size) × TIER_URGENCY_WEIGHT)
            # A player alone in their tier (Chase, Kittle) gets a large boost;
            # a player in a 12-member RB Tier 1 gets a tiny boost.
            tier_urgency = 1.0 + (tier_gap / tier_size) * TIER_URGENCY_WEIGHT

            # Apply uncertainty adjustment based on round
            uncertainty = POSITION_UNCERTAINTY.get(position, 0.5)
            uncertainty_adj = self._calculate_uncertainty_adjustment(
                uncertainty, current_round
            )

            # K/DST "streaming penalty" - if starting slot already filled, make bench K/DST worthless
            if position in ("K", "DST"):
                pos_filled = len(team_roster.get(position, []))
                if pos_filled >= roster_slots.get(position, 0):
                    dynamic_vor = -100.0
                else:
                    # Use draft completion percentage to ensure consistent behavior across league sizes
                    total_picks = sum(roster_slots.values()) * self.league_size
                    picks_made_approx = (current_round - 1) * self.league_size + (self.league_size // 2)
                    draft_pct_complete = picks_made_approx / total_picks if total_picks > 0 else 0.0

                    if draft_pct_complete < 0.65:
                        dynamic_vor = -50.0
                    elif draft_pct_complete < 0.80:
                        dynamic_vor = -5.0
                    else:
                        position_value_penalty = 0.50
                        dynamic_vor = base_vor * scarcity * need * uncertainty_adj * position_value_penalty
            else:
                # Skill positions: dynamic_vor = base_vor * scarcity * need * uncertainty * tier_urgency
                dynamic_vor = base_vor * scarcity * need * uncertainty_adj * tier_urgency

                # Hard cap: apply position-specific max total players
                filled = self._count_position_slots(
                    position, team_roster, roster_slots, player_positions
                )[0]
                hard_cap = POSITION_HARD_CAPS.get(position)
                if hard_cap is not None and filled >= hard_cap:
                    dynamic_vor = -100.0

            results[player_id] = VORResult(
                player_id=player_id,
                base_vor=base_vor,
                dynamic_vor=dynamic_vor,
                scarcity_multiplier=scarcity,
                need_multiplier=need,
                position=position,
                position_rank=position_ranks.get(player_id, 0),
                tier=tier,
                is_tier_boundary=is_tier_boundary,
                uncertainty=uncertainty,
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
        # Also build mapping of player_id -> position for bench depth calculation.
        drafted_positions: Dict[str, int] = {}
        player_positions: Dict[str, str] = {}

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
                        position = player_info["position"]
                        player_positions[pid] = position
                        drafted_positions[position] = (
                            drafted_positions.get(position, 0) + 1
                        )
                else:
                    # Position-specific slot (QB, RB, WR, TE, K, DST)
                    for pid in player_ids:
                        player_positions[pid] = slot
                    drafted_positions[slot] = (
                        drafted_positions.get(slot, 0) + len(player_ids)
                    )

        roster_slots = draft_state.league_config.roster_slots
        team_roster = draft_state.get_team(team_id).roster
        current_round = draft_state.current_round

        return self.calculate_dynamic_vor(
            available_players,
            drafted_positions,
            roster_slots,
            team_roster,
            current_round,
            player_positions,
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

        Formula for skill positions (QB, RB, WR, TE)::

            scarcity = 1 + (drafted_pct * position_weight)
            drafted_pct = drafted_count / total_startable

        Formula for K/DST (INVERSE scarcity - decreases as more drafted)::

            scarcity = 1 - (drafted_pct * position_weight)

        K/DST are interchangeable, so their value DROPS as league fills positions.
        When no players have been drafted the multiplier is 1.0 for all positions.
        """
        total_startable = calculate_baseline_count(position, self.league_size)
        drafted_pct = min(drafted_count / total_startable, 1.0)
        weight = POSITION_SCARCITY_WEIGHTS.get(position, 1.0)

        # K/DST use inverse scarcity (value drops as more drafted)
        if position in ("K", "DST"):
            return max(1.0 - (drafted_pct * weight), 0.1)
        else:
            # Skill positions use normal scarcity (value rises as more drafted)
            return 1.0 + (drafted_pct * weight)

    def _calculate_need_multiplier(
        self,
        position: str,
        team_roster: Dict[str, List],
        roster_slots: Dict[str, int],
        player_positions: Optional[Dict[str, str]] = None,
    ) -> float:
        """Roster-need multiplier for a single team.

        Three-tier formula:

        1. **Empty starting slots**: boost VOR to prioritize filling starters.
           ``need = 1 + (empty / total) * ROSTER_NEED_WEIGHT``

        2. **All starters filled**: penalize to discourage bench-only picks.
           ``need = 1 - ROSTER_FILLED_PENALTY``

        3. **Excess beyond starters**: further penalize each extra player.
           ``need = 1 - ROSTER_FILLED_PENALTY - (excess * ROSTER_EXCESS_PENALTY)``

        For FLEX-eligible positions (RB, WR, TE) the FLEX slot is included
        in both the filled and total counts. Bench players of this position
        are counted as "filled" to trigger the excess penalty.
        """
        filled, total = self._count_position_slots(
            position, team_roster, roster_slots, player_positions
        )

        if total == 0:
            # No slots for this position at all — heavy penalty
            # K/DST get no floor (can go to 0), others floor at 0.05
            min_need = 0.0 if position in ("K", "DST") else 0.05
            return max(1.0 - ROSTER_FILLED_PENALTY, min_need)

        empty = total - filled

        if empty > 0:
            # Boost scales by absolute empty slots, normalized by max starting slots.
            # QB (1 empty slot) gets smaller boost than RB/WR (3 empty slots),
            # which naturally pushes QBs into later rounds vs elite RBs/WRs.
            return 1.0 + (empty * ROSTER_NEED_WEIGHT / NEED_NORMALIZATION)

        # All starting slots filled — penalize
        excess = abs(empty)  # How many beyond starting capacity

        # K/DST get much steeper excess penalty to strongly discourage hoarding
        if position in ("K", "DST"):
            # First bench K/DST: 0.4 penalty (need = 0.6)
            # Second bench: +0.50 more (need = 0.1)
            # Third bench: +0.50 more (need = -0.4, floors at 0.0)
            excess_penalty = excess * 0.50
        else:
            # Skill positions: progressive penalty that escalates with hoarding
            # Prevents teams from drafting excessive depth at one position
            # Tier 1 (excess 1-2): 0.15 per player - reasonable bench depth (3-4 total)
            # Tier 2 (excess 3):   0.40 penalty - getting excessive (5-6 total)
            # Hard cap at excess >= 4 is applied in calculate_dynamic_vor
            excess_penalty = 0.0
            for i in range(excess):
                if i < 2:  # First 2 excess players
                    excess_penalty += ROSTER_EXCESS_PENALTY
                else:  # 3rd+ excess players (2.67× steeper)
                    excess_penalty += ROSTER_EXCESS_PENALTY * 2.67

        penalty = ROSTER_FILLED_PENALTY + excess_penalty

        # K/DST get no floor (can go to 0 or negative), skill positions floor at 0.01
        # Lower floor (0.01 vs 0.05) allows stronger discouragement of excessive hoarding
        min_need = 0.0 if position in ("K", "DST") else 0.01
        return max(1.0 - penalty, min_need)

    @staticmethod
    def _count_position_slots(
        position: str,
        team_roster: Dict[str, List],
        roster_slots: Dict[str, int],
        player_positions: Optional[Dict[str, str]] = None,
    ) -> tuple:
        """Count filled and total slots for a position, including FLEX and BENCH.

        Args:
            position: Position to count (e.g., "QB", "RB").
            team_roster: Current team's roster mapping slot to list of player IDs.
            roster_slots: League roster slot counts.
            player_positions: Optional mapping of player_id -> position for looking up
                positions of players in FLEX and BENCH slots. If not provided, only
                counts players in position-specific slots.

        Returns:
            ``(filled, total)`` tuple where:
            - total = starting slots for this position (pos-specific + FLEX if eligible)
            - filled = count of players at this position across all slots (starting + bench)
        """
        # Count players in position-specific slot
        filled = len(team_roster.get(position, []))
        total = roster_slots.get(position, 0)

        # Add FLEX slot to total for FLEX-eligible positions
        if position in FLEX_ELIGIBLE_POSITIONS:
            total += roster_slots.get("FLEX", 0)

        # If we have player position data, count FLEX and BENCH players of this position
        if player_positions:
            # Count this position in FLEX slot
            for player_id in team_roster.get("FLEX", []):
                if player_positions.get(player_id) == position:
                    filled += 1

            # Count this position in BENCH slot (these become "excess")
            for player_id in team_roster.get("BENCH", []):
                if player_positions.get(player_id) == position:
                    filled += 1
        else:
            # Fallback: just count all FLEX players (assumes all are of this position)
            if position in FLEX_ELIGIBLE_POSITIONS:
                filled += len(team_roster.get("FLEX", []))

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

    def _detect_tiers(
        self,
        available_players: List[Dict],
    ) -> Dict[str, Dict[str, Dict]]:
        """Detect tier boundaries within each position.

        A tier boundary occurs when VOR drops by >TIER_GAP_THRESHOLD between
        adjacent players. Each player record stores:
        - ``tier``: 1-based tier number
        - ``is_boundary``: True if this is the last player in their tier
        - ``tier_gap``: % VOR drop to the next tier (only set on boundary players)
        - ``tier_size``: how many players share this tier (filled in post-pass)

        Returns:
            Dict mapping position -> player_id -> tier metadata dict.
        """
        by_position: Dict[str, List[Dict]] = {}
        for player in available_players:
            pos = player["position"]
            by_position.setdefault(pos, []).append(player)

        tiers: Dict[str, Dict[str, Dict]] = {}
        for pos, players in by_position.items():
            sorted_players = sorted(
                players,
                key=lambda p: p.get("baseline_vor", {}).get(self.scoring_format, 0.0),
                reverse=True,
            )

            pos_tiers: Dict[str, Dict] = {}
            current_tier = 1

            for i, player in enumerate(sorted_players):
                player_id = player["player_id"]
                current_vor = player.get("baseline_vor", {}).get(self.scoring_format, 0.0)

                is_boundary = False
                tier_gap = 0.0
                if i < len(sorted_players) - 1:
                    next_vor = sorted_players[i + 1].get(
                        "baseline_vor", {}
                    ).get(self.scoring_format, 0.0)
                    if current_vor > 0:
                        drop = (current_vor - next_vor) / current_vor
                        if drop > TIER_GAP_THRESHOLD:
                            is_boundary = True
                            tier_gap = drop

                pos_tiers[player_id] = {
                    "tier": current_tier,
                    "is_boundary": is_boundary,
                    "tier_gap": tier_gap,
                    "tier_size": 0,  # filled in below
                }

                if is_boundary:
                    current_tier += 1

            # Second pass: count tier sizes and propagate tier_gap to all
            # members of the same tier so every player knows the gap at the
            # end of their tier.
            tier_members: Dict[int, List[str]] = defaultdict(list)
            tier_gap_by_num: Dict[int, float] = {}
            for pid, info in pos_tiers.items():
                tier_members[info["tier"]].append(pid)
                if info["is_boundary"]:
                    tier_gap_by_num[info["tier"]] = info["tier_gap"]

            for tier_num, member_ids in tier_members.items():
                size = len(member_ids)
                gap = tier_gap_by_num.get(tier_num, 0.0)
                for pid in member_ids:
                    pos_tiers[pid]["tier_size"] = size
                    pos_tiers[pid]["tier_gap"] = gap

            tiers[pos] = pos_tiers

        return tiers

    def _calculate_uncertainty_adjustment(
        self,
        uncertainty: float,
        current_round: int,
    ) -> float:
        """Calculate VOR adjustment based on position uncertainty and draft round.

        Early rounds (1-3): Penalize uncertainty (favor consistent QBs/TEs)
        Mid rounds (4-9): No adjustment
        Late rounds (10+): Reward uncertainty (favor high-upside RBs)

        Args:
            uncertainty: Position uncertainty factor (0.0-1.0).
            current_round: Current draft round.

        Returns:
            Multiplier to apply to VOR (typically 0.8-1.2).
        """
        if current_round <= EARLY_ROUND_THRESHOLD:
            # Early: penalize uncertainty (prefer safe picks)
            return 1.0 - (uncertainty * 0.2)
        elif current_round >= LATE_ROUND_THRESHOLD:
            # Late: reward uncertainty (prefer upside)
            return 1.0 + (uncertainty * 0.15)
        else:
            # Mid-rounds: no adjustment
            return 1.0
