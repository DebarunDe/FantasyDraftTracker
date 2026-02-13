"""Tests for state persistence - save/load draft state to/from JSON."""

import json
from pathlib import Path

import pytest

from src.draft_manager.draft_controller import DraftController
from src.draft_manager.draft_initializer import DraftInitializer
from src.draft_manager.draft_state import DraftState, LeagueConfig, Pick, TeamRoster
from src.draft_manager.state_persistence import StatePersistence


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
    """Create a small set of players for testing."""
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


@pytest.fixture
def tmp_storage(tmp_path):
    """Provide a temporary directory for draft storage."""
    return tmp_path / "drafts"


@pytest.fixture
def persistence(tmp_storage):
    """Provide a StatePersistence instance using tmp storage."""
    return StatePersistence(storage_dir=tmp_storage)


@pytest.fixture
def draft_state():
    """Provide a fresh draft state."""
    return _make_draft_state()


# ── Init ─────────────────────────────────────────────────────────────


class TestStatePersistenceInit:
    def test_creates_storage_dir(self, tmp_path):
        storage = tmp_path / "new_dir" / "nested"
        StatePersistence(storage_dir=storage)
        assert storage.exists()
        assert storage.is_dir()

    def test_uses_default_dir_when_none(self):
        p = StatePersistence()
        from src.draft_manager.config import DRAFTS_DIR
        assert p.storage_dir == DRAFTS_DIR

    def test_existing_dir_is_fine(self, tmp_storage):
        tmp_storage.mkdir(parents=True)
        p = StatePersistence(storage_dir=tmp_storage)
        assert p.storage_dir == tmp_storage


# ── Save Draft ───────────────────────────────────────────────────────


