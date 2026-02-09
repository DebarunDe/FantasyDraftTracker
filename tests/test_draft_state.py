"""Tests for draft state data models."""

import pytest

from src.draft_manager.draft_state import (
    DraftState,
    LeagueConfig,
    Pick,
    TeamRoster,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _make_league_config(**overrides):
    defaults = {
        "league_id": "test_league",
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


def _make_player_data(count=20):
    """Create minimal player data dict."""
    players = {}
    positions = ["QB", "RB", "WR", "TE", "K", "DST"]
    for i in range(count):
        pos = positions[i % len(positions)]
        pid = f"player_{i}_{pos.lower()}"
        players[pid] = {
            "player_id": pid,
            "name": f"Player {i}",
            "position": pos,
            "team": "TST",
        }
    return players


def _make_draft_state(league_size=4, player_count=60, **config_overrides):
    config = _make_league_config(league_size=league_size, **config_overrides)
    players = _make_player_data(player_count)
    team_names = [f"Team {i}" for i in range(league_size)]
    return DraftState.create_new(
        league_config=config,
        team_names=team_names,
        human_team_id=0,
        player_data=players,
    )


# ── TeamRoster ───────────────────────────────────────────────────────

class TestTeamRoster:
    def test_empty_roster_count(self):
        roster = TeamRoster(team_id=0, team_name="T0", is_human=True,
                            roster={"QB": [], "RB": []})
        assert roster.get_roster_count("QB") == 0
        assert roster.get_roster_count("RB") == 0
        assert roster.get_roster_count("WR") == 0  # not in dict

    def test_add_player(self):
        roster = TeamRoster(team_id=0, team_name="T0", is_human=True,
                            roster={"QB": []})
        roster.add_player("qb1", "QB")
        assert roster.get_roster_count("QB") == 1
        assert "qb1" in roster.picks

    def test_add_player_new_slot(self):
        roster = TeamRoster(team_id=0, team_name="T0", is_human=True, roster={})
        roster.add_player("rb1", "BENCH")
        assert roster.get_roster_count("BENCH") == 1

    def test_get_total_picks(self):
        roster = TeamRoster(team_id=0, team_name="T0", is_human=True,
                            roster={"QB": []})
        assert roster.get_total_picks() == 0
        roster.add_player("p1", "QB")
        roster.add_player("p2", "BENCH")
        assert roster.get_total_picks() == 2


# ── Pick ─────────────────────────────────────────────────────────────

class TestPick:
    def test_create(self):
        pick = Pick.create(pick_number=1, round=1, team_id=0, player_id="p1")
        assert pick.pick_number == 1
        assert pick.round == 1
        assert pick.team_id == 0
        assert pick.player_id == "p1"
        assert pick.timestamp  # non-empty ISO string


# ── LeagueConfig ─────────────────────────────────────────────────────

class TestLeagueConfig:
    def test_total_rounds(self):
        config = _make_league_config()
        # QB=1 + RB=2 + WR=2 + TE=1 + FLEX=1 + DST=1 + K=1 + BENCH=6 = 15
        assert config.total_rounds() == 15

    def test_total_rounds_empty_roster_slots_raises(self):
        config = _make_league_config(roster_slots={})
        with pytest.raises(ValueError, match="roster_slots cannot be empty"):
            config.total_rounds()

    def test_get_position_limit(self):
        config = _make_league_config()
        assert config.get_position_limit("QB") == 1
        assert config.get_position_limit("RB") == 2
        assert config.get_position_limit("BENCH") == 6
        assert config.get_position_limit("UNKNOWN") == 0


# ── DraftState.create_new ────────────────────────────────────────────

class TestDraftStateCreation:
    def test_creates_correct_number_of_teams(self):
        state = _make_draft_state(league_size=4)
        assert len(state.teams) == 4

    def test_human_team_flagged(self):
        state = _make_draft_state(league_size=4)
        assert state.teams[0].is_human is True
        assert all(t.is_human is False for t in state.teams[1:])

    def test_initial_state(self):
        state = _make_draft_state()
        assert state.current_pick == 1
        assert state.current_round == 1
        assert state.current_team_id == 0
        assert state.is_complete is False

    def test_all_players_available(self):
        state = _make_draft_state(player_count=30)
        assert len(state.available_players) == 30

    def test_empty_rosters(self):
        state = _make_draft_state()
        for team in state.teams:
            assert team.get_total_picks() == 0

    def test_draft_order(self):
        state = _make_draft_state(league_size=6)
        assert state.draft_order == [0, 1, 2, 3, 4, 5]

    def test_unique_draft_id(self):
        s1 = _make_draft_state()
        s2 = _make_draft_state()
        assert s1.draft_id != s2.draft_id

    def test_team_rosters_have_all_slots(self):
        state = _make_draft_state()
        for team in state.teams:
            for pos in state.league_config.roster_slots:
                assert pos in team.roster

    def test_team_names_mismatch_raises(self):
        config = _make_league_config(league_size=4)
        with pytest.raises(ValueError, match="team_names length"):
            DraftState.create_new(
                league_config=config,
                team_names=["T1", "T2"],
                human_team_id=0,
                player_data=_make_player_data(),
            )

    def test_human_team_id_out_of_range_raises(self):
        config = _make_league_config(league_size=4)
        with pytest.raises(ValueError, match="human_team_id"):
            DraftState.create_new(
                league_config=config,
                team_names=[f"T{i}" for i in range(4)],
                human_team_id=5,
                player_data=_make_player_data(),
            )


# ── DraftState methods ───────────────────────────────────────────────

class TestDraftStateMethods:
    def test_get_current_team(self):
        state = _make_draft_state()
        assert state.get_current_team().team_id == 0

    def test_get_team(self):
        state = _make_draft_state(league_size=4)
        assert state.get_team(2).team_name == "Team 2"

    def test_is_player_available(self):
        state = _make_draft_state()
        pid = state.available_players[0]
        assert state.is_player_available(pid) is True
        assert state.is_player_available("nonexistent") is False

    def test_get_player_info(self):
        state = _make_draft_state()
        pid = state.available_players[0]
        info = state.get_player_info(pid)
        assert info["player_id"] == pid
        assert "name" in info
        assert "position" in info

    def test_get_player_info_missing(self):
        state = _make_draft_state()
        assert state.get_player_info("no_such_player") == {}


# ── Snake Draft Order ────────────────────────────────────────────────

class TestSnakeDraftOrder:
    def test_round_1_forward(self):
        """Round 1: 0 -> 1 -> 2 -> 3"""
        state = _make_draft_state(league_size=4)
        order = [state.current_team_id]
        for _ in range(3):
            state.advance_to_next_pick()
            order.append(state.current_team_id)
        assert order == [0, 1, 2, 3]

    def test_round_2_reverse(self):
        """Round 2: 3 -> 2 -> 1 -> 0"""
        state = _make_draft_state(league_size=4)
        # Complete round 1
        for _ in range(4):
            state.advance_to_next_pick()
        # Now round 2
        order = [state.current_team_id]
        for _ in range(3):
            state.advance_to_next_pick()
            order.append(state.current_team_id)
        assert order == [3, 2, 1, 0]

    def test_round_3_forward_again(self):
        """Round 3: 0 -> 1 -> 2 -> 3"""
        state = _make_draft_state(league_size=4)
        for _ in range(8):
            state.advance_to_next_pick()
        order = [state.current_team_id]
        for _ in range(3):
            state.advance_to_next_pick()
            order.append(state.current_team_id)
        assert order == [0, 1, 2, 3]

    def test_round_tracking(self):
        state = _make_draft_state(league_size=4)
        assert state.current_round == 1
        for _ in range(4):
            state.advance_to_next_pick()
        assert state.current_round == 2
        for _ in range(4):
            state.advance_to_next_pick()
        assert state.current_round == 3

    def test_pick_number_increments(self):
        state = _make_draft_state(league_size=4)
        assert state.current_pick == 1
        state.advance_to_next_pick()
        assert state.current_pick == 2
        state.advance_to_next_pick()
        assert state.current_pick == 3

    def test_12_team_snake(self):
        """Full round in a 12-team league."""
        state = _make_draft_state(league_size=12, player_count=200)
        # Round 1
        r1 = [state.current_team_id]
        for _ in range(11):
            state.advance_to_next_pick()
            r1.append(state.current_team_id)
        assert r1 == list(range(12))
        # Round 2
        r2 = []
        for _ in range(12):
            state.advance_to_next_pick()
            r2.append(state.current_team_id)
        assert r2 == list(range(11, -1, -1))


# ── Draft Completion ─────────────────────────────────────────────────

class TestDraftCompletion:
    def test_not_complete_at_start(self):
        state = _make_draft_state()
        assert state.check_if_complete() is False

    def test_complete_after_all_picks(self):
        state = _make_draft_state(league_size=2, player_count=60)
        total = state.league_config.league_size * state.league_config.total_rounds()
        for _ in range(total):
            state.advance_to_next_pick()
        assert state.check_if_complete() is True
        assert state.completed_at is not None

    def test_completed_at_set_once(self):
        state = _make_draft_state(league_size=2, player_count=60)
        total = state.league_config.league_size * state.league_config.total_rounds()
        for _ in range(total):
            state.advance_to_next_pick()
        state.check_if_complete()
        first_time = state.completed_at
        state.check_if_complete()
        assert state.completed_at == first_time

    def test_advance_noop_after_complete(self):
        """advance_to_next_pick() should not change state once draft is complete."""
        state = _make_draft_state(league_size=2, player_count=60)
        total = state.league_config.league_size * state.league_config.total_rounds()
        for _ in range(total):
            state.advance_to_next_pick()
        state.check_if_complete()
        assert state.is_complete is True
        pick_before = state.current_pick
        state.advance_to_next_pick()
        assert state.current_pick == pick_before
