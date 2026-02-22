"""Tests for ComputerDrafter — Milestone 9: ADP-blended AI opponent."""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from typing import Dict, List

from src.simulation_engine.computer_drafter import ComputerDrafter
from src.simulation_engine.models import VORResult
from src.simulation_engine.config import ADP_BLEND_STRATEGIES, COMPUTER_ADP_WEIGHT
from src.simulation_engine.vor_calculator import DynamicVORCalculator


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_player(
    player_id: str,
    position: str,
    overall_rank: int = 50,
    vor_half_ppr: float = 30.0,
) -> Dict:
    """Build a minimal player dict matching the pipeline JSON format."""
    return {
        "player_id": player_id,
        "name": f"Player {player_id.upper()}",
        "position": position,
        "team": "TEST",
        "overall_rank": overall_rank,
        "projections": {"standard": 100.0, "half_ppr": 120.0, "full_ppr": 140.0},
        "baseline_vor": {
            "standard": vor_half_ppr - 5,
            "half_ppr": vor_half_ppr,
            "full_ppr": vor_half_ppr + 5,
        },
    }


def _make_vor_result(
    player_id: str,
    position: str,
    dynamic_vor: float,
    base_vor: float = None,
) -> VORResult:
    """Build a VORResult with the given dynamic_vor."""
    return VORResult(
        player_id=player_id,
        base_vor=base_vor if base_vor is not None else dynamic_vor,
        dynamic_vor=dynamic_vor,
        scarcity_multiplier=1.0,
        need_multiplier=1.0,
        position=position,
        position_rank=1,
    )


def _make_vor_calculator(scoring_format: str = "half_ppr", league_size: int = 12):
    """Return a real DynamicVORCalculator."""
    return DynamicVORCalculator(scoring_format=scoring_format, league_size=league_size)


def _make_drafter(strategy: str = "balanced") -> ComputerDrafter:
    """Return a ComputerDrafter with a real VOR calculator."""
    vor_calc = _make_vor_calculator()
    return ComputerDrafter(vor_calculator=vor_calc, strategy=strategy)


# ── Init & strategy validation ─────────────────────────────────────────────────


class TestComputerDrafterInit:
    def test_balanced_strategy_sets_correct_adp_weight(self):
        drafter = _make_drafter("balanced")
        assert drafter.adp_weight == ADP_BLEND_STRATEGIES["balanced"]
        assert drafter.adp_weight == 0.4

    def test_vor_only_strategy_zero_adp_weight_no_noise(self):
        drafter = _make_drafter("vor_only")
        assert drafter.adp_weight == 0.0
        assert drafter.noise_factor == 0.0

    def test_consensus_strategy_adp_weight(self):
        drafter = _make_drafter("consensus")
        assert drafter.adp_weight == ADP_BLEND_STRATEGIES["consensus"]
        assert drafter.adp_weight == 0.7

    def test_contrarian_strategy_zero_adp_weight_with_noise(self):
        drafter = _make_drafter("contrarian")
        assert drafter.adp_weight == 0.0
        assert drafter.noise_factor == 0.15

    def test_explicit_adp_weight_overrides_strategy(self):
        vor_calc = _make_vor_calculator()
        drafter = ComputerDrafter(
            vor_calculator=vor_calc, strategy="balanced", adp_weight=0.9
        )
        assert drafter.adp_weight == 0.9

    def test_explicit_adp_weight_zero_overrides_strategy(self):
        vor_calc = _make_vor_calculator()
        drafter = ComputerDrafter(
            vor_calculator=vor_calc, strategy="consensus", adp_weight=0.0
        )
        assert drafter.adp_weight == 0.0

    def test_unknown_strategy_without_explicit_weight_raises(self):
        vor_calc = _make_vor_calculator()
        with pytest.raises(ValueError, match="Unknown strategy"):
            ComputerDrafter(vor_calculator=vor_calc, strategy="superstar")

    def test_unknown_strategy_with_explicit_adp_weight_is_allowed(self):
        vor_calc = _make_vor_calculator()
        drafter = ComputerDrafter(
            vor_calculator=vor_calc, strategy="custom", adp_weight=0.3
        )
        assert drafter.adp_weight == 0.3

    def test_strategy_stored(self):
        drafter = _make_drafter("consensus")
        assert drafter.strategy == "consensus"


