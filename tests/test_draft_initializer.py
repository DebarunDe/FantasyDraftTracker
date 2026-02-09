"""Tests for draft initializer - creating new drafts from real pipeline data."""

import json
from pathlib import Path

import pytest

from src.draft_manager.draft_initializer import DraftInitializer


# ── Check data availability ──────────────────────────────────────────

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
PLAYER_FILE = PROCESSED_DIR / "players_2025.json"
requires_player_data = pytest.mark.skipif(
    not PLAYER_FILE.exists(),
    reason=f"Processed player data not found at {PLAYER_FILE}",
)


# ── Input Validation ─────────────────────────────────────────────────

class TestInputValidation:
    def test_league_size_too_small(self):
        init = DraftInitializer()
        with pytest.raises(ValueError, match="League size"):
            init.create_draft(
                league_size=1,
                scoring_format="half_ppr",
                roster_slots=DraftInitializer.get_default_roster_slots(),
                team_names=["T1"],
                human_team_id=0,
            )

    def test_league_size_too_large(self):
        init = DraftInitializer()
        with pytest.raises(ValueError, match="League size"):
            init.create_draft(
                league_size=22,
                scoring_format="half_ppr",
                roster_slots=DraftInitializer.get_default_roster_slots(),
                team_names=[f"T{i}" for i in range(22)],
                human_team_id=0,
            )

    def test_league_size_must_be_even(self):
        init = DraftInitializer()
        with pytest.raises(ValueError, match="even number"):
            init.create_draft(
                league_size=7,
                scoring_format="half_ppr",
                roster_slots=DraftInitializer.get_default_roster_slots(),
                team_names=[f"T{i}" for i in range(7)],
                human_team_id=0,
            )

    def test_team_names_mismatch(self):
        init = DraftInitializer()
        with pytest.raises(ValueError, match="team names"):
            init.create_draft(
                league_size=4,
                scoring_format="half_ppr",
                roster_slots=DraftInitializer.get_default_roster_slots(),
                team_names=["T1", "T2"],  # only 2, need 4
                human_team_id=0,
            )

    def test_human_team_id_out_of_range(self):
        init = DraftInitializer()
        with pytest.raises(ValueError, match="Human team ID"):
            init.create_draft(
                league_size=4,
                scoring_format="half_ppr",
                roster_slots=DraftInitializer.get_default_roster_slots(),
                team_names=[f"T{i}" for i in range(4)],
                human_team_id=5,
            )

    def test_invalid_scoring_format(self):
        init = DraftInitializer()
        with pytest.raises(ValueError, match="scoring format"):
            init.create_draft(
                league_size=4,
                scoring_format="triple_ppr",
                roster_slots=DraftInitializer.get_default_roster_slots(),
                team_names=[f"T{i}" for i in range(4)],
                human_team_id=0,
            )

    def test_missing_required_positions(self):
        init = DraftInitializer()
        bad_slots = {"QB": 1, "RB": 2}  # missing WR, TE, FLEX, BENCH
        with pytest.raises(ValueError, match="missing required positions"):
            init.create_draft(
                league_size=4,
                scoring_format="half_ppr",
                roster_slots=bad_slots,
                team_names=[f"T{i}" for i in range(4)],
                human_team_id=0,
            )

    def test_missing_data_file(self):
        init = DraftInitializer(processed_data_dir=Path("/nonexistent"))
        with pytest.raises(FileNotFoundError, match="No player data found"):
            init.create_draft(
                league_size=4,
                scoring_format="half_ppr",
                roster_slots=DraftInitializer.get_default_roster_slots(),
                team_names=[f"T{i}" for i in range(4)],
                human_team_id=0,
                data_year=9999,
            )

    def test_malformed_json_missing_players_key(self, tmp_path):
        """JSON file without 'players' key should raise ValueError."""
        bad_file = tmp_path / "players_2025.json"
        bad_file.write_text('{"metadata": {}}', encoding="utf-8")
        init = DraftInitializer(processed_data_dir=tmp_path)
        with pytest.raises((ValueError, KeyError)):
            init.create_draft(
                league_size=4,
                scoring_format="half_ppr",
                roster_slots=DraftInitializer.get_default_roster_slots(),
                team_names=[f"T{i}" for i in range(4)],
                human_team_id=0,
                data_year=2025,
            )

    def test_malformed_json_missing_player_id(self, tmp_path):
        """Player records without 'player_id' should raise ValueError."""
        bad_file = tmp_path / "players_2025.json"
        bad_file.write_text(
            '{"players": [{"name": "No ID"}]}', encoding="utf-8"
        )
        init = DraftInitializer(processed_data_dir=tmp_path)
        with pytest.raises(ValueError, match="Malformed player data"):
            init.create_draft(
                league_size=4,
                scoring_format="half_ppr",
                roster_slots=DraftInitializer.get_default_roster_slots(),
                team_names=[f"T{i}" for i in range(4)],
                human_team_id=0,
                data_year=2025,
            )


# ── Default Helpers ──────────────────────────────────────────────────

