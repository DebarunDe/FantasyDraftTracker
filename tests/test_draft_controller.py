"""Tests for draft controller - pick execution and state management."""

from pathlib import Path

import pytest

from src.draft_manager.draft_controller import DraftController
from src.draft_manager.draft_rules import DraftRules, ValidationError
from src.draft_manager.draft_state import DraftState, LeagueConfig, Pick
from src.draft_manager.roster_validator import RosterValidator


# ── Check data availability ──────────────────────────────────────────

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
PLAYER_FILE = PROCESSED_DIR / "players_2025.json"
requires_player_data = pytest.mark.skipif(
    not PLAYER_FILE.exists(),
    reason=f"Processed player data not found at {PLAYER_FILE}",
)


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


def _make_player_data():
    """Create a small but sufficient set of players with varied positions."""
    players = {}
    specs = [
        ("qb1", "QB"), ("qb2", "QB"), ("qb3", "QB"), ("qb4", "QB"),
        ("rb1", "RB"), ("rb2", "RB"), ("rb3", "RB"), ("rb4", "RB"),
        ("rb5", "RB"), ("rb6", "RB"), ("rb7", "RB"), ("rb8", "RB"),
        ("wr1", "WR"), ("wr2", "WR"), ("wr3", "WR"), ("wr4", "WR"),
        ("wr5", "WR"), ("wr6", "WR"), ("wr7", "WR"), ("wr8", "WR"),
        ("te1", "TE"), ("te2", "TE"), ("te3", "TE"), ("te4", "TE"),
        ("k1", "K"), ("k2", "K"), ("k3", "K"), ("k4", "K"),
        ("dst1", "DST"), ("dst2", "DST"), ("dst3", "DST"), ("dst4", "DST"),
    ]
    for pid, pos in specs:
        players[pid] = {
            "player_id": pid,
            "name": f"Player {pid}",
            "position": pos,
            "team": "TST",
            "projections": {
                "standard": 100.0,
                "half_ppr": 110.0,
                "full_ppr": 120.0,
            },
            "baseline_vor": {
                "standard": 20.0,
                "half_ppr": 22.0,
                "full_ppr": 24.0,
            },
        }
    return players


def _make_draft_state(league_size=4, draft_mode="simulation", **config_overrides):
    config = _make_league_config(
        league_size=league_size,
        draft_mode=draft_mode,
        **config_overrides,
    )
    players = _make_player_data()
    team_names = [f"Team {i}" for i in range(league_size)]
    return DraftState.create_new(
        league_config=config,
        team_names=team_names,
        human_team_id=0,
        player_data=players,
    )


def _make_controller(league_size=4, draft_mode="simulation", **config_overrides):
    state = _make_draft_state(
        league_size=league_size,
        draft_mode=draft_mode,
        **config_overrides,
    )
    return DraftController(state), state


# ── Init ─────────────────────────────────────────────────────────────


class TestDraftControllerInit:
    def test_creates_from_draft_state(self):
        ctrl, state = _make_controller()
        assert ctrl.draft_state is state

    def test_creates_rules_and_validator(self):
        ctrl, _ = _make_controller()
        assert isinstance(ctrl.rules, DraftRules)
        assert isinstance(ctrl.validator, RosterValidator)

    def test_is_complete_initially_false(self):
        ctrl, _ = _make_controller()
        assert ctrl.is_complete is False


# ── Make Pick (valid) ────────────────────────────────────────────────


