"""Tests for the dynamic VOR calculator (Milestone 7)."""

import pytest

from src.draft_manager.draft_controller import DraftController
from src.draft_manager.draft_state import DraftState, LeagueConfig
from src.simulation_engine.config import (
    NEED_NORMALIZATION,
    POSITION_SCARCITY_WEIGHTS,
    QB_STREAMING_DISCOUNT,
    ROSTER_EXCESS_PENALTY,
    ROSTER_FILLED_PENALTY,
    ROSTER_NEED_WEIGHT,
    TIER_URGENCY_WEIGHT,
)
from src.simulation_engine.models import VORResult
from src.simulation_engine.vor_calculator import DynamicVORCalculator

# ── Helpers ──────────────────────────────────────────────────────────


def _make_league_config(**overrides):
    defaults = {
        "league_id": "test",
        "league_size": 4,
        "scoring_format": "half_ppr",
        "draft_type": "snake",
        "draft_mode": "simulation",
        "data_year": 2025,
        "roster_slots": {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 1,
            "DST": 1,
            "K": 1,
            "BENCH": 6,
        },
    }
    defaults.update(overrides)
    return LeagueConfig(**defaults)


def _make_player(pid, position, vor_half_ppr=22.0, vor_standard=20.0, vor_full_ppr=24.0):
    """Create a single player dict with specified VOR values."""
    return {
        "player_id": pid,
        "name": f"Player {pid}",
        "position": position,
        "team": "TST",
        "projections": {
            "standard": 100.0,
            "half_ppr": 110.0,
            "full_ppr": 120.0,
        },
        "baseline_vor": {
            "standard": vor_standard,
            "half_ppr": vor_half_ppr,
            "full_ppr": vor_full_ppr,
        },
    }


def _make_player_data():
    """Create a small set of players with varied positions and VOR values."""
    players = {}
    specs = [
        # (id, position, half_ppr VOR)
        ("qb1", "QB", 40.0),
        ("qb2", "QB", 30.0),
        ("qb3", "QB", 15.0),
        ("qb4", "QB", 5.0),
        ("rb1", "RB", 50.0),
        ("rb2", "RB", 45.0),
        ("rb3", "RB", 35.0),
        ("rb4", "RB", 25.0),
        ("rb5", "RB", 15.0),
        ("rb6", "RB", 10.0),
        ("rb7", "RB", 5.0),
        ("rb8", "RB", 2.0),
        ("wr1", "WR", 48.0),
        ("wr2", "WR", 42.0),
        ("wr3", "WR", 30.0),
        ("wr4", "WR", 20.0),
        ("wr5", "WR", 12.0),
        ("wr6", "WR", 8.0),
        ("wr7", "WR", 4.0),
        ("wr8", "WR", 1.0),
        ("te1", "TE", 35.0),
        ("te2", "TE", 20.0),
        ("te3", "TE", 10.0),
        ("te4", "TE", 3.0),
        ("k1", "K", 8.0),
        ("k2", "K", 5.0),
        ("k3", "K", 2.0),
        ("k4", "K", 1.0),
        ("dst1", "DST", 10.0),
        ("dst2", "DST", 6.0),
        ("dst3", "DST", 3.0),
        ("dst4", "DST", 1.0),
    ]
    for pid, pos, vor in specs:
        players[pid] = _make_player(pid, pos, vor_half_ppr=vor)
    return players


def _make_draft_state(league_size=4, **config_overrides):
    config = _make_league_config(league_size=league_size, **config_overrides)
    players = _make_player_data()
    team_names = [f"Team {i}" for i in range(league_size)]
    return DraftState.create_new(
        league_config=config,
        team_names=team_names,
        human_team_id=0,
        player_data=players,
    )


DEFAULT_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "DST": 1,
    "K": 1,
    "BENCH": 6,
}


# ── Constructor Tests ────────────────────────────────────────────────


class TestDynamicVORCalculatorInit:
    def test_valid_scoring_formats(self):
        for fmt in ("standard", "half_ppr", "full_ppr"):
            calc = DynamicVORCalculator(fmt)
            assert calc.scoring_format == fmt

    def test_invalid_scoring_format_raises(self):
        with pytest.raises(ValueError, match="Invalid scoring_format"):
            DynamicVORCalculator("ppr")


# ── Scarcity Multiplier Tests ────────────────────────────────────────


