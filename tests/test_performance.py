"""Milestone 14: Performance benchmark tests.

All four latency targets from the M14 spec must pass on the CI machine:

| Operation                        | Target  |
|----------------------------------|---------|
| Pick validation                  | < 10 ms |
| VOR calculation (full pool)      | <100 ms |
| Simple recommendation (no MC)   | <500 ms |
| Monte Carlo recommendation       | < 2 s   |

Tests use real 2025 player data (654 players) so timings reflect production
workloads.  Timing is measured with ``time.perf_counter`` around the hot path
only — fixture setup is excluded from every measurement.
"""

import time

import pytest

from src.draft_manager.draft_controller import DraftController
from src.draft_manager.draft_initializer import DraftInitializer
from src.draft_manager.draft_rules import DraftRules
from src.simulation_engine.monte_carlo import MonteCarloSimulator
from src.simulation_engine.pick_recommender import PickRecommender
from src.simulation_engine.vor_calculator import DynamicVORCalculator

# Standard 14-slot roster used across all benchmarks
STANDARD_ROSTER = {
    "QB": 1, "RB": 2, "WR": 2, "TE": 1,
    "FLEX": 1, "DST": 1, "K": 1, "BENCH": 6,
}


# ── Shared fixtures ────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def draft_state_round1():
    """12-team half-PPR draft at pick 1 (round 1) with real 2025 data."""
    initializer = DraftInitializer()
    return initializer.create_draft(
        league_size=12,
        scoring_format="half_ppr",
        roster_slots=STANDARD_ROSTER,
        team_names=[f"Team {i}" for i in range(12)],
        human_team_id=0,
        data_year=2025,
    )


@pytest.fixture(scope="module")
def draft_state_round10(draft_state_round1):
    """Same draft advanced to round 10 by making 108 greedy picks."""
    # Work on a fresh draft so round-1 fixture stays unmodified for other tests.
    initializer = DraftInitializer()
    state = initializer.create_draft(
        league_size=12,
        scoring_format="half_ppr",
        roster_slots=STANDARD_ROSTER,
        team_names=[f"Team {i}" for i in range(12)],
        human_team_id=0,
        data_year=2025,
    )
    controller = DraftController(state)
    # Advance through 9 complete rounds (108 picks) to reach round 10.
    for _ in range(108):
        if state.is_complete:
            break
        team_id = state.current_team_id
        draftable = controller.get_draftable_players(team_id)
        if draftable:
            controller.make_pick(team_id, draftable[0]["player_id"])
    return state


@pytest.fixture(scope="module")
def vor_calc():
    return DynamicVORCalculator(scoring_format="half_ppr", league_size=12)


@pytest.fixture(scope="module")
def mc_sim(vor_calc):
    return MonteCarloSimulator(
        vor_calculator=vor_calc, scoring_format="half_ppr", league_size=12
    )


# ── M14 Benchmark: Pick validation < 10 ms ────────────────────────────


class TestPickValidationPerformance:
    """Pick validation must complete in <10 ms (target from M14 spec)."""

    def test_valid_pick_under_10ms(self, draft_state_round1):
        player_id = draft_state_round1.available_players[0]
        rules = DraftRules(draft_state_round1)

        start = time.perf_counter()
        is_valid, _ = rules.validate_pick(0, player_id)
        elapsed = time.perf_counter() - start

        assert is_valid
        assert elapsed < 0.010, (
            f"Pick validation took {elapsed * 1000:.1f} ms — target <10 ms"
        )

    def test_invalid_pick_under_10ms(self, draft_state_round1):
        """Rejection path (wrong team turn) must also be fast."""
        player_id = draft_state_round1.available_players[0]
        rules = DraftRules(draft_state_round1)

        start = time.perf_counter()
        is_valid, _ = rules.validate_pick(11, player_id)  # wrong team
        elapsed = time.perf_counter() - start

        assert not is_valid
        assert elapsed < 0.010, (
            f"Invalid-pick rejection took {elapsed * 1000:.1f} ms — target <10 ms"
        )


# ── M14 Benchmark: VOR calculation < 100 ms ───────────────────────────