class TestMakePick:
    def test_returns_pick_object(self):
        ctrl, _ = _make_controller()
        pick = ctrl.make_pick(0, "rb1")
        assert isinstance(pick, Pick)

    def test_pick_has_correct_fields(self):
        ctrl, _ = _make_controller()
        pick = ctrl.make_pick(0, "rb1")
        assert pick.pick_number == 1
        assert pick.round == 1
        assert pick.team_id == 0
        assert pick.player_id == "rb1"
        assert pick.slot == "RB"
        assert pick.timestamp  # non-empty

    def test_player_removed_from_available(self):
        ctrl, state = _make_controller()
        ctrl.make_pick(0, "rb1")
        assert "rb1" not in state.available_players

    def test_player_added_to_team_roster(self):
        ctrl, state = _make_controller()
        ctrl.make_pick(0, "rb1")
        team = state.get_team(0)
        assert "rb1" in team.roster["RB"]

    def test_pick_added_to_all_picks(self):
        ctrl, state = _make_controller()
        ctrl.make_pick(0, "rb1")
        assert len(state.all_picks) == 1
        assert state.all_picks[0].player_id == "rb1"

    def test_current_pick_advances(self):
        ctrl, state = _make_controller()
        ctrl.make_pick(0, "rb1")
        assert state.current_pick == 2

    def test_current_team_advances(self):
        ctrl, state = _make_controller()
        ctrl.make_pick(0, "rb1")
        assert state.current_team_id == 1

    def test_pick_added_to_team_picks_list(self):
        ctrl, state = _make_controller()
        ctrl.make_pick(0, "rb1")
        team = state.get_team(0)
        assert "rb1" in team.picks

    def test_slot_assignment_position_first(self):
        """First RB goes to RB slot."""
        ctrl, _ = _make_controller()
        pick = ctrl.make_pick(0, "rb1")
        assert pick.slot == "RB"

    def test_slot_assignment_flex(self):
        """Third RB goes to FLEX slot when RB slots are full."""
        ctrl, state = _make_controller()
        team = state.get_team(0)
        team.roster["RB"] = ["rb_x", "rb_y"]
        pick = ctrl.make_pick(0, "rb1")
        assert pick.slot == "FLEX"

    def test_slot_assignment_bench(self):
        """RB beyond FLEX goes to BENCH."""
        ctrl, state = _make_controller()
        team = state.get_team(0)
        team.roster["RB"] = ["rb_x", "rb_y"]
        team.roster["FLEX"] = ["rb_z"]
        pick = ctrl.make_pick(0, "rb1")
        assert pick.slot == "BENCH"

    def test_qb_skips_flex_goes_to_bench(self):
        """Second QB goes directly to BENCH (not FLEX)."""
        ctrl, state = _make_controller()
        team = state.get_team(0)
        team.roster["QB"] = ["qb_x"]
        pick = ctrl.make_pick(0, "qb1")
        assert pick.slot == "BENCH"


# ── Make Pick (invalid) ──────────────────────────────────────────────


class TestMakePickValidation:
    def test_wrong_team_turn(self):
        ctrl, _ = _make_controller()
        with pytest.raises(ValidationError, match="Not team 1's turn"):
            ctrl.make_pick(1, "rb1")

    def test_player_already_drafted(self):
        ctrl, _ = _make_controller()
        ctrl.make_pick(0, "rb1")
        with pytest.raises(ValidationError, match="already been drafted"):
            ctrl.make_pick(1, "rb1")

    def test_player_not_in_database(self):
        ctrl, _ = _make_controller()
        with pytest.raises(ValidationError, match="not found"):
            ctrl.make_pick(0, "nonexistent_player")

    def test_position_full_no_flex_no_bench(self):
        ctrl, state = _make_controller()
        team = state.get_team(0)
        team.roster["RB"] = ["x1", "x2"]
        team.roster["FLEX"] = ["x3"]
        team.roster["BENCH"] = [f"b{i}" for i in range(6)]
        with pytest.raises(ValidationError, match="Cannot draft another RB"):
            ctrl.make_pick(0, "rb1")

    def test_draft_already_complete(self):
        ctrl, state = _make_controller()
        state.is_complete = True
        with pytest.raises(ValidationError, match="Draft is already complete"):
            ctrl.make_pick(0, "rb1")

    def test_rollback_on_available_pool_inconsistency(self):
        """If player is removed from available_players mid-mutation, state rolls back."""
        ctrl, state = _make_controller()
        team = state.get_team(0)
        # Remove from available_players to create inconsistency
        state.available_players.remove("rb1")
        original_picks = len(state.all_picks)
        original_roster = list(team.roster["RB"])
        original_team_picks = list(team.picks)
        # Patch validate_pick to bypass the availability check
        ctrl.rules.validate_pick = lambda _tid, _pid: (True, None)
        with pytest.raises(ValidationError, match="not in available pool"):
            ctrl.make_pick(0, "rb1")
        # Verify rollback: state unchanged
        assert len(state.all_picks) == original_picks
        assert team.roster["RB"] == original_roster
        assert team.picks == original_team_picks


# ── Multiple Picks ───────────────────────────────────────────────────