# ── _rank_by_vor ───────────────────────────────────────────────────────────────


class TestRankByVOR:
    def test_highest_vor_gets_rank_1(self):
        vor_results = {
            "a": _make_vor_result("a", "RB", dynamic_vor=100.0),
            "b": _make_vor_result("b", "WR", dynamic_vor=50.0),
            "c": _make_vor_result("c", "QB", dynamic_vor=75.0),
        }
        ranks = ComputerDrafter._rank_by_vor(vor_results)
        assert ranks["a"] == 1
        assert ranks["c"] == 2
        assert ranks["b"] == 3

    def test_single_player_rank_1(self):
        vor_results = {"x": _make_vor_result("x", "TE", dynamic_vor=30.0)}
        ranks = ComputerDrafter._rank_by_vor(vor_results)
        assert ranks["x"] == 1

    def test_negative_vor_still_ranked(self):
        vor_results = {
            "a": _make_vor_result("a", "K", dynamic_vor=-50.0),
            "b": _make_vor_result("b", "DST", dynamic_vor=-100.0),
        }
        ranks = ComputerDrafter._rank_by_vor(vor_results)
        assert ranks["a"] == 1
        assert ranks["b"] == 2

    def test_empty_vor_results_returns_empty(self):
        assert ComputerDrafter._rank_by_vor({}) == {}


# ── _compute_blended_scores ────────────────────────────────────────────────────


