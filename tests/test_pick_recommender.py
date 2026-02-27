"""Unit tests for Milestone 11: PickRecommender.

Tests cover:
  - recommend_picks() return type and count
  - Recommendations sorted by dynamic_vor descending
  - Reasoning strings are non-empty and meaningful
  - team_id defaults to current team on the clock
  - Explicit team_id override
  - Reasoning reflects roster need (empty vs filled positions)
  - Reasoning reflects tier boundary status
  - Reasoning reflects position scarcity
  - Edge cases: num_recommendations larger than available pool
  - Recommendation dataclass fields populated correctly
"""

from typing import Dict, List

import pytest

from src.draft_manager.draft_state import DraftState, LeagueConfig, TeamRoster
from src.simulation_engine.models import Recommendation
from src.simulation_engine.pick_recommender import PickRecommender
from src.simulation_engine.vor_calculator import DynamicVORCalculator


# ── Fixtures & helpers ────────────────────────────────────────────────

STANDARD_ROSTER = {
    "QB": 1, "RB": 2, "WR": 2, "TE": 1,
    "FLEX": 1, "DST": 1, "K": 1, "BENCH": 6,
}


def _make_player_pool(
    n_qb: int = 8,
    n_rb: int = 16,
    n_wr: int = 16,
    n_te: int = 8,
    n_k: int = 6,
    n_dst: int = 6,
) -> Dict[str, Dict]:
    """Synthetic player pool with realistic baseline_vor values."""
    players: Dict[str, Dict] = {}
    rank = 1
    for pos, count in [
        ("QB", n_qb), ("RB", n_rb), ("WR", n_wr),
        ("TE", n_te), ("K", n_k), ("DST", n_dst),
    ]:
        for i in range(1, count + 1):
            pid = f"{pos.lower()}{i}"
            players[pid] = {
                "player_id": pid,
                "name": f"{pos} Player {i}",
                "position": pos,
                "team": f"T{i % 32 + 1}",
                "overall_rank": rank,
                "bye_week": (i % 10) + 5,
                "projections": {
                    "standard": max(5.0, 300.0 - rank * 3),
                    "half_ppr": max(5.0, 320.0 - rank * 3),
                    "full_ppr": max(5.0, 340.0 - rank * 3),
                },
                "baseline_vor": {
                    "standard": max(-20.0, 100.0 - rank * 2),
                    "half_ppr": max(-20.0, 110.0 - rank * 2),
                    "full_ppr": max(-20.0, 120.0 - rank * 2),
                },
            }
            rank += 1
    return players


def _make_draft_state(
    league_size: int = 12,
    scoring_format: str = "half_ppr",
    current_pick: int = 1,
    current_round: int = 1,
    picks_made: int = 0,
    player_data: Dict = None,
) -> DraftState:
    """Build a minimal DraftState for testing."""
    if player_data is None:
        player_data = _make_player_pool()

    config = LeagueConfig(
        league_id="test",
        league_size=league_size,
        scoring_format=scoring_format,
        draft_type="snake",
        draft_mode="simulation",
        data_year=2025,
        roster_slots=dict(STANDARD_ROSTER),
    )
    team_names = [f"Team {i + 1}" for i in range(league_size)]
    state = DraftState.create_new(
        league_config=config,
        team_names=team_names,
        human_team_id=0,
        player_data=player_data,
    )
    # Override pick/round if caller specified
    state.current_pick = current_pick
    state.current_round = current_round
    return state


def _make_recommender(
    scoring_format: str = "half_ppr",
    league_size: int = 12,
) -> PickRecommender:
    vor_calc = DynamicVORCalculator(scoring_format, league_size=league_size)
    return PickRecommender(vor_calculator=vor_calc)


# ── TestRecommendPicksBasics ──────────────────────────────────────────