class TestVORCalculationPerformance:
    """Full dynamic VOR recalculation must complete in <100 ms."""

    def test_vor_full_pool_round1_under_100ms(self, draft_state_round1, vor_calc):
        start = time.perf_counter()
        results = vor_calc.calculate_from_draft_state(draft_state_round1, team_id=0)
        elapsed = time.perf_counter() - start

        assert len(results) > 0
        assert elapsed < 0.100, (
            f"VOR (round 1, full pool) took {elapsed * 1000:.1f} ms — target <100 ms"
        )

    def test_vor_reduced_pool_round10_under_100ms(self, draft_state_round10, vor_calc):
        """Late-round VOR (smaller pool) must also meet target."""
        start = time.perf_counter()
        results = vor_calc.calculate_from_draft_state(draft_state_round10, team_id=0)
        elapsed = time.perf_counter() - start

        assert len(results) > 0
        assert elapsed < 0.100, (
            f"VOR (round 10, reduced pool) took {elapsed * 1000:.1f} ms — target <100 ms"
        )


# ── M14 Benchmark: Simple recommendation (no MC) < 500 ms ─────────────


class TestSimpleRecommendationPerformance:
    """PickRecommender without MC must complete in <500 ms."""

    def test_simple_rec_round1_under_500ms(self, draft_state_round1, vor_calc):
        recommender = PickRecommender(vor_calculator=vor_calc, mc_simulator=None)
        available = [
            draft_state_round1.get_player_info(pid)
            for pid in draft_state_round1.available_players
        ]

        start = time.perf_counter()
        recs = recommender.recommend_picks(
            draft_state=draft_state_round1,
            available_players=available,
            num_recommendations=10,
        )
        elapsed = time.perf_counter() - start

        assert len(recs) > 0
        assert elapsed < 0.500, (
            f"Simple recommendation took {elapsed * 1000:.1f} ms — target <500 ms"
        )

    def test_simple_rec_round10_under_500ms(self, draft_state_round10, vor_calc):
        recommender = PickRecommender(vor_calculator=vor_calc, mc_simulator=None)
        available = [
            draft_state_round10.get_player_info(pid)
            for pid in draft_state_round10.available_players
        ]

        start = time.perf_counter()
        recs = recommender.recommend_picks(
            draft_state=draft_state_round10,
            available_players=available,
            num_recommendations=10,
        )
        elapsed = time.perf_counter() - start

        assert len(recs) > 0
        assert elapsed < 0.500, (
            f"Simple recommendation (round 10) took {elapsed * 1000:.1f} ms — target <500 ms"
        )


# ── M14 Benchmark: Monte Carlo recommendation < 2 s ───────────────────


class TestMonteCarloPerformance:
    """Full MC recommendation (200 sims × 15 candidates) must complete in <2 s."""

    def test_mc_rec_round1_under_2s(self, draft_state_round1, vor_calc, mc_sim):
        recommender = PickRecommender(vor_calculator=vor_calc, mc_simulator=mc_sim)
        available = [
            draft_state_round1.get_player_info(pid)
            for pid in draft_state_round1.available_players
        ]

        start = time.perf_counter()
        recs = recommender.recommend_picks(
            draft_state=draft_state_round1,
            available_players=available,
            num_recommendations=5,
        )
        elapsed = time.perf_counter() - start

        assert len(recs) > 0
        assert elapsed < 2.0, (
            f"MC recommendation (round 1) took {elapsed:.2f} s — target <2.0 s"
        )

    def test_mc_rec_round10_under_2s(self, draft_state_round10, vor_calc, mc_sim):
        """Late-round MC uses shorter depth (2 rounds) so must be well under target."""
        recommender = PickRecommender(vor_calculator=vor_calc, mc_simulator=mc_sim)
        available = [
            draft_state_round10.get_player_info(pid)
            for pid in draft_state_round10.available_players
        ]

        start = time.perf_counter()
        recs = recommender.recommend_picks(
            draft_state=draft_state_round10,
            available_players=available,
            num_recommendations=5,
        )
        elapsed = time.perf_counter() - start

        assert len(recs) > 0
        assert elapsed < 2.0, (
            f"MC recommendation (round 10) took {elapsed:.2f} s — target <2.0 s"
        )
