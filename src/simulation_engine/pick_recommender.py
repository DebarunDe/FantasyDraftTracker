"""Pick recommender for human draft users.

Builds on dynamic VOR to produce a ranked list of :class:`Recommendation`
objects, each with a plain-English explanation of why the player is valuable
given the current draft context.
"""

import logging
from typing import Dict, List, Optional

from src.simulation_engine.models import Recommendation, VORResult
from src.simulation_engine.vor_calculator import DynamicVORCalculator

logger = logging.getLogger(__name__)

# Positions that can fill a FLEX roster slot
FLEX_ELIGIBLE = {"RB", "WR", "TE"}

# Minimum picks a player must have slipped past their ADP to show "value" signal
_ADP_SLIP_THRESHOLD = 12


class PickRecommender:
    """Generate ranked pick recommendations for the human drafter.

    Uses :class:`DynamicVORCalculator` as the primary signal.  A Monte Carlo
    simulator (M13) can be injected later; when ``mc_simulator`` is ``None``
    the class falls back to pure VOR ranking.

    All methods are stateless — draft state is passed in on every call.
    """

    def __init__(
        self,
        vor_calculator: DynamicVORCalculator,
        mc_simulator=None,
    ) -> None:
        self.vor_calculator = vor_calculator
        self.mc_simulator = mc_simulator  # Reserved for M13 Monte Carlo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend_picks(
        self,
        draft_state,
        available_players: List[Dict],
        num_recommendations: int = 10,
        team_id: Optional[int] = None,
    ) -> List[Recommendation]:
        """Return the top ``num_recommendations`` picks for *team_id*.

        Args:
            draft_state: Current :class:`~src.draft_manager.draft_state.DraftState`.
            available_players: List of player dicts (already legal for this pick).
            num_recommendations: How many recommendations to return.
            team_id: Team to generate recs for.  Defaults to the team currently
                on the clock (``draft_state.current_team_id``).

        Returns:
            List of :class:`Recommendation` sorted best-first.
        """
        if team_id is None:
            team_id = draft_state.current_team_id

        vor_results = self.vor_calculator.calculate_from_draft_state(
            draft_state, team_id
        )

        available_ids = {p["player_id"] for p in available_players}
        all_sorted = sorted(
            [v for v in vor_results.values() if v.player_id in available_ids],
            key=lambda v: v.dynamic_vor,
            reverse=True,
        )
        top_n = all_sorted[:num_recommendations]

        # Rank within each position by dynamic VOR so clause 1 always matches
        # the recommendation order (not base-VOR order which can differ).
        pos_counter: Dict[str, int] = {}
        dvor_pos_rank: Dict[str, int] = {}
        for v in all_sorted:  # already sorted dVOR desc
            pos = v.position
            pos_counter[pos] = pos_counter.get(pos, 0) + 1
            dvor_pos_rank[v.player_id] = pos_counter[pos]

        team = draft_state.get_team(team_id)
        roster_slots = draft_state.league_config.roster_slots
        drafted_positions = self._get_drafted_positions(draft_state)
        picks_made = len(draft_state.all_picks)
        scoring = self.vor_calculator.scoring_format

        recommendations: List[Recommendation] = []
        for rank, vor_result in enumerate(top_n, 1):
            player = draft_state.player_data.get(vor_result.player_id, {})
            proj = player.get("projections", {}).get(scoring, 0.0)
            pos_rank = dvor_pos_rank.get(vor_result.player_id, vor_result.position_rank)
            reasoning = self._generate_reasoning(
                vor_result,
                player,
                team,
                roster_slots,
                drafted_positions,
                draft_state.current_round,
                draft_state.player_data,
                picks_made=picks_made,
                dvor_position_rank=pos_rank,
            )
            recommendations.append(
                Recommendation(
                    player_id=vor_result.player_id,
                    player_name=player.get("name", "Unknown"),
                    position=vor_result.position,
                    team=player.get("team", "?"),
                    projected_points=proj,
                    dynamic_vor=vor_result.dynamic_vor,
                    base_vor=vor_result.base_vor,
                    rank=rank,
                    reasoning=reasoning,
                    tier=vor_result.tier,
                    is_tier_boundary=vor_result.is_tier_boundary,
                    scarcity_multiplier=vor_result.scarcity_multiplier,
                    need_multiplier=vor_result.need_multiplier,
                )
            )

        return recommendations

    # ------------------------------------------------------------------
    # Reasoning generation
    # ------------------------------------------------------------------

    def _generate_reasoning(
        self,
        vor_result: VORResult,
        player: Dict,
        team,
        roster_slots: Dict[str, int],
        drafted_positions: Dict[str, int],
        current_round: int,
        player_data: Dict,
        picks_made: int = 0,
        dvor_position_rank: int = 0,
    ) -> str:
        """Build a short, plain-English explanation for the recommendation.

        Returns at most two clauses joined by " · " so the output stays
        readable in a terminal table.
        """
        pos = vor_result.position
        clauses: List[str] = []

        team_count = self._count_team_at_position(team, pos, player_data)
        starting_slots = self._get_starting_slots(pos, roster_slots)

        # Effective position rank: prefer dynamic-VOR-based rank passed in from
        # recommend_picks (which matches the recommendation order) over the
        # base-VOR rank stored on VORResult.
        pos_rank = dvor_position_rank if dvor_position_rank > 0 else vor_result.position_rank

        # ── 1. Position rank by dynamic VOR — always the primary signal ───
        if pos_rank == 1:
            clauses.append(f"Best available {pos}")
        else:
            clauses.append(f"#{pos_rank} available {pos}")

        # ── 2. Contextual second clause ──────────────────────────────────
        # Priority: team need > ADP value slip > tier boundary > scarcity
        #           > late upside > bench depth
        overall_rank = player.get("overall_rank", 999)
        adp_slip = picks_made - overall_rank  # positive → player slipped past ADP

        if team_count == 0:
            clauses.append(f"Fills empty {pos} slot")

        elif 0 < team_count < starting_slots:
            clauses.append(f"Needed {pos} depth")

        elif adp_slip >= _ADP_SLIP_THRESHOLD and vor_result.base_vor > 0:
            # Still above replacement value but went later than consensus
            clauses.append(f"Value: fell {adp_slip} picks past ADP")

        elif vor_result.is_tier_boundary:
            clauses.append("Tier drop-off ahead")

        elif vor_result.scarcity_multiplier >= 1.2:
            league_drafted = drafted_positions.get(pos, 0)
            clauses.append(f"{pos} scarce ({league_drafted} drafted)")

        elif current_round >= 10 and vor_result.uncertainty >= 0.8 and pos_rank <= 2:
            # High-upside signal: only shown for the top 2 at a position so it
            # doesn't fill every row when the board is dominated by one position.
            clauses.append("High-upside late target")

        elif team_count >= starting_slots:
            clauses.append("Bench depth pick")

        return " · ".join(clauses[:2])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_drafted_positions(self, draft_state) -> Dict[str, int]:
        """Count how many players have been drafted at each position league-wide."""
        counts: Dict[str, int] = {}
        for pick in draft_state.all_picks:
            player = draft_state.player_data.get(pick.player_id, {})
            pos = player.get("position", "")
            if pos:
                counts[pos] = counts.get(pos, 0) + 1
        return counts

    def _count_team_at_position(
        self, team, position: str, player_data: Dict
    ) -> int:
        """Return how many players the team has drafted at *position*."""
        count = 0
        for pid in team.picks:
            if player_data.get(pid, {}).get("position") == position:
                count += 1
        return count

    def _get_starting_slots(self, position: str, roster_slots: Dict[str, int]) -> int:
        """Return how many starting slots exist for *position* (incl. FLEX)."""
        slots = roster_slots.get(position, 0)
        if position in FLEX_ELIGIBLE:
            slots += roster_slots.get("FLEX", 0)
        return slots