class TestDefaults:
    def test_default_roster_slots(self):
        slots = DraftInitializer.get_default_roster_slots()
        assert slots["QB"] == 1
        assert slots["RB"] == 2
        assert slots["WR"] == 2
        assert slots["TE"] == 1
        assert slots["FLEX"] == 1
        assert slots["DST"] == 1
        assert slots["K"] == 1
        assert slots["BENCH"] == 6

    def test_default_roster_slots_returns_copy(self):
        """Mutating the returned dict shouldn't affect future calls."""
        s1 = DraftInitializer.get_default_roster_slots()
        s1["QB"] = 99
        s2 = DraftInitializer.get_default_roster_slots()
        assert s2["QB"] == 1

    def test_default_scoring_format(self):
        assert DraftInitializer.get_default_scoring_format() == "half_ppr"


# ── Integration with Real Data ───────────────────────────────────────

@requires_player_data
class TestCreateDraftWithRealData:
    """Integration tests using real processed pipeline output."""

    def test_create_12_team_draft(self):
        init = DraftInitializer()
        team_names = [f"Team {i+1}" for i in range(12)]
        state = init.create_draft(
            league_size=12,
            scoring_format="half_ppr",
            roster_slots=DraftInitializer.get_default_roster_slots(),
            team_names=team_names,
            human_team_id=0,
            data_year=2025,
        )

        assert state.current_pick == 1
        assert state.current_round == 1
        assert len(state.teams) == 12
        assert len(state.available_players) > 300
        assert state.is_complete is False

    def test_player_data_loaded(self):
        init = DraftInitializer()
        state = init.create_draft(
            league_size=12,
            scoring_format="half_ppr",
            roster_slots=DraftInitializer.get_default_roster_slots(),
            team_names=[f"Team {i+1}" for i in range(12)],
            human_team_id=0,
            data_year=2025,
        )

        # Spot-check a player
        pid = state.available_players[0]
        info = state.get_player_info(pid)
        assert "name" in info
        assert "position" in info
        assert info["position"] in ("QB", "RB", "WR", "TE", "K", "DST")

    def test_all_scoring_formats_work(self):
        init = DraftInitializer()
        for fmt in ("standard", "half_ppr", "full_ppr"):
            state = init.create_draft(
                league_size=4,
                scoring_format=fmt,
                roster_slots=DraftInitializer.get_default_roster_slots(),
                team_names=[f"Team {i+1}" for i in range(4)],
                human_team_id=0,
                data_year=2025,
            )
            assert state.league_config.scoring_format == fmt

    def test_simulation_mode(self):
        init = DraftInitializer()
        state = init.create_draft(
            league_size=4,
            scoring_format="half_ppr",
            roster_slots=DraftInitializer.get_default_roster_slots(),
            team_names=[f"Team {i+1}" for i in range(4)],
            human_team_id=0,
            draft_mode="simulation",
            data_year=2025,
        )
        assert state.league_config.draft_mode == "simulation"

    def test_manual_tracker_mode(self):
        init = DraftInitializer()
        state = init.create_draft(
            league_size=4,
            scoring_format="half_ppr",
            roster_slots=DraftInitializer.get_default_roster_slots(),
            team_names=[f"Team {i+1}" for i in range(4)],
            human_team_id=0,
            draft_mode="manual_tracker",
            data_year=2025,
        )
        assert state.league_config.draft_mode == "manual_tracker"

    def test_human_team_position(self):
        init = DraftInitializer()
        state = init.create_draft(
            league_size=4,
            scoring_format="half_ppr",
            roster_slots=DraftInitializer.get_default_roster_slots(),
            team_names=[f"Team {i+1}" for i in range(4)],
            human_team_id=2,
            data_year=2025,
        )
        assert state.teams[2].is_human is True
        assert state.teams[0].is_human is False

    def test_custom_roster_slots(self):
        init = DraftInitializer()
        custom_slots = {
            "QB": 2, "RB": 3, "WR": 3, "TE": 2,
            "FLEX": 2, "DST": 1, "K": 1, "BENCH": 4,
        }
        state = init.create_draft(
            league_size=4,
            scoring_format="half_ppr",
            roster_slots=custom_slots,
            team_names=[f"Team {i+1}" for i in range(4)],
            human_team_id=0,
            data_year=2025,
        )
        assert state.league_config.roster_slots["QB"] == 2
        assert state.league_config.total_rounds() == 18

    def test_player_data_has_required_fields(self):
        """Verify pipeline output has fields the draft manager needs."""
        init = DraftInitializer()
        state = init.create_draft(
            league_size=4,
            scoring_format="half_ppr",
            roster_slots=DraftInitializer.get_default_roster_slots(),
            team_names=[f"Team {i+1}" for i in range(4)],
            human_team_id=0,
            data_year=2025,
        )

        for pid in list(state.available_players)[:20]:
            info = state.get_player_info(pid)
            assert "player_id" in info, f"{pid} missing player_id"
            assert "name" in info, f"{pid} missing name"
            assert "position" in info, f"{pid} missing position"
            assert "team" in info, f"{pid} missing team"
            assert "projections" in info, f"{pid} missing projections"
            assert "baseline_vor" in info, f"{pid} missing baseline_vor"
