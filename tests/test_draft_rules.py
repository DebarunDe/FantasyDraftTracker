"""Tests for draft rules and pick validation."""

import pytest

from src.draft_manager.draft_rules import DraftRules, ValidationError
from src.draft_manager.draft_state import DraftState, LeagueConfig, TeamRoster


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
    """Create a small set of players with varied positions."""
    players = {}
    specs = [
        ("qb1", "QB"), ("qb2", "QB"),
        ("rb1", "RB"), ("rb2", "RB"), ("rb3", "RB"), ("rb4", "RB"),
        ("wr1", "WR"), ("wr2", "WR"), ("wr3", "WR"),
        ("te1", "TE"), ("te2", "TE"),
        ("k1", "K"), ("k2", "K"),
        ("dst1", "DST"), ("dst2", "DST"),
    ]
    for pid, pos in specs:
        players[pid] = {
            "player_id": pid,
            "name": f"Player {pid}",
            "position": pos,
            "team": "TST",
        }
    return players


def _make_draft_state(**config_overrides):
    config = _make_league_config(**config_overrides)
    players = _make_player_data()
    team_names = [f"Team {i}" for i in range(config.league_size)]
    return DraftState.create_new(
        league_config=config,
        team_names=team_names,
        human_team_id=0,
        player_data=players,
    )


# ── Valid Picks ──────────────────────────────────────────────────────

class TestValidPicks:
    def test_valid_first_pick(self):
        state = _make_draft_state()
        rules = DraftRules(state)
        valid, error = rules.validate_pick(0, "rb1")
        assert valid is True
        assert error is None

    def test_valid_pick_any_position(self):
        state = _make_draft_state()
        rules = DraftRules(state)
        for pid in ["qb1", "rb1", "wr1", "te1", "k1", "dst1"]:
            valid, error = rules.validate_pick(0, pid)
            assert valid is True, f"Expected {pid} to be valid, got: {error}"


# ── Invalid Picks ────────────────────────────────────────────────────

class TestInvalidPicks:
    def test_wrong_team_turn(self):
        state = _make_draft_state()
        rules = DraftRules(state)
        # Current team is 0, trying to pick as team 1
        valid, error = rules.validate_pick(1, "rb1")
        assert valid is False
        assert "Not team 1's turn" in error

    def test_player_already_drafted(self):
        state = _make_draft_state()
        rules = DraftRules(state)
        # Simulate drafting rb1
        state.available_players.remove("rb1")
        valid, error = rules.validate_pick(0, "rb1")
        assert valid is False
        assert "already been drafted" in error

    def test_player_not_in_database(self):
        state = _make_draft_state()
        rules = DraftRules(state)
        valid, error = rules.validate_pick(0, "nonexistent_player")
        assert valid is False
        assert "not found" in error

    def test_player_missing_position(self):
        """Player in data but with no position field should be rejected."""
        state = _make_draft_state()
        rules = DraftRules(state)
        # Add a malformed player with no position
        state.player_data["bad_player"] = {"player_id": "bad_player", "name": "Bad"}
        state.available_players.append("bad_player")
        valid, error = rules.validate_pick(0, "bad_player")
        assert valid is False
        assert "no position defined" in error


# ── Position Limits ──────────────────────────────────────────────────

class TestPositionLimits:
    def test_allows_within_limit(self):
        state = _make_draft_state()
        rules = DraftRules(state)
        # QB limit is 1, nothing drafted yet
        valid, _ = rules.validate_pick(0, "qb1")
        assert valid is True

    def test_allows_flex_overflow(self):
        """RB beyond position limit goes to FLEX."""
        state = _make_draft_state()
        rules = DraftRules(state)
        team = state.get_team(0)
        # Fill RB slots (limit 2)
        team.roster["RB"] = ["rb1", "rb2"]
        # Third RB should still be valid (FLEX slot available)
        valid, _ = rules._validate_position_limit(team, "RB")
        assert valid is True

    def test_allows_bench_overflow(self):
        """RB beyond position+FLEX limit goes to BENCH."""
        state = _make_draft_state()
        rules = DraftRules(state)
        team = state.get_team(0)
        team.roster["RB"] = ["rb1", "rb2"]
        team.roster["FLEX"] = ["rb3"]
        # Fourth RB should go to bench
        valid, _ = rules._validate_position_limit(team, "RB")
        assert valid is True

    def test_rejects_when_all_full(self):
        """Reject when position, FLEX, and BENCH are all full."""
        state = _make_draft_state()
        rules = DraftRules(state)
        team = state.get_team(0)
        team.roster["RB"] = ["rb1", "rb2"]
        team.roster["FLEX"] = ["rb3"]
        team.roster["BENCH"] = [f"b{i}" for i in range(6)]
        valid, error = rules._validate_position_limit(team, "RB")
        assert valid is False
        assert "Cannot draft another RB" in error

    def test_qb_no_flex_eligible(self):
        """QB can't go to FLEX; only bench after position full."""
        state = _make_draft_state()
        rules = DraftRules(state)
        team = state.get_team(0)
        team.roster["QB"] = ["qb1"]
        # Second QB should go to bench (not FLEX)
        valid, _ = rules._validate_position_limit(team, "QB")
        assert valid is True  # bench available

    def test_qb_no_flex_or_bench(self):
        state = _make_draft_state()
        rules = DraftRules(state)
        team = state.get_team(0)
        team.roster["QB"] = ["qb1"]
        team.roster["BENCH"] = [f"b{i}" for i in range(6)]
        valid, error = rules._validate_position_limit(team, "QB")
        assert valid is False
        assert "Cannot draft another QB" in error

    def test_wr_to_flex(self):
        state = _make_draft_state()
        rules = DraftRules(state)
        team = state.get_team(0)
        team.roster["WR"] = ["wr1", "wr2"]
        valid, _ = rules._validate_position_limit(team, "WR")
        assert valid is True  # FLEX slot open

    def test_te_to_flex(self):
        state = _make_draft_state()
        rules = DraftRules(state)
        team = state.get_team(0)
        team.roster["TE"] = ["te1"]
        valid, _ = rules._validate_position_limit(team, "TE")
        assert valid is True  # FLEX slot open


# ── Manual Tracker Mode ──────────────────────────────────────────────

class TestManualTrackerMode:
    def test_allows_any_team_to_pick(self):
        """In manual tracker mode, any team can pick regardless of turn."""
        state = _make_draft_state(draft_mode="manual_tracker")
        rules = DraftRules(state)
        # Team 3 picking when it's team 0's turn
        valid, error = rules.validate_pick(3, "rb1")
        assert valid is True


# ── Draft Complete ───────────────────────────────────────────────────

class TestIsDraftComplete:
    def test_not_complete_no_picks(self):
        state = _make_draft_state()
        rules = DraftRules(state)
        assert rules.is_draft_complete() is False

    def test_complete_after_all_picks(self):
        state = _make_draft_state(league_size=2)
        rules = DraftRules(state)
        total = state.league_config.league_size * state.league_config.total_rounds()
        # Add dummy picks
        from src.draft_manager.draft_state import Pick
        for i in range(total):
            state.all_picks.append(
                Pick(pick_number=i + 1, round=1, team_id=0,
                     player_id=f"p{i}", timestamp="t")
            )
        assert rules.is_draft_complete() is True