class TestRecommendPicksBasics:
    """Basic contract: return type, count, sorting."""

    def test_returns_list_of_recommendations(self):
        state = _make_draft_state()
        rec = _make_recommender()
        available = list(state.player_data.values())
        result = rec.recommend_picks(state, available, num_recommendations=5)
        assert isinstance(result, list)
        assert all(isinstance(r, Recommendation) for r in result)

    def test_returns_correct_count(self):
        state = _make_draft_state()
        rec = _make_recommender()
        available = list(state.player_data.values())
        result = rec.recommend_picks(state, available, num_recommendations=5)
        assert len(result) == 5

    def test_default_count_is_ten(self):
        state = _make_draft_state()
        rec = _make_recommender()
        available = list(state.player_data.values())
        result = rec.recommend_picks(state, available)
        assert len(result) == 10

    def test_sorted_by_dynamic_vor_descending(self):
        state = _make_draft_state()
        rec = _make_recommender()
        available = list(state.player_data.values())
        result = rec.recommend_picks(state, available, num_recommendations=10)
        vors = [r.dynamic_vor for r in result]
        assert vors == sorted(vors, reverse=True)

    def test_rank_is_sequential_one_based(self):
        state = _make_draft_state()
        rec = _make_recommender()
        available = list(state.player_data.values())
        result = rec.recommend_picks(state, available, num_recommendations=5)
        assert [r.rank for r in result] == [1, 2, 3, 4, 5]

    def test_num_recommendations_larger_than_pool_returns_all(self):
        player_data = _make_player_pool(n_qb=2, n_rb=2, n_wr=2, n_te=2, n_k=1, n_dst=1)
        state = _make_draft_state(player_data=player_data)
        rec = _make_recommender()
        available = list(state.player_data.values())
        result = rec.recommend_picks(state, available, num_recommendations=100)
        assert len(result) == len(available)


# ── TestRecommendationFields ──────────────────────────────────────────

class TestRecommendationFields:
    """Each Recommendation has all required fields populated."""

    def setup_method(self):
        self.state = _make_draft_state()
        self.rec = _make_recommender()
        available = list(self.state.player_data.values())
        self.results = self.rec.recommend_picks(self.state, available, num_recommendations=3)

    def test_player_id_is_string(self):
        for r in self.results:
            assert isinstance(r.player_id, str) and r.player_id

    def test_player_name_is_string(self):
        for r in self.results:
            assert isinstance(r.player_name, str) and r.player_name

    def test_position_is_valid(self):
        valid = {"QB", "RB", "WR", "TE", "K", "DST"}
        for r in self.results:
            assert r.position in valid

    def test_projected_points_is_positive(self):
        for r in self.results:
            assert r.projected_points > 0

    def test_dynamic_vor_is_float(self):
        for r in self.results:
            assert isinstance(r.dynamic_vor, float)

    def test_reasoning_is_non_empty_string(self):
        for r in self.results:
            assert isinstance(r.reasoning, str) and r.reasoning.strip()

    def test_tier_is_positive_int(self):
        for r in self.results:
            assert isinstance(r.tier, int) and r.tier >= 1


# ── TestTeamIdBehavior ────────────────────────────────────────────────

class TestTeamIdBehavior:
    """team_id defaults and overrides work correctly."""

    def test_defaults_to_current_team_id(self):
        state = _make_draft_state()
        # team on the clock is 0 (pick 1 of snake)
        assert state.current_team_id == 0
        rec = _make_recommender()
        available = list(state.player_data.values())
        # Should not raise
        result = rec.recommend_picks(state, available, num_recommendations=3)
        assert len(result) == 3

    def test_explicit_team_id_override(self):
        state = _make_draft_state()
        rec = _make_recommender()
        available = list(state.player_data.values())
        # Team 5 is not on the clock, but we can explicitly request recs for it
        result = rec.recommend_picks(state, available, num_recommendations=3, team_id=5)
        assert len(result) == 3
        assert all(isinstance(r, Recommendation) for r in result)


# ── TestReasoningContent ──────────────────────────────────────────────