class TestSaveDraft:
    def test_returns_file_path(self, persistence, draft_state):
        path = persistence.save_draft(draft_state)
        assert isinstance(path, Path)
        assert path.exists()

    def test_file_name_contains_draft_id(self, persistence, draft_state):
        path = persistence.save_draft(draft_state)
        assert draft_state.draft_id in path.name

    def test_file_is_valid_json(self, persistence, draft_state):
        path = persistence.save_draft(draft_state)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_json_has_required_keys(self, persistence, draft_state):
        path = persistence.save_draft(draft_state)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        required = {
            "draft_id", "league_config", "draft_start_time",
            "current_pick", "current_round", "current_team_id",
            "draft_order", "teams", "all_picks", "available_players",
            "player_data", "is_complete", "completed_at",
        }
        assert required.issubset(data.keys())

    def test_league_config_serialized(self, persistence, draft_state):
        path = persistence.save_draft(draft_state)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        lc = data["league_config"]
        assert lc["league_id"] == "test"
        assert lc["league_size"] == 4
        assert lc["scoring_format"] == "half_ppr"
        assert lc["draft_type"] == "snake"
        assert lc["draft_mode"] == "simulation"
        assert lc["data_year"] == 2025
        assert lc["roster_slots"]["QB"] == 1

    def test_teams_serialized(self, persistence, draft_state):
        path = persistence.save_draft(draft_state)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["teams"]) == 4
        team = data["teams"][0]
        assert team["team_id"] == 0
        assert team["team_name"] == "Team 0"
        assert team["is_human"] is True
        assert "QB" in team["roster"]

    def test_player_data_preserved(self, persistence, draft_state):
        path = persistence.save_draft(draft_state)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "qb1" in data["player_data"]
        assert data["player_data"]["qb1"]["position"] == "QB"

    def test_creates_active_draft_symlink(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        active = persistence.storage_dir / "active_draft.json"
        assert active.exists()
        assert active.is_symlink()

    def test_active_draft_points_to_saved_file(self, persistence, draft_state):
        path = persistence.save_draft(draft_state)
        active = persistence.storage_dir / "active_draft.json"
        # Symlink is relative, so resolve both to compare
        assert active.resolve() == path.resolve()

    def test_overwrite_on_re_save(self, persistence, draft_state):
        """Saving the same draft twice overwrites the file."""
        path1 = persistence.save_draft(draft_state)
        # Modify state
        draft_state.current_pick = 5
        path2 = persistence.save_draft(draft_state)
        assert path1 == path2
        with open(path2, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["current_pick"] == 5


# ── Save After Picks ────────────────────────────────────────────────


class TestSaveAfterPicks:
    def test_saves_picks_correctly(self, persistence, draft_state):
        ctrl = DraftController(draft_state)
        ctrl.make_pick(0, "rb1")
        ctrl.make_pick(1, "wr1")

        path = persistence.save_draft(draft_state)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["all_picks"]) == 2
        assert data["all_picks"][0]["player_id"] == "rb1"
        assert data["all_picks"][0]["slot"] == "RB"
        assert data["all_picks"][1]["player_id"] == "wr1"

    def test_saves_updated_available_players(self, persistence, draft_state):
        ctrl = DraftController(draft_state)
        ctrl.make_pick(0, "rb1")

        path = persistence.save_draft(draft_state)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "rb1" not in data["available_players"]

    def test_saves_updated_team_rosters(self, persistence, draft_state):
        ctrl = DraftController(draft_state)
        ctrl.make_pick(0, "rb1")

        path = persistence.save_draft(draft_state)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        team0 = data["teams"][0]
        assert "rb1" in team0["roster"]["RB"]
        assert "rb1" in team0["picks"]

    def test_saves_advanced_state(self, persistence, draft_state):
        ctrl = DraftController(draft_state)
        ctrl.make_pick(0, "rb1")

        path = persistence.save_draft(draft_state)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["current_pick"] == 2
        assert data["current_team_id"] == 1


# ── Load Draft ───────────────────────────────────────────────────────


class TestLoadDraft:
    def test_returns_draft_state(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)
        assert isinstance(loaded, DraftState)

    def test_returns_none_for_missing_id(self, persistence):
        loaded = persistence.load_draft("nonexistent-id")
        assert loaded is None

    def test_returns_none_for_corrupt_file(self, persistence):
        """Corrupt JSON file returns None instead of raising."""
        corrupt = persistence.storage_dir / "draft_bad-id.json"
        corrupt.write_text("not valid json{{{")
        loaded = persistence.load_draft("bad-id")
        assert loaded is None

    def test_draft_id_matches(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)
        assert loaded.draft_id == draft_state.draft_id

    def test_league_config_matches(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)
        lc = loaded.league_config
        assert lc.league_id == draft_state.league_config.league_id
        assert lc.league_size == draft_state.league_config.league_size
        assert lc.scoring_format == draft_state.league_config.scoring_format
        assert lc.draft_type == draft_state.league_config.draft_type
        assert lc.draft_mode == draft_state.league_config.draft_mode
        assert lc.data_year == draft_state.league_config.data_year
        assert lc.roster_slots == draft_state.league_config.roster_slots

    def test_current_state_matches(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)
        assert loaded.current_pick == draft_state.current_pick
        assert loaded.current_round == draft_state.current_round
        assert loaded.current_team_id == draft_state.current_team_id

    def test_draft_order_matches(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)
        assert loaded.draft_order == draft_state.draft_order

    def test_teams_match(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)
        assert len(loaded.teams) == len(draft_state.teams)
        for orig, ld in zip(draft_state.teams, loaded.teams):
            assert ld.team_id == orig.team_id
            assert ld.team_name == orig.team_name
            assert ld.is_human == orig.is_human
            assert ld.roster == orig.roster
            assert ld.picks == orig.picks

    def test_available_players_match(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)
        assert loaded.available_players == draft_state.available_players

    def test_player_data_matches(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)
        assert loaded.player_data == draft_state.player_data

    def test_is_complete_matches(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)
        assert loaded.is_complete == draft_state.is_complete
        assert loaded.completed_at == draft_state.completed_at


# ── Round-Trip After Picks ───────────────────────────────────────────


class TestRoundTripAfterPicks:
    def test_picks_survive_round_trip(self, persistence, draft_state):
        ctrl = DraftController(draft_state)
        ctrl.make_pick(0, "rb1")
        ctrl.make_pick(1, "wr1")

        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)

        assert len(loaded.all_picks) == 2
        assert loaded.all_picks[0].player_id == "rb1"
        assert loaded.all_picks[0].slot == "RB"
        assert loaded.all_picks[1].player_id == "wr1"

    def test_pick_fields_survive_round_trip(self, persistence, draft_state):
        ctrl = DraftController(draft_state)
        pick = ctrl.make_pick(0, "rb1")

        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)
        loaded_pick = loaded.all_picks[0]

        assert loaded_pick.pick_number == pick.pick_number
        assert loaded_pick.round == pick.round
        assert loaded_pick.team_id == pick.team_id
        assert loaded_pick.player_id == pick.player_id
        assert loaded_pick.timestamp == pick.timestamp
        assert loaded_pick.slot == pick.slot

    def test_roster_state_survives_round_trip(self, persistence, draft_state):
        ctrl = DraftController(draft_state)
        ctrl.make_pick(0, "rb1")

        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)

        team0 = loaded.get_team(0)
        assert "rb1" in team0.roster["RB"]
        assert "rb1" in team0.picks

    def test_advanced_state_survives_round_trip(self, persistence, draft_state):
        ctrl = DraftController(draft_state)
        ctrl.make_pick(0, "rb1")
        ctrl.make_pick(1, "wr1")
        ctrl.make_pick(2, "rb2")

        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)

        assert loaded.current_pick == draft_state.current_pick
        assert loaded.current_round == draft_state.current_round
        assert loaded.current_team_id == draft_state.current_team_id

    def test_available_players_updated_after_picks(self, persistence, draft_state):
        ctrl = DraftController(draft_state)
        ctrl.make_pick(0, "rb1")
        ctrl.make_pick(1, "wr1")

        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)

        assert "rb1" not in loaded.available_players
        assert "wr1" not in loaded.available_players


