"""Tests for the dynamic VOR calculator (Milestone 7)."""

import pytest

from src.draft_manager.draft_controller import DraftController
from src.draft_manager.draft_state import DraftState, LeagueConfig
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
            "QB": 1, "RB": 2, "WR": 2, "TE": 1,
            "FLEX": 1, "DST": 1, "K": 1, "BENCH": 6,
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
        ("qb1", "QB", 40.0), ("qb2", "QB", 30.0),
        ("qb3", "QB", 15.0), ("qb4", "QB", 5.0),
        ("rb1", "RB", 50.0), ("rb2", "RB", 45.0),
        ("rb3", "RB", 35.0), ("rb4", "RB", 25.0),
        ("rb5", "RB", 15.0), ("rb6", "RB", 10.0),
        ("rb7", "RB", 5.0), ("rb8", "RB", 2.0),
        ("wr1", "WR", 48.0), ("wr2", "WR", 42.0),
        ("wr3", "WR", 30.0), ("wr4", "WR", 20.0),
        ("wr5", "WR", 12.0), ("wr6", "WR", 8.0),
        ("wr7", "WR", 4.0), ("wr8", "WR", 1.0),
        ("te1", "TE", 35.0), ("te2", "TE", 20.0),
        ("te3", "TE", 10.0), ("te4", "TE", 3.0),
        ("k1", "K", 8.0), ("k2", "K", 5.0),
        ("k3", "K", 2.0), ("k4", "K", 1.0),
        ("dst1", "DST", 10.0), ("dst2", "DST", 6.0),
        ("dst3", "DST", 3.0), ("dst4", "DST", 1.0),
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
    "QB": 1, "RB": 2, "WR": 2, "TE": 1,
    "FLEX": 1, "DST": 1, "K": 1, "BENCH": 6,
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
        self.calc = DynamicVORCalculator("half_ppr")

    def test_no_players_drafted_returns_one(self):
        result = self.calc._calculate_scarcity_multiplier("RB", drafted_count=0)
        assert result == 1.0

    def test_scarcity_increases_with_drafted_count(self):
        low = self.calc._calculate_scarcity_multiplier("RB", drafted_count=5)
        high = self.calc._calculate_scarcity_multiplier("RB", drafted_count=20)
        assert high > low > 1.0

    def test_rb_higher_weight_than_qb_at_equal_pct(self):
        """At the same drafted percentage, RB weight (2.0) > QB weight (1.2)."""
        # 50% drafted at each position
        rb_scarcity = self.calc._calculate_scarcity_multiplier("RB", drafted_count=18)  # 18/36
        qb_scarcity = self.calc._calculate_scarcity_multiplier("QB", drafted_count=6)   # 6/12
        assert rb_scarcity > qb_scarcity

    def test_wr_higher_weight_than_te_at_equal_pct(self):
        """At the same drafted percentage, WR weight (1.8) > TE weight (1.5)."""
        # 50% drafted at each position
        wr_scarcity = self.calc._calculate_scarcity_multiplier("WR", drafted_count=18)  # 18/36
        te_scarcity = self.calc._calculate_scarcity_multiplier("TE", drafted_count=6)   # 6/12
        assert wr_scarcity > te_scarcity

    def test_k_and_dst_have_equal_weight(self):
        k_scarcity = self.calc._calculate_scarcity_multiplier("K", drafted_count=5)
        dst_scarcity = self.calc._calculate_scarcity_multiplier("DST", drafted_count=5)
        assert k_scarcity == dst_scarcity

    def test_drafted_pct_capped_at_one(self):
        """Even if more players drafted than baseline, pct stays <= 1.0."""
        # VOR_BASELINE_COUNTS["QB"] = 12, but draft 20
        result = self.calc._calculate_scarcity_multiplier("QB", drafted_count=20)
        max_result = self.calc._calculate_scarcity_multiplier("QB", drafted_count=12)
        assert result == max_result

    def test_specific_values(self):
        """Verify formula: 1 + (drafted_pct * weight)."""
        # RB: weight=2.0, baseline=36
        # 18 drafted: pct = 18/36 = 0.5, scarcity = 1 + 0.5*2.0 = 2.0
        result = self.calc._calculate_scarcity_multiplier("RB", drafted_count=18)
        assert result == pytest.approx(2.0)

        # QB: weight=1.2, baseline=12
        # 6 drafted: pct = 6/12 = 0.5, scarcity = 1 + 0.5*1.2 = 1.6
        result = self.calc._calculate_scarcity_multiplier("QB", drafted_count=6)
        assert result == pytest.approx(1.6)