class TestReasoningContent:
    """Reasoning strings reflect meaningful draft context."""

    def test_reasoning_non_empty_for_all_top10(self):
        state = _make_draft_state()
        rec = _make_recommender()
        available = list(state.player_data.values())
        results = rec.recommend_picks(state, available, num_recommendations=10)
        for r in results:
            assert r.reasoning.strip(), f"Empty reasoning for {r.player_name}"

    def test_empty_position_triggers_fills_slot_reasoning(self):
        """Team with no QB drafted → top QB recommendation mentions filling slot."""
        state = _make_draft_state()
        rec = _make_recommender()
        # Narrow available pool to just QBs so QB is recommended
        available = [p for p in state.player_data.values() if p["position"] == "QB"]
        results = rec.recommend_picks(state, available, num_recommendations=1)
        assert results, "Expected at least one recommendation"
        top = results[0]
        assert "QB" in top.reasoning or "slot" in top.reasoning.lower() or "empty" in top.reasoning.lower()

    def test_reasoning_uses_separator_when_multiple_clauses(self):
        """Multi-clause reasoning is joined with ' · '."""
        state = _make_draft_state()
        rec = _make_recommender()
        available = list(state.player_data.values())
        results = rec.recommend_picks(state, available, num_recommendations=10)
        multi_clause = [r for r in results if " · " in r.reasoning]
        # Not all will have two clauses, but at least some should with an empty roster
        assert len(multi_clause) >= 1

    def test_tier_boundary_mentioned_in_reasoning(self):
        """When a player is the last in their tier, reasoning notes the drop-off."""
        state = _make_draft_state()
        rec = _make_recommender()
        available = list(state.player_data.values())
        results = rec.recommend_picks(state, available, num_recommendations=20)
        boundary_recs = [r for r in results if r.is_tier_boundary]
        for r in boundary_recs:
            assert "tier" in r.reasoning.lower() or "drop" in r.reasoning.lower(), (
                f"Tier boundary not mentioned for {r.player_name}: '{r.reasoning}'"
            )


# ── TestAvailableFiltering ────────────────────────────────────────────

class TestAvailableFiltering:
    """Only players in available_players are recommended."""

    def test_only_available_players_recommended(self):
        state = _make_draft_state()
        rec = _make_recommender()
        # Pass only the first 5 players
        all_players = list(state.player_data.values())
        subset = all_players[:5]
        subset_ids = {p["player_id"] for p in subset}
        results = rec.recommend_picks(state, subset, num_recommendations=10)
        for r in results:
            assert r.player_id in subset_ids

    def test_player_not_in_available_excluded(self):
        state = _make_draft_state()
        rec = _make_recommender()
        all_players = list(state.player_data.values())
        # Exclude first player
        excluded_id = all_players[0]["player_id"]
        subset = all_players[1:]
        results = rec.recommend_picks(state, subset, num_recommendations=len(subset))
        assert all(r.player_id != excluded_id for r in results)


# ── TestScoringFormats ────────────────────────────────────────────────

class TestScoringFormats:
    """Recommender works correctly for all three scoring formats."""

    @pytest.mark.parametrize("scoring", ["standard", "half_ppr", "full_ppr"])
    def test_all_scoring_formats_return_valid_recommendations(self, scoring):
        state = _make_draft_state(scoring_format=scoring)
        vor_calc = DynamicVORCalculator(scoring, league_size=12)
        rec = PickRecommender(vor_calculator=vor_calc)
        available = list(state.player_data.values())
        results = rec.recommend_picks(state, available, num_recommendations=5)
        assert len(results) == 5
        for r in results:
            assert r.projected_points >= 0
            assert r.reasoning.strip()


# ── TestMcSimulatorStub ───────────────────────────────────────────────

class TestMcSimulatorStub:
    """mc_simulator=None is the default and works without error (M13 hook)."""

    def test_none_mc_simulator_accepted(self):
        vor_calc = DynamicVORCalculator("half_ppr", league_size=12)
        rec = PickRecommender(vor_calculator=vor_calc, mc_simulator=None)
        assert rec.mc_simulator is None

    def test_custom_object_stored_for_future_use(self):
        vor_calc = DynamicVORCalculator("half_ppr", league_size=12)
        stub = object()
        rec = PickRecommender(vor_calculator=vor_calc, mc_simulator=stub)
        assert rec.mc_simulator is stub