# ── Resume Draft ─────────────────────────────────────────────────────


class TestResumeDraft:
    def test_can_continue_making_picks_after_load(self, persistence, draft_state):
        """Core resume test: save mid-draft, load, continue picking."""
        ctrl = DraftController(draft_state)
        ctrl.make_pick(0, "rb1")
        ctrl.make_pick(1, "wr1")

        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)

        # Continue drafting from loaded state
        ctrl2 = DraftController(loaded)
        pick = ctrl2.make_pick(loaded.current_team_id, "rb2")
        assert pick.player_id == "rb2"
        assert loaded.current_pick == 4

    def test_resume_preserves_snake_order(self, persistence, draft_state):
        """After saving mid-round-2, snake order is maintained on resume."""
        ctrl = DraftController(draft_state)
        # Round 1: 0, 1, 2, 3
        ctrl.make_pick(0, "rb1")
        ctrl.make_pick(1, "wr1")
        ctrl.make_pick(2, "rb2")
        ctrl.make_pick(3, "wr2")
        # Round 2 starts at team 3 (snake)
        assert draft_state.current_team_id == 3
        ctrl.make_pick(3, "rb3")

        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)

        # Should continue round 2 at team 2
        assert loaded.current_team_id == 2
        ctrl2 = DraftController(loaded)
        pick = ctrl2.make_pick(2, "wr3")
        assert pick.team_id == 2
        assert loaded.current_team_id == 1

    def test_resume_completed_draft(self, persistence):
        """Completed draft loads as complete."""
        state = _make_draft_state(
            league_size=2,
            roster_slots={
                "QB": 1, "RB": 0, "WR": 0, "TE": 0,
                "FLEX": 0, "DST": 0, "K": 0, "BENCH": 0,
            },
        )
        ctrl = DraftController(state)
        ctrl.make_pick(0, "qb1")
        ctrl.make_pick(1, "qb2")
        assert state.is_complete is True

        persistence.save_draft(state)
        loaded = persistence.load_draft(state.draft_id)

        assert loaded.is_complete is True
        assert loaded.completed_at is not None