# ── Need Multiplier Tests ────────────────────────────────────────────


class TestNeedMultiplier:
    def setup_method(self):
        self.calc = DynamicVORCalculator("half_ppr")

    def _empty_roster(self):
        return {pos: [] for pos in DEFAULT_ROSTER_SLOTS}

    def test_empty_roster_gives_max_need(self):
        """All slots empty → maximum need multiplier."""
        roster = self._empty_roster()
        # QB: 1 slot, 0 filled → need = 1 + (1/1)*0.5 = 1.5
        result = self.calc._calculate_need_multiplier("QB", roster, DEFAULT_ROSTER_SLOTS)
        assert result == pytest.approx(1.5)

    def test_filled_position_reduces_need(self):
        """Filling a position slot reduces need multiplier."""
        roster = self._empty_roster()
        need_empty = self.calc._calculate_need_multiplier("QB", roster, DEFAULT_ROSTER_SLOTS)

        roster["QB"] = ["qb1"]
        need_filled = self.calc._calculate_need_multiplier("QB", roster, DEFAULT_ROSTER_SLOTS)

        assert need_filled < need_empty

    def test_fully_filled_gives_one(self):
        """When all slots filled, need multiplier is 1.0."""
        roster = self._empty_roster()
        roster["QB"] = ["qb1"]  # QB has 1 slot
        result = self.calc._calculate_need_multiplier("QB", roster, DEFAULT_ROSTER_SLOTS)
        assert result == pytest.approx(1.0)

    def test_flex_eligible_includes_flex_slot(self):
        """RB/WR/TE need includes the FLEX slot."""
        roster = self._empty_roster()
        # RB: 2 RB slots + 1 FLEX = 3 total, 0 filled
        # need = 1 + (3/3)*0.5 = 1.5
        result = self.calc._calculate_need_multiplier("RB", roster, DEFAULT_ROSTER_SLOTS)
        assert result == pytest.approx(1.5)

    def test_flex_filled_reduces_rb_need(self):
        """Filling the FLEX slot reduces need for FLEX-eligible positions."""
        roster = self._empty_roster()
        need_before = self.calc._calculate_need_multiplier("RB", roster, DEFAULT_ROSTER_SLOTS)

        roster["FLEX"] = ["wr1"]  # Someone in FLEX
        need_after = self.calc._calculate_need_multiplier("RB", roster, DEFAULT_ROSTER_SLOTS)

        assert need_after < need_before

    def test_qb_not_flex_eligible(self):
        """QB need does NOT include FLEX slot."""
        roster = self._empty_roster()
        # QB has 1 slot only (FLEX doesn't count)
        result = self.calc._calculate_need_multiplier("QB", roster, DEFAULT_ROSTER_SLOTS)
        # 1 + (1/1)*0.5 = 1.5
        assert result == pytest.approx(1.5)

    def test_k_not_flex_eligible(self):
        """K need does NOT include FLEX slot."""
        roster = self._empty_roster()
        result = self.calc._calculate_need_multiplier("K", roster, DEFAULT_ROSTER_SLOTS)
        assert result == pytest.approx(1.5)

    def test_dst_not_flex_eligible(self):
        """DST need does NOT include FLEX slot."""
        roster = self._empty_roster()
        result = self.calc._calculate_need_multiplier("DST", roster, DEFAULT_ROSTER_SLOTS)
        assert result == pytest.approx(1.5)

    def test_partially_filled_rb(self):
        """Partially filled RB slots give intermediate need."""
        roster = self._empty_roster()
        roster["RB"] = ["rb1"]
        # RB: 2 RB slots + 1 FLEX = 3 total, 1 filled
        # need = 1 + (2/3)*0.5 = 1.333...
        result = self.calc._calculate_need_multiplier("RB", roster, DEFAULT_ROSTER_SLOTS)
        assert result == pytest.approx(1 + (2 / 3) * 0.5)

    def test_zero_total_slots_returns_one(self):
        """Position with no slots in config returns 1.0."""
        roster = self._empty_roster()
        slots = {**DEFAULT_ROSTER_SLOTS}
        del slots["K"]
        result = self.calc._calculate_need_multiplier("K", roster, slots)
        assert result == 1.0


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
        self.calc = DynamicVORCalculator("half_ppr")

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
        """With no drafted players and empty roster, VOR = base * 1.0 * need."""
        player = _make_player("qb1", "QB", vor_half_ppr=40.0)
        result = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        r = result["qb1"]
        assert r.base_vor == 40.0
        assert r.scarcity_multiplier == 1.0
        # QB: 1 slot, 0 filled → need = 1.5
        assert r.need_multiplier == pytest.approx(1.5)
        assert r.dynamic_vor == pytest.approx(40.0 * 1.0 * 1.5)

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
        calc_std = DynamicVORCalculator("standard")
        calc_half = DynamicVORCalculator("half_ppr")

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
        self.calc = DynamicVORCalculator("half_ppr")

    def test_zero_base_vor(self):
        """Player with 0 base VOR gets 0 dynamic VOR regardless of multipliers."""
        player = _make_player("rb1", "RB", vor_half_ppr=0.0)
        result = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={"RB": 20},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        assert result["rb1"].dynamic_vor == 0.0
        assert result["rb1"].scarcity_multiplier > 1.0  # Scarcity still applies

    def test_negative_base_vor(self):
        """Negative VOR stays negative but is amplified by multipliers."""
        player = _make_player("rb1", "RB", vor_half_ppr=-5.0)
        result = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={"RB": 18},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        # Negative * positive multipliers → more negative
        assert result["rb1"].dynamic_vor < -5.0

    def test_missing_baseline_vor_defaults_to_zero(self):
        """Player without baseline_vor key gets 0.0."""
        player = {
            "player_id": "unknown",
            "name": "Unknown",
            "position": "RB",
            "team": "TST",
        }
        result = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
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
        # QB baseline=12, draft all 12
        result_12 = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={"QB": 12},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        # Draft more than baseline
        result_20 = self.calc.calculate_dynamic_vor(
            available_players=[player],
            drafted_positions={"QB": 20},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )
        assert result_12["qb1"].scarcity_multiplier == result_20["qb1"].scarcity_multiplier
        # QB weight=1.2, pct=1.0 → scarcity = 1 + 1.0*1.2 = 2.2
        assert result_12["qb1"].scarcity_multiplier == pytest.approx(2.2)