class TestComputeBlendedScores:
    def test_returns_score_for_every_available_player(self):
        drafter = _make_drafter("balanced")
        players = [_make_player("a", "RB", overall_rank=1), _make_player("b", "WR", overall_rank=2)]
        vor_results = {
            "a": _make_vor_result("a", "RB", dynamic_vor=80.0),
            "b": _make_vor_result("b", "WR", dynamic_vor=40.0),
        }
        scores = drafter._compute_blended_scores(players, vor_results)
        assert set(scores.keys()) == {"a", "b"}

    def test_empty_players_returns_empty_dict(self):
        drafter = _make_drafter("balanced")
        scores = drafter._compute_blended_scores([], {})
        assert scores == {}

    def test_all_scores_between_0_and_1(self):
        """All composite scores are in [0, 1] for a typical pool."""
        drafter = _make_drafter("balanced")
        players = [
            _make_player("a", "RB", overall_rank=1),
            _make_player("b", "WR", overall_rank=2),
            _make_player("c", "QB", overall_rank=3),
        ]
        vor_results = {
            "a": _make_vor_result("a", "RB", dynamic_vor=90.0),
            "b": _make_vor_result("b", "WR", dynamic_vor=60.0),
            "c": _make_vor_result("c", "QB", dynamic_vor=30.0),
        }
        scores = drafter._compute_blended_scores(players, vor_results)
        for pid, score in scores.items():
            assert 0.0 <= score <= 1.0, f"{pid} score {score} out of [0, 1]"

    def test_scores_always_in_0_1_regardless_of_global_rank(self):
        """Scores stay in [0, 1] even when overall_rank far exceeds the pool size.

        ADP is re-ranked within the available pool, so a player with global ECR
        200 in a 2-player pool gets adp_rank=2 (not 200), keeping adp_score in
        [0, 1].  Ordering is preserved: the lower global ECR wins.
        """
        drafter = _make_drafter("balanced")
        players = [
            _make_player("a", "RB", overall_rank=1),
            _make_player("b", "WR", overall_rank=200),  # high global ECR
        ]
        vor_results = {
            "a": _make_vor_result("a", "RB", dynamic_vor=90.0),
            "b": _make_vor_result("b", "WR", dynamic_vor=50.0),
        }
        scores = drafter._compute_blended_scores(players, vor_results)
        for pid, score in scores.items():
            assert 0.0 <= score <= 1.0, f"{pid} score {score} out of [0, 1]"
        assert scores["a"] > scores["b"]

    def test_best_vor_and_best_adp_player_wins_balanced(self):
        """Player dominant on both signals should score highest."""
        drafter = _make_drafter("balanced")
        players = [
            _make_player("dominant", "RB", overall_rank=1),
            _make_player("weak", "WR", overall_rank=10),
        ]
        vor_results = {
            "dominant": _make_vor_result("dominant", "RB", dynamic_vor=100.0),
            "weak": _make_vor_result("weak", "WR", dynamic_vor=10.0),
        }
        scores = drafter._compute_blended_scores(players, vor_results)
        assert scores["dominant"] > scores["weak"]

    def test_adp_blend_raises_score_of_top_adp_player(self):
        """balanced (adp_weight=0.4) should lift a player with great ADP vs pure VOR.

        We compare the balanced composite score of the top-ADP/weak-VOR player
        against its score under pure VOR.  Blending must increase it relative to
        pure VOR scoring.
        """
        vor_calc = _make_vor_calculator()
        balanced = ComputerDrafter(vor_calculator=vor_calc, strategy="balanced")
        vor_only = ComputerDrafter(vor_calculator=vor_calc, strategy="vor_only")

        # Use 10 players so rank differences are small (0.1 apart) and in-range
        players = [_make_player(f"p{i}", "RB", overall_rank=i) for i in range(1, 11)]
        # Player p10 has worst VOR (rank 10) but best ADP (rank 1) among 10 players
        players[-1]["overall_rank"] = 1    # p10 → #1 ADP
        players[0]["overall_rank"] = 10    # p1  → #10 ADP (worst)
        vor_results = {
            f"p{i}": _make_vor_result(f"p{i}", "RB", dynamic_vor=float(11 - i) * 10)
            for i in range(1, 11)
        }  # p1 has highest VOR (100), p10 has lowest (10)

        balanced_scores = balanced._compute_blended_scores(players, vor_results)
        vor_scores = vor_only._compute_blended_scores(players, vor_results)

        # p10 has worst VOR rank but best ADP — balanced should give it a higher
        # relative score than pure VOR
        assert balanced_scores["p10"] > vor_scores["p10"]

    def test_vor_only_strategy_ignores_adp(self):
        """adp_weight=0.0 means composite equals VOR score only."""
        drafter = _make_drafter("vor_only")
        players = [
            _make_player("a", "WR", overall_rank=1),   # great ADP, poor VOR
            _make_player("b", "RB", overall_rank=200),  # bad ADP, great VOR
        ]
        vor_results = {
            "a": _make_vor_result("a", "WR", dynamic_vor=5.0),
            "b": _make_vor_result("b", "RB", dynamic_vor=90.0),
        }
        scores = drafter._compute_blended_scores(players, vor_results)
        # With pure VOR, b must win despite awful ADP
        assert scores["b"] > scores["a"]

    def test_missing_overall_rank_falls_back_to_last(self):
        """Players without overall_rank are treated as worst ADP rank (total)."""
        drafter = _make_drafter("balanced")
        player = _make_player("x", "QB", overall_rank=1)
        player.pop("overall_rank")  # remove the field entirely

        vor_results = {"x": _make_vor_result("x", "QB", dynamic_vor=40.0)}
        scores = drafter._compute_blended_scores([player], vor_results)
        # Must not raise, and score should be a valid float
        assert isinstance(scores["x"], float)

    def test_overall_rank_zero_falls_back_to_last(self):
        """overall_rank=0 is falsy; should fall back to total (worst ADP)."""
        drafter = _make_drafter("balanced")
        player = _make_player("x", "QB")
        player["overall_rank"] = 0

        vor_results = {"x": _make_vor_result("x", "QB", dynamic_vor=40.0)}
        scores = drafter._compute_blended_scores([player], vor_results)
        assert isinstance(scores["x"], float)

    def test_player_missing_from_vor_results_uses_worst_vor_rank(self):
        """Player not in vor_results gets rank=total (worst VOR)."""
        drafter = _make_drafter("vor_only")
        players = [
            _make_player("known", "RB", overall_rank=1),
            _make_player("unknown", "WR", overall_rank=2),
        ]
        vor_results = {
            "known": _make_vor_result("known", "RB", dynamic_vor=80.0),
            # "unknown" deliberately absent
        }
        scores = drafter._compute_blended_scores(players, vor_results)
        assert scores["known"] > scores["unknown"]

    def test_contrarian_adds_noise(self):
        """contrarian strategy introduces non-zero variance across runs."""
        np.random.seed(42)
        drafter = _make_drafter("contrarian")
        players = [_make_player("a", "RB", overall_rank=1, vor_half_ppr=50.0)]
        vor_results = {"a": _make_vor_result("a", "RB", dynamic_vor=50.0)}

        run1 = drafter._compute_blended_scores(players, vor_results)["a"]
        run2 = drafter._compute_blended_scores(players, vor_results)["a"]
        # With a fresh random stream the two values will usually differ
        # (probability of exact equality is negligible)
        # We just verify that noise_factor is active by checking the score
        # can deviate from the no-noise baseline
        no_noise_drafter = _make_drafter("vor_only")
        baseline = no_noise_drafter._compute_blended_scores(players, vor_results)["a"]
        # At least one of the contrarian scores should differ from the pure VOR baseline
        assert run1 != baseline or run2 != baseline

    def test_contrarian_score_never_negative(self):
        """contrarian clips composite to 0.0 floor."""
        np.random.seed(99)
        drafter = _make_drafter("contrarian")
        # Force worst-ranked player so base score is near 0
        players = [_make_player("z", "DST", overall_rank=654)]
        vor_results = {"z": _make_vor_result("z", "DST", dynamic_vor=-50.0)}

        for _ in range(50):
            scores = drafter._compute_blended_scores(players, vor_results)
            assert scores["z"] >= 0.0