class TestMultiplePicks:
    def test_two_consecutive_picks(self):
        ctrl, state = _make_controller()
        ctrl.make_pick(0, "rb1")
        ctrl.make_pick(1, "wr1")
        assert state.current_pick == 3
        assert len(state.all_picks) == 2

    def test_full_round(self):
        """All 4 teams pick in round 1."""
        ctrl, state = _make_controller(league_size=4)
        ctrl.make_pick(0, "rb1")
        ctrl.make_pick(1, "rb2")
        ctrl.make_pick(2, "wr1")
        ctrl.make_pick(3, "wr2")
        assert state.current_round == 2
        assert state.current_pick == 5

    def test_snake_order_round_2(self):
        """Round 2 reverses: team 3 picks first."""
        ctrl, state = _make_controller(league_size=4)
        # Round 1: teams 0, 1, 2, 3
        ctrl.make_pick(0, "rb1")
        ctrl.make_pick(1, "rb2")
        ctrl.make_pick(2, "wr1")
        ctrl.make_pick(3, "wr2")
        # Round 2: teams 3, 2, 1, 0
        assert state.current_team_id == 3
        ctrl.make_pick(3, "rb3")
        assert state.current_team_id == 2
        ctrl.make_pick(2, "rb4")
        assert state.current_team_id == 1
        ctrl.make_pick(1, "te1")
        assert state.current_team_id == 0

    def test_multiple_rounds_state_consistency(self):
        """After 2 rounds (8 picks in 4-team league), state is consistent."""
        ctrl, state = _make_controller(league_size=4)
        picks = ["rb1", "rb2", "wr1", "wr2", "rb3", "rb4", "wr3", "wr4"]
        teams = [0, 1, 2, 3, 3, 2, 1, 0]  # Snake order
        for team_id, pid in zip(teams, picks):
            ctrl.make_pick(team_id, pid)
        assert len(state.all_picks) == 8
        assert state.current_round == 3
        for pid in picks:
            assert pid not in state.available_players


# ── Draft Completion ─────────────────────────────────────────────────


class TestDraftCompletion:
    def test_draft_completes_after_all_picks(self):
        """Use a tiny 2-team, 1-round draft to verify completion."""
        ctrl, state = _make_controller(
            league_size=2,
            roster_slots={
                "QB": 1, "RB": 0, "WR": 0, "TE": 0,
                "FLEX": 0, "DST": 0, "K": 0, "BENCH": 0,
            },
        )
        # 2 teams * 1 round = 2 picks total
        ctrl.make_pick(0, "qb1")
        ctrl.make_pick(1, "qb2")
        assert ctrl.is_complete is True
        assert state.is_complete is True
        assert state.completed_at is not None

    def test_cannot_pick_after_complete(self):
        ctrl, state = _make_controller(
            league_size=2,
            roster_slots={
                "QB": 1, "RB": 0, "WR": 0, "TE": 0,
                "FLEX": 0, "DST": 0, "K": 0, "BENCH": 0,
            },
        )
        ctrl.make_pick(0, "qb1")
        ctrl.make_pick(1, "qb2")
        with pytest.raises(ValidationError, match="Draft is already complete"):
            ctrl.make_pick(0, "qb3")

    def test_is_complete_property(self):
        ctrl, _ = _make_controller()
        assert ctrl.is_complete is False


# ── Getters ──────────────────────────────────────────────────────────


class TestGetters:
    def test_get_current_team(self):
        ctrl, _ = _make_controller()
        team = ctrl.get_current_team()
        assert team.team_id == 0
        assert team.team_name == "Team 0"

    def test_get_current_team_after_pick(self):
        ctrl, _ = _make_controller()
        ctrl.make_pick(0, "rb1")
        team = ctrl.get_current_team()
        assert team.team_id == 1

    def test_get_available_players_all(self):
        ctrl, state = _make_controller()
        available = ctrl.get_available_players()
        assert len(available) == len(state.available_players)
        assert all("player_id" in p for p in available)
        assert all("name" in p for p in available)

    def test_get_available_players_after_pick(self):
        ctrl, _ = _make_controller()
        initial_count = len(ctrl.get_available_players())
        ctrl.make_pick(0, "rb1")
        assert len(ctrl.get_available_players()) == initial_count - 1

    def test_get_available_players_by_position(self):
        ctrl, _ = _make_controller()
        qbs = ctrl.get_available_players(position="QB")
        assert all(p["position"] == "QB" for p in qbs)
        assert len(qbs) == 4  # qb1, qb2, qb3, qb4

    def test_get_team_roster_empty(self):
        ctrl, _ = _make_controller()
        roster = ctrl.get_team_roster(0)
        assert "QB" in roster
        assert roster["QB"] == []

    def test_get_team_roster_after_pick(self):
        ctrl, _ = _make_controller()
        ctrl.make_pick(0, "rb1")
        roster = ctrl.get_team_roster(0)
        assert len(roster["RB"]) == 1
        assert roster["RB"][0]["player_id"] == "rb1"
        assert roster["RB"][0]["name"] == "Player rb1"


# ── Manual Tracker Mode ──────────────────────────────────────────────