# ── DraftState Integration Tests ─────────────────────────────────────


class TestCalculateFromDraftState:
    def setup_method(self):
        self.calc = DynamicVORCalculator("half_ppr")

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
        controller.make_pick(0, "rb1")   # Team 0 picks (RB slot)
        controller.make_pick(1, "wr1")   # Team 1
        controller.make_pick(2, "qb1")   # Team 2
        controller.make_pick(3, "te1")   # Team 3

        # Round 2 (snake: 3,2,1,0)
        controller.make_pick(3, "wr2")
        controller.make_pick(2, "rb2")
        controller.make_pick(1, "qb2")
        controller.make_pick(0, "rb3")   # Team 0's second RB (fills RB2)

        # Round 3 (1,2,3,4)
        controller.make_pick(0, "rb4")   # Team 0 → goes to FLEX slot

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
        """Replicate the example from SIMULATION_ENGINE_MODULE.md."""
        calc = DynamicVORCalculator("half_ppr")

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
        )

        # Henry: scarcity = 1 + (15/36)*2.0 ≈ 1.833
        henry_r = result["henry"]
        assert henry_r.scarcity_multiplier == pytest.approx(1 + (15 / 36) * 2.0)
        # Henry: need = 1 + (2/3)*0.5 = 1.333 (1 of 3 slots filled)
        assert henry_r.need_multiplier == pytest.approx(1 + (2 / 3) * 0.5)

        # Wilson: scarcity = 1 + (10/36)*1.8 = 1.5
        wilson_r = result["wilson"]
        assert wilson_r.scarcity_multiplier == pytest.approx(1 + (10 / 36) * 1.8)
        # Wilson: same need (1 of 3 slots filled)
        assert wilson_r.need_multiplier == pytest.approx(1 + (2 / 3) * 0.5)

        # Henry should have higher dynamic VOR
        assert henry_r.dynamic_vor > wilson_r.dynamic_vor

    def test_dynamic_vor_equals_product(self):
        """dynamic_vor == base_vor * scarcity * need for every player."""
        calc = DynamicVORCalculator("half_ppr")
        players = list(_make_player_data().values())

        result = calc.calculate_dynamic_vor(
            available_players=players,
            drafted_positions={"QB": 3, "RB": 10, "WR": 8, "TE": 2},
            roster_slots=DEFAULT_ROSTER_SLOTS,
            team_roster={pos: [] for pos in DEFAULT_ROSTER_SLOTS},
        )

        for vor in result.values():
            expected = vor.base_vor * vor.scarcity_multiplier * vor.need_multiplier
            assert vor.dynamic_vor == pytest.approx(expected)