class TestScarcityMultiplier:
    def setup_method(self):
        self.calc = DynamicVORCalculator("half_ppr", league_size=12)

    def test_no_players_drafted_returns_one(self):
        result = self.calc._calculate_scarcity_multiplier("RB", drafted_count=0, roster_slots=DEFAULT_ROSTER_SLOTS)
        assert result == 1.0

    def test_scarcity_increases_with_drafted_count(self):
        low = self.calc._calculate_scarcity_multiplier("RB", drafted_count=5, roster_slots=DEFAULT_ROSTER_SLOTS)
        high = self.calc._calculate_scarcity_multiplier("RB", drafted_count=20, roster_slots=DEFAULT_ROSTER_SLOTS)
        assert high > low > 1.0

    def test_rb_higher_weight_than_qb_at_equal_pct(self):
        """At the same drafted percentage, RB weight > QB weight."""
        # total = (slots + FLEX) × league_size; 50% of each
        rb_total = (DEFAULT_ROSTER_SLOTS["RB"] + DEFAULT_ROSTER_SLOTS["FLEX"]) * 12  # 36
        qb_total = DEFAULT_ROSTER_SLOTS["QB"] * 12  # 12
        rb_scarcity = self.calc._calculate_scarcity_multiplier("RB", drafted_count=rb_total // 2, roster_slots=DEFAULT_ROSTER_SLOTS)
        qb_scarcity = self.calc._calculate_scarcity_multiplier("QB", drafted_count=qb_total // 2, roster_slots=DEFAULT_ROSTER_SLOTS)
        assert rb_scarcity > qb_scarcity

    def test_te_higher_weight_than_wr_at_equal_pct(self):
        """At the same drafted percentage, TE weight (1.6) > WR weight (1.5)."""
        # total = (slots + FLEX) × league_size; 50% of each
        wr_total = (DEFAULT_ROSTER_SLOTS["WR"] + DEFAULT_ROSTER_SLOTS["FLEX"]) * 12  # 36
        te_total = (DEFAULT_ROSTER_SLOTS["TE"] + DEFAULT_ROSTER_SLOTS["FLEX"]) * 12  # 24
        wr_scarcity = self.calc._calculate_scarcity_multiplier("WR", drafted_count=wr_total // 2, roster_slots=DEFAULT_ROSTER_SLOTS)
        te_scarcity = self.calc._calculate_scarcity_multiplier("TE", drafted_count=te_total // 2, roster_slots=DEFAULT_ROSTER_SLOTS)
        assert te_scarcity > wr_scarcity

    def test_k_and_dst_have_equal_weight(self):
        k_scarcity = self.calc._calculate_scarcity_multiplier("K", drafted_count=5, roster_slots=DEFAULT_ROSTER_SLOTS)
        dst_scarcity = self.calc._calculate_scarcity_multiplier("DST", drafted_count=5, roster_slots=DEFAULT_ROSTER_SLOTS)
        assert k_scarcity == dst_scarcity

    def test_drafted_pct_capped_at_one(self):
        """Even if more players drafted than total startable, pct stays <= 1.0."""
        # QB total = 1 slot × 12 teams = 12
        qb_total = DEFAULT_ROSTER_SLOTS["QB"] * 12  # 12
        result = self.calc._calculate_scarcity_multiplier("QB", drafted_count=qb_total + 5, roster_slots=DEFAULT_ROSTER_SLOTS)
        max_result = self.calc._calculate_scarcity_multiplier("QB", drafted_count=qb_total, roster_slots=DEFAULT_ROSTER_SLOTS)
        assert result == max_result

    def test_specific_values(self):
        """Verify formula: 1 + (drafted_pct * weight)."""
        # RB: weight=1.5, total=(2+1)*12=36
        # 18 drafted: pct = 18/36 = 0.5, scarcity = 1 + 0.5*1.5 = 1.75
        rb_total = (DEFAULT_ROSTER_SLOTS["RB"] + DEFAULT_ROSTER_SLOTS["FLEX"]) * 12  # 36
        result = self.calc._calculate_scarcity_multiplier("RB", drafted_count=rb_total // 2, roster_slots=DEFAULT_ROSTER_SLOTS)
        expected = 1.0 + 0.5 * POSITION_SCARCITY_WEIGHTS["RB"]
        assert result == pytest.approx(expected)

        # QB: weight=0.8, total=1*12=12
        # 6 drafted: pct = 6/12 = 0.5, scarcity = 1 + 0.5*0.8 = 1.4
        qb_total = DEFAULT_ROSTER_SLOTS["QB"] * 12  # 12
        result = self.calc._calculate_scarcity_multiplier("QB", drafted_count=qb_total // 2, roster_slots=DEFAULT_ROSTER_SLOTS)
        expected_qb = 1.0 + 0.5 * POSITION_SCARCITY_WEIGHTS["QB"]
        assert result == pytest.approx(expected_qb)

    def test_k_and_dst_inverse_scarcity(self):
        """K/DST scarcity DECREASES as more drafted (inverse of skill positions).

        Skill positions: scarcity = 1 + (pct * weight) → increases
        K/DST: scarcity = 1 - (pct * weight) → decreases
        """
        # K total = 1 slot × 12 teams = 12
        k_total = DEFAULT_ROSTER_SLOTS["K"] * 12  # 12
        k_weight = POSITION_SCARCITY_WEIGHTS["K"]  # 0.3

        # No K drafted: scarcity = 1.0
        scarcity_0 = self.calc._calculate_scarcity_multiplier("K", 0, DEFAULT_ROSTER_SLOTS)
        assert scarcity_0 == pytest.approx(1.0)

        # Some K drafted: verify formula scarcity = 1 - (pct * weight)
        drafted_count = 4
        drafted_pct = drafted_count / k_total  # 4/12 ≈ 0.333
        scarcity_some = self.calc._calculate_scarcity_multiplier("K", drafted_count, DEFAULT_ROSTER_SLOTS)
        expected_some = 1.0 - (drafted_pct * k_weight)
        assert scarcity_some == pytest.approx(expected_some)

        # All K drafted: scarcity = 1 - 1.0*0.3 = 0.7
        scarcity_full = self.calc._calculate_scarcity_multiplier("K", k_total, DEFAULT_ROSTER_SLOTS)
        expected_full = 1.0 - k_weight
        assert scarcity_full == pytest.approx(expected_full)

        # Verify it decreases (inverse of skill positions)
        assert scarcity_0 > scarcity_some > scarcity_full

        # Same for DST (same slots and weight)
        dst_some = self.calc._calculate_scarcity_multiplier("DST", drafted_count, DEFAULT_ROSTER_SLOTS)
        assert dst_some == scarcity_some  # Same weight, same behavior


# ── Need Multiplier Tests ────────────────────────────────────────────


class TestNeedMultiplier:
    def setup_method(self):
        self.calc = DynamicVORCalculator("half_ppr", league_size=12)

    def _empty_roster(self):
        return {pos: [] for pos in DEFAULT_ROSTER_SLOTS}

    def test_empty_roster_gives_max_need(self):
        """All slots empty → need = 1 + (empty * ROSTER_NEED_WEIGHT / NEED_NORMALIZATION)."""
        roster = self._empty_roster()
        # QB: 1 empty slot → need = 1 + 1*0.6/3.0 = 1.2
        result = self.calc._calculate_need_multiplier("QB", roster, DEFAULT_ROSTER_SLOTS)
        expected = 1.0 + 1 * ROSTER_NEED_WEIGHT / NEED_NORMALIZATION
        assert result == pytest.approx(expected)

        # RB: 3 empty slots (2 RB + 1 FLEX) → need = 1 + 3*0.6/3.0 = 1.6
        result_rb = self.calc._calculate_need_multiplier("RB", roster, DEFAULT_ROSTER_SLOTS)
        expected_rb = 1.0 + 3 * ROSTER_NEED_WEIGHT / NEED_NORMALIZATION
        assert result_rb == pytest.approx(expected_rb)

    def test_filled_position_reduces_need(self):
        """Filling a position slot reduces need multiplier."""
        roster = self._empty_roster()
        need_empty = self.calc._calculate_need_multiplier("QB", roster, DEFAULT_ROSTER_SLOTS)

        roster["QB"] = ["qb1"]
        need_filled = self.calc._calculate_need_multiplier("QB", roster, DEFAULT_ROSTER_SLOTS)

        assert need_filled < need_empty

    def test_fully_filled_gives_penalty(self):
        """When all slots filled, need multiplier penalizes (< 1.0)."""
        roster = self._empty_roster()
        roster["QB"] = ["qb1"]  # QB has 1 slot
        result = self.calc._calculate_need_multiplier("QB", roster, DEFAULT_ROSTER_SLOTS)
        # Filled: need = 1 - ROSTER_FILLED_PENALTY = 1 - 0.4 = 0.6
        expected = 1.0 - ROSTER_FILLED_PENALTY
        assert result == pytest.approx(expected)

    def test_flex_eligible_includes_flex_slot(self):
        """RB/WR/TE need includes the FLEX slot (3 total empty slots → max boost)."""
        roster = self._empty_roster()
        # RB: 2 RB slots + 1 FLEX = 3 empty → need = 1 + 3*0.6/3.0 = 1.6
        result = self.calc._calculate_need_multiplier("RB", roster, DEFAULT_ROSTER_SLOTS)
        expected = 1.0 + 3 * ROSTER_NEED_WEIGHT / NEED_NORMALIZATION
        assert result == pytest.approx(expected)

    def test_flex_filled_reduces_rb_need(self):
        """Filling the FLEX slot reduces need for FLEX-eligible positions."""
        roster = self._empty_roster()
        need_before = self.calc._calculate_need_multiplier("RB", roster, DEFAULT_ROSTER_SLOTS)

        roster["FLEX"] = ["wr1"]  # Someone in FLEX
        need_after = self.calc._calculate_need_multiplier("RB", roster, DEFAULT_ROSTER_SLOTS)

        assert need_after < need_before

    def test_qb_not_flex_eligible(self):
        """QB need does NOT include FLEX slot (1 empty slot → smaller boost than RB)."""
        roster = self._empty_roster()
        result = self.calc._calculate_need_multiplier("QB", roster, DEFAULT_ROSTER_SLOTS)
        # 1 empty slot: need = 1 + 1*0.6/3.0 = 1.2 (less than RB's 1.6)
        expected = 1.0 + 1 * ROSTER_NEED_WEIGHT / NEED_NORMALIZATION
        assert result == pytest.approx(expected)
        # Verify QB need < RB need (intentional design: QBs drafted later)
        rb_need = self.calc._calculate_need_multiplier("RB", roster, DEFAULT_ROSTER_SLOTS)
        assert result < rb_need

    def test_k_not_flex_eligible(self):
        """K need does NOT include FLEX slot (1 empty slot → 1.2)."""
        roster = self._empty_roster()
        result = self.calc._calculate_need_multiplier("K", roster, DEFAULT_ROSTER_SLOTS)
        expected = 1.0 + 1 * ROSTER_NEED_WEIGHT / NEED_NORMALIZATION
        assert result == pytest.approx(expected)

    def test_dst_not_flex_eligible(self):
        """DST need does NOT include FLEX slot (1 empty slot → 1.2)."""
        roster = self._empty_roster()
        result = self.calc._calculate_need_multiplier("DST", roster, DEFAULT_ROSTER_SLOTS)
        expected = 1.0 + 1 * ROSTER_NEED_WEIGHT / NEED_NORMALIZATION
        assert result == pytest.approx(expected)

    def test_partially_filled_rb(self):
        """Partially filled RB slots give intermediate need."""
        roster = self._empty_roster()
        roster["RB"] = ["rb1"]
        # RB: 3 total starting (2 RB + 1 FLEX), 1 filled → 2 empty
        # need = 1 + (2 * 0.6 / 3.0) = 1.4
        result = self.calc._calculate_need_multiplier("RB", roster, DEFAULT_ROSTER_SLOTS)
        expected = 1 + (2 * ROSTER_NEED_WEIGHT / NEED_NORMALIZATION)
        assert result == pytest.approx(expected, abs=0.01)

    def test_zero_total_slots_returns_penalty(self):
        """Position with no slots in config returns penalized value."""
        roster = self._empty_roster()
        slots = {**DEFAULT_ROSTER_SLOTS}
        del slots["K"]
        result = self.calc._calculate_need_multiplier("K", roster, slots)
        # No slots at all: 1 - ROSTER_FILLED_PENALTY = 1 - 0.4 = 0.6
        expected = 1.0 - ROSTER_FILLED_PENALTY
        assert result == pytest.approx(expected)

    def test_excess_players_increase_penalty(self):
        """Drafting beyond starting slots increases penalty progressively."""
        roster = self._empty_roster()
        roster["K"] = ["k1"]  # K slot filled (1/1)
        need_first_extra = self.calc._calculate_need_multiplier("K", roster, DEFAULT_ROSTER_SLOTS)

        roster["K"] = ["k1", "k2"]  # 2 Ks, only 1 slot (1 excess)
        need_second_extra = self.calc._calculate_need_multiplier("K", roster, DEFAULT_ROSTER_SLOTS)

        # Both should be < 1.0 (penalized)
        assert need_first_extra < 1.0
        assert need_second_extra < 1.0
        # More excess = more penalty
        assert need_second_extra < need_first_extra

    def test_penalty_floors_at_minimum(self):
        """Need multiplier floors depend on position.

        K/DST floor at 0.0 to aggressively discourage hoarding.
        Other positions floor at 0.01 (lowered from 0.05 to allow stronger penalties).
        """
        roster = self._empty_roster()

        # K/DST with extreme excess floor at 0.0
        roster["K"] = [f"k{i}" for i in range(10)]
        result_k = self.calc._calculate_need_multiplier("K", roster, DEFAULT_ROSTER_SLOTS)
        assert result_k == pytest.approx(0.0)

        # Skill positions with extreme excess floor at 0.01
        roster_rb = self._empty_roster()
        roster_rb["RB"] = [f"rb{i}" for i in range(20)]
        result_rb = self.calc._calculate_need_multiplier("RB", roster_rb, DEFAULT_ROSTER_SLOTS)
        assert result_rb >= 0.01

    def test_filled_k_penalizes_vs_unfilled_wr(self):
        """A team with K filled should value WR much higher than another K."""
        roster = self._empty_roster()
        roster["K"] = ["k1"]
        k_need = self.calc._calculate_need_multiplier("K", roster, DEFAULT_ROSTER_SLOTS)
        wr_need = self.calc._calculate_need_multiplier("WR", roster, DEFAULT_ROSTER_SLOTS)
        # WR has 3 empty slots → boosted; K is filled → penalized
        assert wr_need > k_need
        assert wr_need > 1.0
        assert k_need < 1.0


# ── Position Slot Counting Tests ─────────────────────────────────────


class TestCountPositionSlots:
    def test_qb_no_flex(self):
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        filled, total = DynamicVORCalculator._count_position_slots(
            "QB", roster, DEFAULT_ROSTER_SLOTS
        )
        assert total == 1
        assert filled == 0

    def test_rb_includes_flex(self):
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        filled, total = DynamicVORCalculator._count_position_slots(
            "RB", roster, DEFAULT_ROSTER_SLOTS
        )
        assert total == 3  # 2 RB + 1 FLEX
        assert filled == 0

    def test_wr_includes_flex(self):
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        filled, total = DynamicVORCalculator._count_position_slots(
            "WR", roster, DEFAULT_ROSTER_SLOTS
        )
        assert total == 3  # 2 WR + 1 FLEX

    def test_te_includes_flex(self):
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        filled, total = DynamicVORCalculator._count_position_slots(
            "TE", roster, DEFAULT_ROSTER_SLOTS
        )
        assert total == 2  # 1 TE + 1 FLEX

    def test_filled_counts_correctly(self):
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        roster["RB"] = ["rb1", "rb2"]
        roster["FLEX"] = ["rb3"]
        filled, total = DynamicVORCalculator._count_position_slots(
            "RB", roster, DEFAULT_ROSTER_SLOTS
        )
        assert filled == 3  # 2 RB + 1 FLEX
        assert total == 3


# ── Dynamic VOR End-to-End Tests ─────────────────────────────────────


class TestCalculateDynamicVOR:
    def setup_method(self):
        self.calc = DynamicVORCalculator("half_ppr", league_size=12)

    def test_returns_vor_result_for_each_player(self):
        players = [_make_player("rb1", "RB"), _make_player("wr1", "WR")]
        result = self.calc.calculate_dynamic_vor(
            available_players=players,
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        assert len(result) == 2
        assert "rb1" in result
        assert "wr1" in result
        assert isinstance(result["rb1"], VORResult)

    def test_no_drafted_no_roster_returns_base_vor_times_need(self):
        """With no drafted players and empty roster, VOR = base * scarcity * need * uncertainty."""
        player = _make_player("qb1", "QB", vor_half_ppr=40.0)
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        result = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster,
            current_round=5,  # Mid-round (uncertainty_adj = 1.0)
        )
        r = result["qb1"]
        assert r.base_vor == 40.0
        assert r.scarcity_multiplier == 1.0
        # QB: 1 empty slot → need = 1 + 1*0.6/3.0 = 1.2
        expected_need = 1.0 + 1 * ROSTER_NEED_WEIGHT / NEED_NORMALIZATION
        assert r.need_multiplier == pytest.approx(expected_need)
        # Mid-round: uncertainty_adj = 1.0; single player → tier_urgency = 1.0 (no gap)
        # QB also gets QB_STREAMING_DISCOUNT applied (1-QB league streaming adjustment)
        # dynamic_vor = base * scarcity * need * uncertainty_adj * tier_urgency * QB_STREAMING_DISCOUNT
        expected = 40.0 * 1.0 * expected_need * 1.0 * 1.0 * QB_STREAMING_DISCOUNT
        assert r.dynamic_vor == pytest.approx(expected)

    def test_scarcity_boosts_positions_with_more_drafted(self):
        """Position with more drafted players gets higher scarcity boost."""
        rb = _make_player("rb1", "RB", vor_half_ppr=40.0)
        wr = _make_player("wr1", "WR", vor_half_ppr=40.0)

        result = self.calc.calculate_dynamic_vor(
            available_players=[rb, wr],
            drafted_positions={"RB": 20, "WR": 5},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        # RB has more drafted → higher scarcity multiplier
        assert result["rb1"].scarcity_multiplier > result["wr1"].scarcity_multiplier
        # Same base VOR + higher scarcity → higher dynamic VOR for RB
        assert result["rb1"].dynamic_vor > result["wr1"].dynamic_vor

    def test_need_boosts_unfilled_positions(self):
        """Unfilled positions get higher need multiplier."""
        qb = _make_player("qb1", "QB", vor_half_ppr=30.0)
        te = _make_player("te1", "TE", vor_half_ppr=30.0)

        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        roster["QB"] = ["other_qb"]  # QB slot filled

        result = self.calc.calculate_dynamic_vor(
            available_players=[qb, te],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster,
        )
        # TE has unfilled slots, QB is filled → TE gets higher need
        assert result["te1"].need_multiplier > result["qb1"].need_multiplier

    def test_monotonic_within_position(self):
        """Higher base VOR → higher dynamic VOR at same position."""
        players = [
            _make_player("rb1", "RB", vor_half_ppr=50.0),
            _make_player("rb2", "RB", vor_half_ppr=40.0),
            _make_player("rb3", "RB", vor_half_ppr=30.0),
        ]
        result = self.calc.calculate_dynamic_vor(
            available_players=players,
            drafted_positions={"RB": 10},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        assert result["rb1"].dynamic_vor > result["rb2"].dynamic_vor
        assert result["rb2"].dynamic_vor > result["rb3"].dynamic_vor

    def test_position_ranks_assigned(self):
        """Players ranked within their position by base VOR."""
        players = [
            _make_player("rb1", "RB", vor_half_ppr=50.0),
            _make_player("rb2", "RB", vor_half_ppr=30.0),
            _make_player("wr1", "WR", vor_half_ppr=45.0),
        ]
        result = self.calc.calculate_dynamic_vor(
            available_players=players,
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        assert result["rb1"].position_rank == 1
        assert result["rb2"].position_rank == 2
        assert result["wr1"].position_rank == 1  # Only WR

    def test_different_scoring_format(self):
        """VOR looks up the correct scoring format."""
        player = _make_player("qb1", "QB", vor_standard=15.0, vor_half_ppr=20.0)
        calc_std = DynamicVORCalculator("standard", league_size=12)
        calc_half = DynamicVORCalculator("half_ppr", league_size=12)

        result_std = calc_std.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        result_half = calc_half.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        assert result_std["qb1"].base_vor == 15.0
        assert result_half["qb1"].base_vor == 20.0

    def test_empty_available_players(self):
        result = self.calc.calculate_dynamic_vor(
            available_players=[],
            drafted_positions={"RB": 10},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        assert result == {}


# ── Edge Case Tests ──────────────────────────────────────────────────


class TestEdgeCases:
    def setup_method(self):
        self.calc = DynamicVORCalculator("half_ppr", league_size=12)

    def test_zero_base_vor(self):
        """Player with 0 base VOR still gets balance adjustment (not zero due to additive component)."""
        player = _make_player("rb1", "RB", vor_half_ppr=0.0)
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        result = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={"RB": 20},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster,
        )
        # 0 * anything = 0
        assert result["rb1"].base_vor == 0.0
        assert result["rb1"].dynamic_vor == 0.0
        assert result["rb1"].scarcity_multiplier > 1.0  # Scarcity still applies

    def test_negative_base_vor(self):
        """Negative base VOR stays negative (multiplicative formula preserves sign)."""
        player = _make_player("rb1", "RB", vor_half_ppr=-5.0)
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        result = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={"RB": 18},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster,
        )
        assert result["rb1"].base_vor == -5.0
        # Negative base * positive multipliers = negative dynamic
        assert result["rb1"].dynamic_vor < 0

    def test_missing_baseline_vor_defaults_to_zero(self):
        """Player without baseline_vor key gets 0.0 base and 0.0 dynamic."""
        player = {
            "player_id": "unknown",
            "name": "Unknown",
            "position": "RB",
            "team": "TST",
        }
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        result = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster,
        )
        assert result["unknown"].base_vor == 0.0
        assert result["unknown"].dynamic_vor == 0.0

    def test_missing_position_in_drafted_positions(self):
        """Position not in drafted_positions dict treated as 0 drafted."""
        player = _make_player("k1", "K", vor_half_ppr=5.0)
        result = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={"RB": 10},  # No K entry
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        assert result["k1"].scarcity_multiplier == 1.0

    def test_all_startable_drafted_caps_scarcity(self):
        """Scarcity doesn't go above the capped value."""
        player = _make_player("qb1", "QB", vor_half_ppr=30.0)
        # QB total startable = 1 slot × 12 teams = 12
        qb_total = DEFAULT_ROSTER_SLOTS["QB"] * 12  # 12
        result_at = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={"QB": qb_total},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
            current_round=5,
        )
        # Draft more than total
        result_over = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={"QB": qb_total + 10},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
            current_round=5,
        )
        assert result_at["qb1"].scarcity_multiplier == result_over["qb1"].scarcity_multiplier
        # QB weight=0.8, pct=1.0 → scarcity = 1 + 1.0*0.8 = 1.8
        expected_max_scarcity = 1.0 + 1.0 * POSITION_SCARCITY_WEIGHTS["QB"]
        assert result_at["qb1"].scarcity_multiplier == pytest.approx(expected_max_scarcity)


# ── DraftState Integration Tests ─────────────────────────────────────


class TestCalculateFromDraftState:
    def setup_method(self):
        self.calc = DynamicVORCalculator("half_ppr", league_size=12)

    def test_fresh_draft(self):
        """calculate_from_draft_state works on a brand-new draft."""
        state = _make_draft_state()
        result = self.calc.calculate_from_draft_state(state, team_id=0)

        # Should have a result for every available player
        assert len(result) == len(state.available_players)

        # All scarcity multipliers should be 1.0 (nothing drafted yet)
        for vor_result in result.values():
            assert vor_result.scarcity_multiplier == 1.0

        # All need multipliers should be > 1.0 (all slots empty)
        for vor_result in result.values():
            assert vor_result.need_multiplier > 1.0

    def test_after_picks(self):
        """VOR adjusts after picks are made."""
        state = _make_draft_state()
        controller = DraftController(state)

        # Make a few picks
        controller.make_pick(0, "rb1")  # Team 0 picks RB
        controller.make_pick(1, "rb2")  # Team 1 picks RB
        controller.make_pick(2, "rb3")  # Team 2 picks RB
        controller.make_pick(3, "rb4")  # Team 3 picks RB

        result = self.calc.calculate_from_draft_state(state, team_id=0)

        # Drafted players should not appear
        assert "rb1" not in result
        assert "rb2" not in result

        # RB scarcity should be > 1.0 (4 RBs drafted)
        rb_results = [r for r in result.values() if r.position == "RB"]
        for r in rb_results:
            assert r.scarcity_multiplier > 1.0

        # Team 0 already has an RB, so RB need lower than for a team with none
        result_team1 = self.calc.calculate_from_draft_state(state, team_id=1)
        rb5_team0 = result["rb5"]
        rb5_team1 = result_team1["rb5"]
        # Both teams have 1 RB each, so need should be equal
        assert rb5_team0.need_multiplier == pytest.approx(rb5_team1.need_multiplier)

    def test_flex_pick_counted_correctly(self):
        """Players drafted into FLEX slot are counted by their actual position."""
        state = _make_draft_state()
        controller = DraftController(state)

        # Fill Team 0's RB slots: 2 RB + 1 FLEX
        controller.make_pick(0, "rb1")  # Team 0 picks (RB slot)
        controller.make_pick(1, "wr1")  # Team 1
        controller.make_pick(2, "qb1")  # Team 2
        controller.make_pick(3, "te1")  # Team 3

        # Round 2 (snake: 3,2,1,0)
        controller.make_pick(3, "wr2")
        controller.make_pick(2, "rb2")
        controller.make_pick(1, "qb2")
        controller.make_pick(0, "rb3")  # Team 0's second RB (fills RB2)

        # Round 3 (1,2,3,4)
        controller.make_pick(0, "rb4")  # Team 0 → goes to FLEX slot

        result = self.calc.calculate_from_draft_state(state, team_id=0)

        # rb4 is in FLEX but is an RB → should be counted as RB drafted
        # Remaining RBs should reflect the drafted count
        remaining_rbs = [r for r in result.values() if r.position == "RB"]
        for r in remaining_rbs:
            # 4 RBs drafted: rb1 (team 0), rb3 (team 0), rb4 (team 0 FLEX), rb2 (team 2)
            assert r.scarcity_multiplier > 1.0

    def test_different_teams_have_different_need(self):
        """Two teams with different rosters get different need multipliers."""
        state = _make_draft_state()
        controller = DraftController(state)

        # Team 0 picks QB, Team 1 picks RB
        controller.make_pick(0, "qb1")
        controller.make_pick(1, "rb1")
        controller.make_pick(2, "wr1")
        controller.make_pick(3, "te1")

        result_team0 = self.calc.calculate_from_draft_state(state, team_id=0)
        result_team1 = self.calc.calculate_from_draft_state(state, team_id=1)

        # Team 0 filled QB → QB need lower
        qb2_team0 = result_team0["qb2"]
        qb2_team1 = result_team1["qb2"]
        assert qb2_team0.need_multiplier < qb2_team1.need_multiplier

        # Team 1 filled RB → RB need lower for team 1
        rb2_team0 = result_team0["rb2"]
        rb2_team1 = result_team1["rb2"]
        assert rb2_team1.need_multiplier < rb2_team0.need_multiplier


# ── Formula Verification Tests ───────────────────────────────────────


class TestFormulaVerification:
    """Verify the exact dynamic VOR formula from the architecture doc."""

    def test_architecture_doc_example(self):
        """Replicate the example from SIMULATION_ENGINE_MODULE.md (updated for new constants)."""
        calc = DynamicVORCalculator("half_ppr", league_size=12)

        henry = _make_player("henry", "RB", vor_half_ppr=85.2)
        wilson = _make_player("wilson", "WR", vor_half_ppr=75.5)

        # Scenario: Round 3, Pick 5 (12-team league)
        # 28 picks made: 15 RBs, 10 WRs, 3 QBs
        # Team roster: 1 RB filled, 1 WR filled (RB+WR each have 2+1FLEX=3 slots)
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        roster["RB"] = ["some_rb"]
        roster["WR"] = ["some_wr"]

        result = calc.calculate_dynamic_vor(
            available_players=[henry, wilson],
            drafted_positions={"QB": 3, "RB": 15, "WR": 10},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster,
            current_round=3,
        )

        # Henry: total = (RB+FLEX)*12 = (2+1)*12 = 36; scarcity = 1 + (15/36)*1.5
        rb_total = (DEFAULT_ROSTER_SLOTS["RB"] + DEFAULT_ROSTER_SLOTS["FLEX"]) * 12  # 36
        henry_r = result["henry"]
        expected_scarcity = 1 + (15 / rb_total) * POSITION_SCARCITY_WEIGHTS["RB"]
        assert henry_r.scarcity_multiplier == pytest.approx(expected_scarcity)
        # Henry: need = 1 + (2/3)*0.6 = 1.4 (1 of 3 slots filled, ROSTER_NEED_WEIGHT=0.6)
        assert henry_r.need_multiplier == pytest.approx(1 + (2 / 3) * ROSTER_NEED_WEIGHT)

        # Wilson: total = (WR+FLEX)*12 = (2+1)*12 = 36; scarcity = 1 + (10/36)*1.5
        wr_total = (DEFAULT_ROSTER_SLOTS["WR"] + DEFAULT_ROSTER_SLOTS["FLEX"]) * 12  # 36
        wilson_r = result["wilson"]
        expected_wr_scarcity = 1 + (10 / wr_total) * POSITION_SCARCITY_WEIGHTS["WR"]
        assert wilson_r.scarcity_multiplier == pytest.approx(expected_wr_scarcity)
        # Wilson: same need (1 of 3 slots filled)
        assert wilson_r.need_multiplier == pytest.approx(1 + (2 / 3) * ROSTER_NEED_WEIGHT)

        # Henry has higher base VOR and more scarcity → higher dynamic VOR
        assert henry_r.dynamic_vor > wilson_r.dynamic_vor > 0

    def test_dynamic_vor_equals_product(self):
        """dynamic_vor == base_vor * scarcity * need * uncertainty_adj for every player."""
        calc = DynamicVORCalculator("half_ppr", league_size=12)
        players = list(_make_player_data().values())

        result = calc.calculate_dynamic_vor(
            available_players=players,
            drafted_positions={"QB": 3, "RB": 10, "WR": 8, "TE": 2},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
            current_round=5,  # Mid-round (no uncertainty adjustment)
        )

        # Calculate draft completion percentage for round 5
        total_picks = sum(DEFAULT_ROSTER_SLOTS.values()) * 12  # 180
        picks_made_approx = (5 - 1) * 12 + (12 // 2)  # 54
        draft_pct_complete = picks_made_approx / total_picks  # 0.30 (30%)

        # Build tier information for all players so we can look up urgency
        tiers_data = calc._detect_tiers(players)

        for vor in result.values():
            # Mid-round (round 5): uncertainty_adj = 1.0
            uncertainty_adj = calc._calculate_uncertainty_adjustment(vor.uncertainty, 5)

            # Tier urgency for this player
            tier_info = tiers_data.get(vor.position, {}).get(vor.player_id, {})
            tier_gap = tier_info.get("tier_gap", 0.0)
            tier_size = max(1, tier_info.get("tier_size", 1))
            tier_urgency = 1.0 + (tier_gap / tier_size) * TIER_URGENCY_WEIGHT

            # K/DST use fixed negative values early in draft based on completion percentage
            if vor.position in ("K", "DST"):
                if draft_pct_complete < 0.65:
                    expected = -50.0
                elif draft_pct_complete < 0.80:
                    expected = -5.0
                else:
                    position_value_penalty = 0.50
                    expected = (
                        vor.base_vor
                        * vor.scarcity_multiplier
                        * vor.need_multiplier
                        * uncertainty_adj
                        * position_value_penalty
                    )
            else:
                # Skill positions: base * scarcity * need * uncertainty * tier_urgency
                expected = (
                    vor.base_vor
                    * vor.scarcity_multiplier
                    * vor.need_multiplier
                    * uncertainty_adj
                    * tier_urgency
                )
                # QB also gets streaming discount applied (1-QB league BEER+ adjustment)
                if vor.position == "QB":
                    expected *= QB_STREAMING_DISCOUNT

            assert vor.dynamic_vor == pytest.approx(expected, rel=1e-4)


# ── Bench Depth Penalty Tests ────────────────────────────────────────


class TestBenchDepthPenalty:
    """Test that bench players are counted when calculating excess position penalty."""

    def setup_method(self):
        self.calc = DynamicVORCalculator("half_ppr", league_size=12)

    def test_bench_wr_counts_as_filled(self):
        """WRs on the bench should count toward excess penalty."""
        # DEFAULT_ROSTER_SLOTS: 2 WR slots + 1 FLEX = 3 starting slots for WRs
        # Team has 2 WRs in WR slots + 1 in FLEX + 3 WRs on bench = 6 total WRs
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        roster["WR"] = ["wr1", "wr2"]  # 2 WRs in WR slots
        roster["FLEX"] = ["wr3"]  # 1 WR in FLEX
        roster["BENCH"] = ["wr4", "wr5", "wr6"]  # 3 more WRs on bench

        # Build player_positions mapping
        player_positions = {
            "wr1": "WR",
            "wr2": "WR",
            "wr3": "WR",
            "wr4": "WR",
            "wr5": "WR",
            "wr6": "WR",
        }

        result = self.calc.calculate_dynamic_vor(
            available_players=[_make_player("wr7", "WR")],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster,
            current_round=5,
            player_positions=player_positions,
        )

        wr = result["wr7"]
        # Total WR+FLEX slots = 2 WR + 1 FLEX = 3
        # Filled = 2 (WR slots) + 1 (FLEX) + 3 (BENCH) = 6 (all are WRs)
        # Excess = 6 - 3 = 3
        # Progressive penalty: excess 1: 0.15, excess 2: 0.15, excess 3: 0.40 → total = 0.70
        # Need = 1 - ROSTER_FILLED_PENALTY - progressive_penalty
        #      = 1 - 0.4 - 0.70 = -0.10 → floors at 0.01
        expected_need = 0.01
        assert wr.need_multiplier == pytest.approx(expected_need)

    def test_bench_rb_counts_as_filled(self):
        """RBs on the bench should count toward excess penalty."""
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        roster["RB"] = ["rb1", "rb2"]  # 2 RBs in RB slots
        roster["BENCH"] = ["rb3", "rb4", "rb5"]  # 3 RBs on bench

        player_positions = {
            "rb1": "RB",
            "rb2": "RB",
            "rb3": "RB",
            "rb4": "RB",
            "rb5": "RB",
        }

        result = self.calc.calculate_dynamic_vor(
            available_players=[_make_player("rb6", "RB")],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster,
            current_round=5,
            player_positions=player_positions,
        )

        rb = result["rb6"]
        # Total RB+FLEX slots = 2 RB + 1 FLEX = 3
        # Filled = 2 RB + 3 BENCH = 5 (all are RBs)
        # Excess = 5 - 3 = 2
        # Need = 1 - 0.4 - (2 * 0.15) = 0.3
        expected_need = 1.0 - ROSTER_FILLED_PENALTY - (2 * ROSTER_EXCESS_PENALTY)
        assert rb.need_multiplier == pytest.approx(expected_need)

    def test_bench_kicker_counts_as_filled(self):
        """Kickers on the bench should heavily penalize additional K picks."""
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        roster["K"] = ["k1"]  # 1 K in K slot (K only has 1 slot, not FLEX-eligible)
        roster["BENCH"] = ["k2", "k3", "k4"]  # 3 Ks on bench (excessive!)

        player_positions = {
            "k1": "K",
            "k2": "K",
            "k3": "K",
            "k4": "K",
        }

        result = self.calc.calculate_dynamic_vor(
            available_players=[_make_player("k5", "K")],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster,
            current_round=5,
            player_positions=player_positions,
        )

        k = result["k5"]
        # Total K slots = 1 (K is not FLEX-eligible)
        # Filled = 1 K + 3 BENCH = 4 (all are Ks)
        # Excess = 4 - 1 = 3
        # K/DST have steeper penalty: 0.4 + (3 * 0.50) = 1.9
        # Need = 1 - 1.9 = -0.9, floors at 0.0 for K/DST
        expected_need = 0.0
        assert k.need_multiplier == pytest.approx(expected_need)

    def test_mixed_positions_on_bench(self):
        """Only bench players of the target position should count."""
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        roster["WR"] = ["wr1"]  # 1 WR in WR slot
        roster["BENCH"] = ["wr2", "rb1", "qb1"]  # 1 WR + 1 RB + 1 QB on bench

        player_positions = {
            "wr1": "WR",
            "wr2": "WR",
            "rb1": "RB",
            "qb1": "QB",
        }

        result = self.calc.calculate_dynamic_vor(
            available_players=[_make_player("wr3", "WR")],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster,
            current_round=5,
            player_positions=player_positions,
        )

        wr = result["wr3"]
        # Total WR+FLEX slots = 2 WR + 1 FLEX = 3
        # Filled = 1 (WR slot) + 0 (FLEX, empty) + 1 (BENCH_WR) = 2 (only counting WRs, not RB or QB)
        # Empty = 3 - 2 = 1
        # Need = 1 + (1/3) * 0.6 = 1 + 0.2 = 1.2
        expected_need = 1.0 + (1 / 3) * ROSTER_NEED_WEIGHT
        assert wr.need_multiplier == pytest.approx(expected_need)

    def test_kicker_steeper_penalty_than_skill_positions(self):
        """K/DST should have steeper excess penalty (0.50) vs skill positions (0.15)."""
        # Create two rosters with same excess (2 bench players)
        roster_k = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        roster_k["K"] = ["k1"]
        roster_k["BENCH"] = ["k2", "k3"]  # 2 excess kickers

        roster_rb = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        roster_rb["RB"] = ["rb1", "rb2"]
        roster_rb["FLEX"] = ["rb3"]  # All RB starting slots filled
        roster_rb["BENCH"] = ["rb4", "rb5"]  # 2 excess RBs

        player_positions_k = {"k1": "K", "k2": "K", "k3": "K"}
        player_positions_rb = {
            "rb1": "RB",
            "rb2": "RB",
            "rb3": "RB",
            "rb4": "RB",
            "rb5": "RB",
        }

        result_k = self.calc.calculate_dynamic_vor(
            available_players=[_make_player("k4", "K")],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster_k,
            current_round=5,
            player_positions=player_positions_k,
        )

        result_rb = self.calc.calculate_dynamic_vor(
            available_players=[_make_player("rb6", "RB")],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster_rb,
            current_round=5,
            player_positions=player_positions_rb,
        )

        k = result_k["k4"]
        rb = result_rb["rb6"]

        # K with 2 excess: penalty = 0.4 + (2 * 0.50) = 1.4, need = 1 - 1.4 = -0.4, floors at 0.0
        assert k.need_multiplier == pytest.approx(0.0)

        # RB with 2 excess: penalty = 0.4 + (2 * 0.15) = 0.7, need = 1 - 0.7 = 0.3, floors at 0.01
        expected_rb_need = 1.0 - ROSTER_FILLED_PENALTY - (2 * ROSTER_EXCESS_PENALTY)
        assert rb.need_multiplier == pytest.approx(expected_rb_need)

        # K penalty should be much more severe
        assert k.need_multiplier < rb.need_multiplier

    def test_without_player_positions_uses_fallback(self):
        """When player_positions is not provided, bench is not counted (fallback logic)."""
        roster = {pos: [] for pos in DEFAULT_ROSTER_SLOTS}
        roster["WR"] = ["wr1", "wr2"]  # 2 WRs in WR slots
        roster["FLEX"] = ["wr3"]  # 1 WR in FLEX (fallback assumes this is a WR)
        roster["BENCH"] = [
            "wr4",
            "wr5",
        ]  # These won't be counted without player_positions

        # Call WITHOUT player_positions parameter
        result = self.calc.calculate_dynamic_vor(
            available_players=[_make_player("wr6", "WR")],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster=roster,
            current_round=5,
            # NO player_positions provided
        )

        wr = result["wr6"]
        # Without player_positions, bench is not counted, but FLEX is counted (fallback)
        # Total WR+FLEX slots = 2 WR + 1 FLEX = 3
        # Filled = 2 (WR) + 1 (FLEX, fallback counts all FLEX players)  = 3
        # Empty = 3 - 3 = 0
        # All starters filled: Need = 1 - ROSTER_FILLED_PENALTY = 1 - 0.4 = 0.6
        expected_need = 1.0 - ROSTER_FILLED_PENALTY
        assert wr.need_multiplier == pytest.approx(expected_need)