# ── make_pick ──────────────────────────────────────────────────────────────────


class TestMakePick:
    """Integration tests using a mocked VOR calculator for speed."""

    def _build_drafter_with_mock_vor(self, strategy: str, vor_map: Dict[str, float]):
        """Create a ComputerDrafter whose VOR calculator always returns vor_map."""
        vor_calc = MagicMock()
        vor_results = {
            pid: _make_vor_result(pid, "RB", dynamic_vor=v)
            for pid, v in vor_map.items()
        }
        vor_calc.calculate_from_draft_state.return_value = vor_results
        drafter = ComputerDrafter(vor_calculator=vor_calc, strategy=strategy)
        return drafter

    def test_make_pick_returns_valid_player_id(self):
        vor_map = {"p1": 80.0, "p2": 50.0, "p3": 30.0}
        drafter = self._build_drafter_with_mock_vor("balanced", vor_map)
        players = [
            _make_player("p1", "RB", overall_rank=1),
            _make_player("p2", "WR", overall_rank=2),
            _make_player("p3", "QB", overall_rank=3),
        ]
        draft_state = MagicMock()
        pick = drafter.make_pick(draft_state, players, team_id=0)
        assert pick in {"p1", "p2", "p3"}

    def test_vor_only_picks_highest_vor_player(self):
        """vor_only with adp_weight=0 always picks the top VOR player."""
        vor_map = {"rb1": 100.0, "wr1": 40.0, "qb1": 20.0}
        drafter = self._build_drafter_with_mock_vor("vor_only", vor_map)
        players = [
            _make_player("rb1", "RB", overall_rank=50),  # poor ADP
            _make_player("wr1", "WR", overall_rank=1),   # great ADP
            _make_player("qb1", "QB", overall_rank=2),   # great ADP
        ]
        draft_state = MagicMock()
        pick = drafter.make_pick(draft_state, players, team_id=0)
        assert pick == "rb1"  # VOR dominates, ADP ignored

    def test_consensus_heavily_favors_adp(self):
        """consensus (adp_weight=0.7) should pick the top ADP player when VOR is weaker."""
        # Player A: middling VOR but #1 ADP rank
        # Player B: top VOR but #50 ADP rank (out of 2 players → terrible ADP score)
        vor_map = {"a": 40.0, "b": 80.0}
        drafter = self._build_drafter_with_mock_vor("consensus", vor_map)
        players = [
            _make_player("a", "WR", overall_rank=1),
            _make_player("b", "RB", overall_rank=2),
        ]
        draft_state = MagicMock()
        pick = drafter.make_pick(draft_state, players, team_id=0)
        # With only 2 players, adp_score gap is 0.5; vor_score gap is 0.5
        # consensus: 0.3*vor + 0.7*adp — player A wins via ADP
        assert pick == "a"

    def test_all_strategies_return_valid_player_id(self):
        vor_map = {"p1": 80.0, "p2": 60.0, "p3": 20.0}
        players = [
            _make_player("p1", "RB", overall_rank=1),
            _make_player("p2", "WR", overall_rank=2),
            _make_player("p3", "QB", overall_rank=3),
        ]
        available_ids = {p["player_id"] for p in players}
        draft_state = MagicMock()

        for strategy in ["vor_only", "balanced", "consensus", "contrarian"]:
            drafter = self._build_drafter_with_mock_vor(strategy, vor_map)
            pick = drafter.make_pick(draft_state, players, team_id=0)
            assert pick in available_ids, f"Strategy '{strategy}' returned invalid pick: {pick}"

    def test_empty_available_players_raises(self):
        drafter = self._build_drafter_with_mock_vor("balanced", {})
        draft_state = MagicMock()
        with pytest.raises(ValueError, match="No available players"):
            drafter.make_pick(draft_state, [], team_id=0)

    def test_contrarian_varies_across_runs(self):
        """contrarian strategy produces different picks due to noise (statistical).

        Use 10 players so rank differences are small (~0.11) and easily overcome
        by noise=0.15; the same setup is deterministic for vor_only.
        """
        np.random.seed(0)
        # 10 players with nearly equal VOR — rank gap between adjacent players is 1/10 = 0.1
        vor_map = {f"p{i}": 50.0 + i * 0.01 for i in range(1, 11)}
        players = [_make_player(f"p{i}", "RB", overall_rank=i) for i in range(1, 11)]
        draft_state = MagicMock()
        drafter = self._build_drafter_with_mock_vor("contrarian", vor_map)

        picks = {drafter.make_pick(draft_state, players, team_id=0) for _ in range(50)}
        # Noise of ±0.15 easily swamps the ~0.01 VOR rank gap → multiple winners expected
        assert len(picks) >= 2