class TestManualTrackerMode:
    def test_any_team_can_pick(self):
        """In manual tracker mode, turn order is not enforced."""
        ctrl, state = _make_controller(draft_mode="manual_tracker")
        pick = ctrl.make_pick(2, "rb1")
        assert pick.team_id == 2
        assert "rb1" in state.get_team(2).picks

    def test_state_still_advances(self):
        """Even in manual mode, current_pick/current_team advance."""
        ctrl, state = _make_controller(draft_mode="manual_tracker")
        ctrl.make_pick(2, "rb1")
        assert state.current_pick == 2


# ── Draft Summary ────────────────────────────────────────────────────


class TestGetDraftSummary:
    def test_returns_error_if_not_complete(self):
        ctrl, _ = _make_controller()
        summary = ctrl.get_draft_summary()
        assert "error" in summary

    def test_returns_summary_when_complete(self):
        ctrl, state = _make_controller(
            league_size=2,
            roster_slots={
                "QB": 1, "RB": 0, "WR": 0, "TE": 0,
                "FLEX": 0, "DST": 0, "K": 0, "BENCH": 0,
            },
        )
        ctrl.make_pick(0, "qb1")
        ctrl.make_pick(1, "qb2")
        summary = ctrl.get_draft_summary()
        assert summary["draft_id"] == state.draft_id
        assert summary["total_picks"] == 2
        assert len(summary["teams"]) == 2

    def test_projected_points_excludes_bench(self):
        ctrl, _ = _make_controller(
            league_size=2,
            roster_slots={
                "QB": 1, "RB": 0, "WR": 0, "TE": 0,
                "FLEX": 0, "DST": 0, "K": 0, "BENCH": 1,
            },
        )
        # Round 1: Team 0 gets qb1 (QB starter), Team 1 gets qb2 (QB starter)
        ctrl.make_pick(0, "qb1")
        ctrl.make_pick(1, "qb2")
        # Round 2 (snake): Team 1 gets rb1 (BENCH), Team 0 gets rb2 (BENCH)
        ctrl.make_pick(1, "rb1")
        ctrl.make_pick(0, "rb2")
        summary = ctrl.get_draft_summary()
        # Points should only include the QB (110.0 half_ppr), not bench
        team0 = summary["teams"][0]
        assert team0["projected_points"] == 110.0


# ── Pick Slot Field ──────────────────────────────────────────────────


class TestPickSlotField:
    def test_pick_has_slot(self):
        ctrl, _ = _make_controller()
        pick = ctrl.make_pick(0, "rb1")
        assert pick.slot == "RB"

    def test_pick_create_with_slot(self):
        """Pick.create() accepts slot parameter."""
        pick = Pick.create(
            pick_number=1, round=1, team_id=0,
            player_id="p1", slot="FLEX",
        )
        assert pick.slot == "FLEX"

    def test_pick_create_without_slot_defaults_none(self):
        """Backward compatibility: slot defaults to None."""
        pick = Pick.create(pick_number=1, round=1, team_id=0, player_id="p1")
        assert pick.slot is None

    def test_pick_constructor_without_slot_defaults_none(self):
        """Backward compatibility: direct constructor still works."""
        pick = Pick(
            pick_number=1, round=1, team_id=0,
            player_id="p1", timestamp="2025-01-01",
        )
        assert pick.slot is None


# ── Integration with Real Data ───────────────────────────────────────


@requires_player_data
class TestIntegrationWithRealData:
    def test_make_pick_with_real_data(self):
        """Create a draft from real data and make one pick."""
        from src.draft_manager.draft_initializer import DraftInitializer

        init = DraftInitializer()
        state = init.create_draft(
            league_size=12,
            scoring_format="half_ppr",
            roster_slots=DraftInitializer.get_default_roster_slots(),
            team_names=[f"Team {i + 1}" for i in range(12)],
            human_team_id=0,
            data_year=2025,
        )
        ctrl = DraftController(state)

        pid = state.available_players[0]
        pick = ctrl.make_pick(0, pid)

        assert pick.player_id == pid
        assert state.current_pick == 2
        assert pid not in state.available_players

    def test_full_round_with_real_data(self):
        """Complete one full round (12 picks) with real data."""
        from src.draft_manager.draft_initializer import DraftInitializer

        init = DraftInitializer()
        state = init.create_draft(
            league_size=12,
            scoring_format="half_ppr",
            roster_slots=DraftInitializer.get_default_roster_slots(),
            team_names=[f"Team {i + 1}" for i in range(12)],
            human_team_id=0,
            data_year=2025,
        )
        ctrl = DraftController(state)

        for _ in range(12):
            pid = state.available_players[0]
            ctrl.make_pick(state.current_team_id, pid)

        assert state.current_round == 2
        assert len(state.all_picks) == 12