# ── Load Active Draft ────────────────────────────────────────────────


class TestLoadActiveDraft:
    def test_returns_none_when_no_active(self, persistence):
        loaded = persistence.load_active_draft()
        assert loaded is None

    def test_returns_most_recently_saved(self, persistence):
        state1 = _make_draft_state()
        state2 = _make_draft_state()
        persistence.save_draft(state1)
        persistence.save_draft(state2)
        loaded = persistence.load_active_draft()
        assert loaded.draft_id == state2.draft_id

    def test_active_draft_matches_saved(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        loaded = persistence.load_active_draft()
        assert loaded.draft_id == draft_state.draft_id
        assert loaded.current_pick == draft_state.current_pick

    def test_returns_none_for_broken_symlink(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        # Delete the actual file but leave symlink
        actual = persistence.storage_dir / f"draft_{draft_state.draft_id}.json"
        actual.unlink()
        loaded = persistence.load_active_draft()
        assert loaded is None


# ── List Saved Drafts ────────────────────────────────────────────────


class TestListSavedDrafts:
    def test_empty_when_no_drafts(self, persistence):
        drafts = persistence.list_saved_drafts()
        assert drafts == []

    def test_returns_saved_draft(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        drafts = persistence.list_saved_drafts()
        assert len(drafts) == 1
        assert drafts[0]["draft_id"] == draft_state.draft_id

    def test_metadata_fields(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        drafts = persistence.list_saved_drafts()
        d = drafts[0]
        assert "draft_id" in d
        assert "start_time" in d
        assert "is_complete" in d
        assert "current_round" in d
        assert "current_pick" in d
        assert "league_size" in d
        assert "scoring_format" in d

    def test_multiple_drafts(self, persistence):
        state1 = _make_draft_state()
        state2 = _make_draft_state()
        persistence.save_draft(state1)
        persistence.save_draft(state2)
        drafts = persistence.list_saved_drafts()
        assert len(drafts) == 2
        ids = {d["draft_id"] for d in drafts}
        assert state1.draft_id in ids
        assert state2.draft_id in ids

    def test_sorted_by_start_time_descending(self, persistence):
        state1 = _make_draft_state()
        state2 = _make_draft_state()
        # state1 should have earlier timestamp than state2
        persistence.save_draft(state1)
        persistence.save_draft(state2)
        drafts = persistence.list_saved_drafts()
        assert drafts[0]["start_time"] >= drafts[1]["start_time"]

    def test_excludes_active_draft_symlink(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        drafts = persistence.list_saved_drafts()
        # Should only count the actual file, not the symlink
        assert len(drafts) == 1

    def test_skips_corrupt_files(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        # Write a corrupt file
        corrupt = persistence.storage_dir / "draft_corrupt.json"
        corrupt.write_text("not valid json{{{")
        drafts = persistence.list_saved_drafts()
        assert len(drafts) == 1
        assert drafts[0]["draft_id"] == draft_state.draft_id

    def test_skips_malformed_json_missing_keys(self, persistence, draft_state):
        """Valid JSON but missing required keys is skipped."""
        persistence.save_draft(draft_state)
        malformed = persistence.storage_dir / "draft_malformed.json"
        malformed.write_text('{"some_key": "some_value"}')
        drafts = persistence.list_saved_drafts()
        assert len(drafts) == 1
        assert drafts[0]["draft_id"] == draft_state.draft_id


# ── Delete Draft ─────────────────────────────────────────────────────


class TestDeleteDraft:
    def test_deletes_existing_draft(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        result = persistence.delete_draft(draft_state.draft_id)
        assert result is True
        filepath = persistence.storage_dir / f"draft_{draft_state.draft_id}.json"
        assert not filepath.exists()

    def test_returns_false_for_missing_draft(self, persistence):
        result = persistence.delete_draft("nonexistent-id")
        assert result is False

    def test_removes_active_symlink_when_deleting_active(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        active = persistence.storage_dir / "active_draft.json"
        assert active.is_symlink()
        persistence.delete_draft(draft_state.draft_id)
        assert not active.exists()

    def test_preserves_active_symlink_when_deleting_other(self, persistence):
        state1 = _make_draft_state()
        state2 = _make_draft_state()
        persistence.save_draft(state1)
        persistence.save_draft(state2)  # state2 is now active
        persistence.delete_draft(state1.draft_id)
        active = persistence.storage_dir / "active_draft.json"
        assert active.is_symlink()

    def test_not_listed_after_delete(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        persistence.delete_draft(draft_state.draft_id)
        drafts = persistence.list_saved_drafts()
        assert len(drafts) == 0

    def test_cannot_load_after_delete(self, persistence, draft_state):
        persistence.save_draft(draft_state)
        persistence.delete_draft(draft_state.draft_id)
        loaded = persistence.load_draft(draft_state.draft_id)
        assert loaded is None


# ── Multiple Saves ───────────────────────────────────────────────────


class TestMultipleSaves:
    def test_active_link_updates_to_last_saved(self, persistence):
        state1 = _make_draft_state()
        state2 = _make_draft_state()
        persistence.save_draft(state1)
        persistence.save_draft(state2)
        loaded = persistence.load_active_draft()
        assert loaded.draft_id == state2.draft_id

    def test_both_drafts_independently_loadable(self, persistence):
        state1 = _make_draft_state()
        state2 = _make_draft_state()
        persistence.save_draft(state1)
        persistence.save_draft(state2)
        loaded1 = persistence.load_draft(state1.draft_id)
        loaded2 = persistence.load_draft(state2.draft_id)
        assert loaded1.draft_id == state1.draft_id
        assert loaded2.draft_id == state2.draft_id

    def test_save_updates_existing_file(self, persistence, draft_state):
        """Re-saving same draft updates the file in place."""
        path1 = persistence.save_draft(draft_state)
        draft_state.current_pick = 10
        path2 = persistence.save_draft(draft_state)
        assert path1 == path2
        loaded = persistence.load_draft(draft_state.draft_id)
        assert loaded.current_pick == 10


# ── Edge Cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    def test_completed_draft_round_trip(self, persistence):
        state = _make_draft_state(
            league_size=2,
            roster_slots={
                "QB": 1, "RB": 0, "WR": 0, "TE": 0,
                "FLEX": 0, "DST": 0, "K": 0, "BENCH": 0,
            },
        )
        ctrl = DraftController(state)
        ctrl.make_pick(0, "qb1")
        ctrl.make_pick(1, "qb2")

        persistence.save_draft(state)
        loaded = persistence.load_draft(state.draft_id)

        assert loaded.is_complete is True
        assert loaded.completed_at == state.completed_at
        assert len(loaded.all_picks) == 2

    def test_manual_tracker_mode_round_trip(self, persistence):
        state = _make_draft_state(draft_mode="manual_tracker")
        ctrl = DraftController(state)
        # In manual mode, any team can pick
        ctrl.make_pick(2, "rb1")

        persistence.save_draft(state)
        loaded = persistence.load_draft(state.draft_id)

        assert loaded.league_config.draft_mode == "manual_tracker"
        assert loaded.get_team(2).picks == ["rb1"]

    def test_pick_with_none_slot_round_trip(self, persistence, draft_state):
        """Pick records with slot=None survive serialization."""
        # Manually create a pick with no slot
        pick = Pick(
            pick_number=1, round=1, team_id=0,
            player_id="rb1", timestamp="2025-01-01", slot=None,
        )
        draft_state.all_picks.append(pick)

        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)

        assert loaded.all_picks[0].slot is None

    def test_empty_roster_round_trip(self, persistence, draft_state):
        """Fresh draft with empty rosters survives round trip."""
        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)

        for team in loaded.teams:
            for slot_players in team.roster.values():
                assert slot_players == []

    def test_full_draft_state_equality(self, persistence, draft_state):
        """Comprehensive: every field matches after save/load."""
        ctrl = DraftController(draft_state)
        ctrl.make_pick(0, "rb1")
        ctrl.make_pick(1, "wr1")
        ctrl.make_pick(2, "qb1")

        persistence.save_draft(draft_state)
        loaded = persistence.load_draft(draft_state.draft_id)

        # Scalar fields
        assert loaded.draft_id == draft_state.draft_id
        assert loaded.draft_start_time == draft_state.draft_start_time
        assert loaded.current_pick == draft_state.current_pick
        assert loaded.current_round == draft_state.current_round
        assert loaded.current_team_id == draft_state.current_team_id
        assert loaded.is_complete == draft_state.is_complete
        assert loaded.completed_at == draft_state.completed_at

        # Collections
        assert loaded.draft_order == draft_state.draft_order
        assert loaded.available_players == draft_state.available_players
        assert loaded.player_data == draft_state.player_data

        # Teams
        assert len(loaded.teams) == len(draft_state.teams)
        for orig, ld in zip(draft_state.teams, loaded.teams):
            assert ld.team_id == orig.team_id
            assert ld.team_name == orig.team_name
            assert ld.is_human == orig.is_human
            assert ld.roster == orig.roster
            assert ld.picks == orig.picks

        # Picks
        assert len(loaded.all_picks) == len(draft_state.all_picks)
        for orig, ld in zip(draft_state.all_picks, loaded.all_picks):
            assert ld.pick_number == orig.pick_number
            assert ld.round == orig.round
            assert ld.team_id == orig.team_id
            assert ld.player_id == orig.player_id
            assert ld.timestamp == orig.timestamp
            assert ld.slot == orig.slot

        # League config
        olc = draft_state.league_config
        llc = loaded.league_config
        assert llc.league_id == olc.league_id
        assert llc.league_size == olc.league_size
        assert llc.scoring_format == olc.scoring_format
        assert llc.draft_type == olc.draft_type
        assert llc.draft_mode == olc.draft_mode
        assert llc.data_year == olc.data_year
        assert llc.roster_slots == olc.roster_slots


# ── Integration with Real Data ───────────────────────────────────────


@requires_player_data
class TestIntegrationWithRealData:
    def test_save_and_load_real_draft(self, persistence):
        """Create a real draft, make picks, save, load, verify."""
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

        # Make a few picks
        for _ in range(12):
            pid = state.available_players[0]
            ctrl.make_pick(state.current_team_id, pid)

        persistence.save_draft(state)
        loaded = persistence.load_draft(state.draft_id)

        assert loaded.current_round == 2
        assert len(loaded.all_picks) == 12
        assert len(loaded.available_players) == len(state.available_players)

    def test_resume_real_draft(self, persistence):
        """Save mid-draft with real data, load, continue picking."""
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

        # Make one round of picks
        for _ in range(12):
            pid = state.available_players[0]
            ctrl.make_pick(state.current_team_id, pid)

        persistence.save_draft(state)
        loaded = persistence.load_draft(state.draft_id)
        ctrl2 = DraftController(loaded)

        # Continue round 2
        pid = loaded.available_players[0]
        pick = ctrl2.make_pick(loaded.current_team_id, pid)
        assert pick.round == 2
        assert len(loaded.all_picks) == 13

    def test_list_real_drafts(self, persistence):
        """Verify list_saved_drafts works with real data."""
        init = DraftInitializer()
        state = init.create_draft(
            league_size=12,
            scoring_format="half_ppr",
            roster_slots=DraftInitializer.get_default_roster_slots(),
            team_names=[f"Team {i + 1}" for i in range(12)],
            human_team_id=0,
            data_year=2025,
        )
        persistence.save_draft(state)

        drafts = persistence.list_saved_drafts()
        assert len(drafts) == 1
        assert drafts[0]["league_size"] == 12
        assert drafts[0]["scoring_format"] == "half_ppr"