# ── Integration with real DraftState (full pipeline) ─────────────────────────


class TestMakePickWithRealDraftState:
    """Smoke tests using real player data from the processed pipeline JSON."""

    @pytest.fixture
    def draft_state(self):
        """Load a minimal real draft state from the processed JSON."""
        from src.draft_manager.draft_initializer import DraftInitializer

        initializer = DraftInitializer()
        state = initializer.create_draft(
            league_size=12,
            scoring_format="half_ppr",
            roster_slots={
                "QB": 1, "RB": 2, "WR": 2, "TE": 1,
                "FLEX": 1, "DST": 1, "K": 1, "BENCH": 6,
            },
            team_names=[f"Team {i+1}" for i in range(12)],
            human_team_id=0,
        )
        return state

    def test_all_strategies_return_valid_player_id(self, draft_state):
        from src.draft_manager.draft_controller import DraftController

        controller = DraftController(draft_state)
        available = controller.get_available_players()
        available_ids = {p["player_id"] for p in available}

        for strategy in ["vor_only", "balanced", "consensus", "contrarian"]:
            vor_calc = DynamicVORCalculator("half_ppr", league_size=12)
            drafter = ComputerDrafter(vor_calculator=vor_calc, strategy=strategy)
            pick = drafter.make_pick(draft_state, available, team_id=0)
            assert pick in available_ids, (
                f"Strategy '{strategy}' returned invalid pick: {pick}"
            )

    def test_balanced_drafter_picks_a_reasonable_player(self, draft_state):
        """Balanced drafter's first pick should be a top-tier skill player, not K/DST."""
        from src.draft_manager.draft_controller import DraftController

        controller = DraftController(draft_state)
        available = controller.get_available_players()

        vor_calc = DynamicVORCalculator("half_ppr", league_size=12)
        drafter = ComputerDrafter(vor_calculator=vor_calc, strategy="balanced")
        pick = drafter.make_pick(draft_state, available, team_id=0)

        player_info = draft_state.get_player_info(pick)
        assert player_info["position"] in ("QB", "RB", "WR", "TE"), (
            f"Round 1 pick should not be K/DST; got {player_info['position']} ({player_info['name']})"
        )

    def test_overall_rank_field_present_in_player_data(self, draft_state):
        """overall_rank must exist in player data for ADP blending to work."""
        for pid, player in list(draft_state.player_data.items())[:20]:
            assert "overall_rank" in player, (
                f"Player {pid} missing 'overall_rank' field needed for ADP blending"
            )
