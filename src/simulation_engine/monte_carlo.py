"""Monte Carlo simulator for draft pick evaluation.

Runs lightweight forward simulations of the remaining draft to estimate the
expected team projected points for each candidate pick.  This produces better
recommendations than pure VOR because it accounts for *positional scarcity
pressure*: a player who is the only top-tier option at their position (and will
be gone before your next pick) scores higher in MC than in static VOR even if
their point projections are similar to an alternative.

Algorithm
---------
For each candidate player (top N by VOR):
    1. Assign the candidate to the human team at the current pick.
    2. Simulate the next D rounds of the draft:
        - Computer teams pick by ADP (``overall_rank``), respecting hard caps.
        - Human team fills remaining picks greedily by dynamic VOR.
    3. Score the human team's optimal starting lineup at simulation end.
    4. Average scores across N simulations → expected team value.

The candidate with the highest average expected team value is recommended.

Key design decisions
---------------------
- **Lightweight state**: pure Python dicts; no DraftState copies per simulation.
- **Pre-computed VOR**: computed once per ``evaluate_candidates`` call, shared
  across all simulations (valid approximation for depth-limited sims).
- **Pre-sorted player lists**: VOR-sorted and ADP-sorted lists built once.
- **Adaptive depth**: 5 rounds early, 3 mid, 2 late (see SIMULATION_DEPTH_BY_ROUND).
- **Hard caps**: POSITION_HARD_CAPS enforced to prevent position hoarding.
- **Stateless**: all data passed as parameters; no instance-level mutable state.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from src.simulation_engine.config import (
    CANDIDATE_POOL_SIZE,
    MC_NUM_SIMULATIONS,
    POSITION_HARD_CAPS,
    SIMULATION_DEPTH_BY_ROUND,
)

if TYPE_CHECKING:
    from src.draft_manager.draft_state import DraftState
    from src.simulation_engine.models import VORResult
    from src.simulation_engine.vor_calculator import DynamicVORCalculator

logger = logging.getLogger(__name__)

# Positions eligible for the FLEX roster slot.
FLEX_ELIGIBLE = frozenset({"RB", "WR", "TE"})


class MonteCarloSimulator:
    """Evaluate draft picks using forward Monte Carlo simulation.

    Computer teams draft by ADP; the human team fills remaining rounds
    by pre-computed dynamic VOR.  All methods are stateless — draft state
    is passed in on every call.

    Args:
        vor_calculator: Initialized :class:`DynamicVORCalculator`.
        scoring_format: One of ``"standard"``, ``"half_ppr"``, ``"full_ppr"``.
        league_size: Number of teams in the league (default 12).
    """

    def __init__(
        self,
        vor_calculator: "DynamicVORCalculator",
        scoring_format: str,
        league_size: int = 12,
    ) -> None:
        self.vor_calculator = vor_calculator
        self.scoring_format = scoring_format
        self.league_size = league_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_candidates(
        self,
        draft_state: "DraftState",
        candidates: List[Dict],
        num_simulations: Optional[int] = None,
    ) -> Dict[str, float]:
        """Estimate expected team starting-lineup score for each candidate pick.

        Args:
            draft_state: Current DraftState.
            candidates: Player dicts to evaluate (typically top N by VOR).
            num_simulations: Simulations per candidate.  Defaults to
                ``MC_NUM_SIMULATIONS`` from config.

        Returns:
            Dict mapping ``player_id`` → mean expected starting-lineup
            projected points over all simulations.
        """
        n = num_simulations if num_simulations is not None else MC_NUM_SIMULATIONS
        depth = self._get_simulation_depth(draft_state.current_round)
        my_team_id = draft_state.current_team_id
        player_data = draft_state.player_data

        # Pre-compute VOR results once; shared as the human's greedy oracle.
        vor_results = self.vor_calculator.calculate_from_draft_state(
            draft_state, my_team_id
        )

        available_ids: set = set(draft_state.available_players)

        # Pre-sorted pick lists for the simulation inner loop.
        vor_sorted = self._build_vor_sorted(available_ids, vor_results)
        adp_sorted = self._build_adp_sorted(available_ids, player_data)

        # Existing position counts per team (from real rosters).
        team_pos_counts = self._extract_team_pos_counts(draft_state)

        # Existing human-team picks with positions (included in scoring).
        my_team = draft_state.get_team(my_team_id)
        existing_my_picks: List[Tuple[str, str]] = [
            (pid, player_data.get(pid, {}).get("position", ""))
            for pid in my_team.picks
            if player_data.get(pid, {}).get("position", "")
        ]

        expected_values: Dict[str, float] = {}
        for candidate in candidates:
            cid = candidate["player_id"]
            if cid not in available_ids:
                continue

            total = 0.0
            for _ in range(n):
                total += self._simulate_single(
                    candidate_id=cid,
                    my_team_id=my_team_id,
                    current_pick=draft_state.current_pick,
                    draft_order=draft_state.draft_order,
                    league_size=draft_state.league_config.league_size,
                    roster_slots=draft_state.league_config.roster_slots,
                    original_available=available_ids,
                    vor_sorted=vor_sorted,
                    adp_sorted=adp_sorted,
                    base_team_pos_counts=team_pos_counts,
                    player_data=player_data,
                    existing_my_picks=existing_my_picks,
                    depth=depth,
                )
            expected_values[cid] = total / n
            logger.debug(
                "MC: candidate %s → %.1f avg pts",
                candidate.get("name", cid),
                expected_values[cid],
            )

        return expected_values

    # ------------------------------------------------------------------
    # Simulation internals
    # ------------------------------------------------------------------

    def _simulate_single(
        self,
        *,
        candidate_id: str,
        my_team_id: int,
        current_pick: int,
        draft_order: List[int],
        league_size: int,
        roster_slots: Dict[str, int],
        original_available: set,
        vor_sorted: List[Tuple[str, str]],
        adp_sorted: List[Tuple[str, str]],
        base_team_pos_counts: Dict[int, Dict[str, int]],
        player_data: Dict[str, Dict],
        existing_my_picks: List[Tuple[str, str]],
        depth: int,
    ) -> float:
        """Run one Monte Carlo simulation.

        Returns the human team's expected starting-lineup projected points.
        The candidate player is always picked first; subsequent picks are
        made greedily (VOR for human, ADP for computer teams).
        """
        # Shallow copy of mutable state — no DraftState copies needed.
        available: set = original_available - {candidate_id}

        # Per-team position counts (copy so simulations are independent).
        team_pos_counts: Dict[int, Dict[str, int]] = {
            tid: dict(counts) for tid, counts in base_team_pos_counts.items()
        }

        # Build human team's picks list, seeded with existing + candidate.
        my_picks: List[Tuple[str, str]] = list(existing_my_picks)
        cand_pos = player_data.get(candidate_id, {}).get("position", "")
        if cand_pos:
            my_picks.append((candidate_id, cand_pos))
            team_pos_counts[my_team_id][cand_pos] = (
                team_pos_counts[my_team_id].get(cand_pos, 0) + 1
            )

        # Simulate picks for the next `depth` rounds.
        start_pick = current_pick + 1
        end_pick = start_pick + depth * league_size - 1

        for pick_num in range(start_pick, end_pick + 1):
            if not available:
                break

            team_id = _get_team_for_pick(pick_num, league_size, draft_order)
            pos_counts = team_pos_counts[team_id]

            if team_id == my_team_id:
                chosen = _pick_by_vor(available, vor_sorted, pos_counts)
            else:
                chosen = _pick_by_adp(available, adp_sorted, pos_counts)

            if chosen is None:
                break

            chosen_pos = player_data.get(chosen, {}).get("position", "")
            available.discard(chosen)
            if chosen_pos:
                pos_counts[chosen_pos] = pos_counts.get(chosen_pos, 0) + 1
            if team_id == my_team_id and chosen_pos:
                my_picks.append((chosen, chosen_pos))

        return _score_team(my_picks, player_data, self.scoring_format, roster_slots)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_simulation_depth(self, current_round: int) -> int:
        """Return simulation depth (rounds ahead) based on current round."""
        if current_round <= 3:
            return SIMULATION_DEPTH_BY_ROUND["early"]
        elif current_round <= 9:
            return SIMULATION_DEPTH_BY_ROUND["mid"]
        return SIMULATION_DEPTH_BY_ROUND["late"]

    @staticmethod
    def _build_vor_sorted(
        available_ids: set,
        vor_results: Dict[str, "VORResult"],
    ) -> List[Tuple[str, str]]:
        """Build (player_id, position) list sorted by VOR desc.

        Used as the greedy oracle for human-team picks in simulation.
        Players not in ``vor_results`` are excluded.
        """
        sorted_ids = sorted(
            (pid for pid in available_ids if pid in vor_results),
            key=lambda pid: vor_results[pid].dynamic_vor,
            reverse=True,
        )
        return [(pid, vor_results[pid].position) for pid in sorted_ids]

    @staticmethod
    def _build_adp_sorted(
        available_ids: set,
        player_data: Dict[str, Dict],
    ) -> List[Tuple[str, str]]:
        """Build (player_id, position) list sorted by ADP asc.

        ``overall_rank`` (FantasyPros ECR) is the ADP signal.  Players with
        no rank sort last.  Used for computer-team greedy picks in simulation.
        """
        sorted_ids = sorted(
            available_ids,
            key=lambda pid: player_data.get(pid, {}).get("overall_rank") or 9999,
        )
        return [
            (pid, player_data.get(pid, {}).get("position", ""))
            for pid in sorted_ids
        ]

    @staticmethod
    def _extract_team_pos_counts(
        draft_state: "DraftState",
    ) -> Dict[int, Dict[str, int]]:
        """Extract current position counts per team from the real draft state.

        Used to initialise each simulation's mutable position-count state.
        """
        result: Dict[int, Dict[str, int]] = {}
        for team in draft_state.teams:
            counts: Dict[str, int] = defaultdict(int)
            for pid in team.picks:
                pos = draft_state.player_data.get(pid, {}).get("position", "")
                if pos:
                    counts[pos] += 1
            result[team.team_id] = dict(counts)
        return result


# ------------------------------------------------------------------
# Module-level pure functions (used inside the hot simulation loop)
# ------------------------------------------------------------------

def _get_team_for_pick(
    pick_num: int,
    league_size: int,
    draft_order: List[int],
) -> int:
    """Return team_id for *pick_num* in a snake draft.

    Picks are 1-indexed.  Rounds alternate direction: odd rounds go
    left-to-right, even rounds go right-to-left in draft_order.
    """
    pick_0 = pick_num - 1
    round_num = pick_0 // league_size + 1
    pos_in_round = pick_0 % league_size
    if round_num % 2 == 1:  # odd round → ascending
        team_index = pos_in_round
    else:  # even round → descending
        team_index = league_size - 1 - pos_in_round
    return draft_order[team_index]


def _pick_by_vor(
    available: set,
    vor_sorted: List[Tuple[str, str]],
    pos_counts: Dict[str, int],
) -> Optional[str]:
    """Return the highest-VOR available player that respects hard caps."""
    for pid, pos in vor_sorted:
        if pid in available:
            cap = POSITION_HARD_CAPS.get(pos, 999)
            if pos_counts.get(pos, 0) < cap:
                return pid
    return None


def _pick_by_adp(
    available: set,
    adp_sorted: List[Tuple[str, str]],
    pos_counts: Dict[str, int],
) -> Optional[str]:
    """Return the highest-ADP (lowest overall_rank) available player that respects hard caps."""
    for pid, pos in adp_sorted:
        if pid in available:
            cap = POSITION_HARD_CAPS.get(pos, 999)
            if pos_counts.get(pos, 0) < cap:
                return pid
    return None


def _score_team(
    picks: List[Tuple[str, str]],
    player_data: Dict[str, Dict],
    scoring_format: str,
    roster_slots: Dict[str, int],
) -> float:
    """Sum projected points for the optimal starting lineup from *picks*.

    Fills dedicated position slots (QB, RB, WR, TE, K, DST) first, then
    fills FLEX with the highest remaining FLEX-eligible (RB/WR/TE) players.
    BENCH picks do not contribute to the score.

    Args:
        picks: List of ``(player_id, position)`` tuples (existing + simulated).
        player_data: Full player data snapshot.
        scoring_format: Scoring format key for ``projections``.
        roster_slots: Slot configuration, e.g. ``{"QB": 1, "RB": 2, ...}``.

    Returns:
        Total projected points for the best starting lineup.
    """
    if not picks:
        return 0.0

    # Group projected points by position (desc sorted for starter selection).
    by_position: Dict[str, List[float]] = defaultdict(list)
    for pid, pos in picks:
        pts = player_data.get(pid, {}).get("projections", {}).get(scoring_format, 0.0)
        by_position[pos].append(pts)

    for pos in by_position:
        by_position[pos].sort(reverse=True)

    total = 0.0
    used: Dict[str, int] = defaultdict(int)

    # Fill dedicated position slots.
    for slot in ("QB", "RB", "WR", "TE", "K", "DST"):
        n_slots = roster_slots.get(slot, 0)
        pts_list = by_position.get(slot, [])
        take = min(n_slots, len(pts_list))
        total += sum(pts_list[:take])
        used[slot] = take

    # Fill FLEX with best remaining FLEX-eligible players.
    flex_slots = roster_slots.get("FLEX", 0)
    if flex_slots > 0:
        flex_candidates: List[float] = []
        for pos in FLEX_ELIGIBLE:
            pts_list = by_position.get(pos, [])
            flex_candidates.extend(pts_list[used[pos]:])
        flex_candidates.sort(reverse=True)
        total += sum(flex_candidates[:flex_slots])

    return total
