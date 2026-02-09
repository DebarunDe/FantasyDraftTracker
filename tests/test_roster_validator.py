"""Tests for roster validator and slot assignment."""

import pytest

from src.draft_manager.draft_state import LeagueConfig, TeamRoster
from src.draft_manager.roster_validator import RosterValidator


def _make_config():
    return LeagueConfig(
        league_id="test",
        league_size=12,
        scoring_format="half_ppr",
        roster_slots={
            "QB": 1, "RB": 2, "WR": 2, "TE": 1,
            "FLEX": 1, "DST": 1, "K": 1, "BENCH": 6,
        },
    )


def _make_team():
    config = _make_config()
    return TeamRoster(
        team_id=0,
        team_name="Test Team",
        is_human=True,
        roster={pos: [] for pos in config.roster_slots},
    )


# ── Slot Determination ───────────────────────────────────────────────

class TestDetermineRosterSlot:
    def test_fills_specific_position_first(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        assert v.determine_roster_slot(team, "QB") == "QB"
        assert v.determine_roster_slot(team, "RB") == "RB"
        assert v.determine_roster_slot(team, "WR") == "WR"

    def test_fills_flex_after_position_full(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        team.roster["RB"] = ["rb1", "rb2"]
        assert v.determine_roster_slot(team, "RB") == "FLEX"

    def test_fills_bench_after_flex_full(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        team.roster["RB"] = ["rb1", "rb2"]
        team.roster["FLEX"] = ["rb3"]
        assert v.determine_roster_slot(team, "RB") == "BENCH"

    def test_qb_skips_flex(self):
        """QB is not FLEX-eligible; goes straight to BENCH."""
        v = RosterValidator(_make_config())
        team = _make_team()
        team.roster["QB"] = ["qb1"]
        assert v.determine_roster_slot(team, "QB") == "BENCH"

    def test_k_skips_flex(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        team.roster["K"] = ["k1"]
        assert v.determine_roster_slot(team, "K") == "BENCH"

    def test_dst_skips_flex(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        team.roster["DST"] = ["dst1"]
        assert v.determine_roster_slot(team, "DST") == "BENCH"

    def test_wr_to_flex(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        team.roster["WR"] = ["wr1", "wr2"]
        assert v.determine_roster_slot(team, "WR") == "FLEX"

    def test_te_to_flex(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        team.roster["TE"] = ["te1"]
        assert v.determine_roster_slot(team, "TE") == "FLEX"

    def test_nine_rbs_allowed(self):
        """9 RBs is valid: 2 RB slots + 1 FLEX + 6 BENCH."""
        v = RosterValidator(_make_config())
        team = _make_team()
        slots = []
        for i in range(9):
            slot = v.determine_roster_slot(team, "RB")
            team.add_player(f"rb{i+1}", slot)
            slots.append(slot)
        assert slots == ["RB", "RB", "FLEX", "BENCH", "BENCH",
                         "BENCH", "BENCH", "BENCH", "BENCH"]


# ── Final Roster Validation ──────────────────────────────────────────

class TestValidateFinalRoster:
    def test_valid_complete_roster(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        team.roster["QB"] = ["qb1"]
        team.roster["RB"] = ["rb1", "rb2"]
        team.roster["WR"] = ["wr1", "wr2"]
        team.roster["TE"] = ["te1"]
        team.roster["FLEX"] = ["rb3"]
        team.roster["DST"] = ["dst1"]
        team.roster["K"] = ["k1"]
        team.roster["BENCH"] = [f"b{i}" for i in range(6)]
        is_valid, errors = v.validate_final_roster(team)
        assert is_valid is True
        assert errors == []

    def test_missing_positions(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        is_valid, errors = v.validate_final_roster(team)
        assert is_valid is False
        assert len(errors) > 0

    def test_too_many_at_position(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        team.roster["QB"] = ["qb1", "qb2"]  # limit is 1
        is_valid, errors = v.validate_final_roster(team)
        assert is_valid is False
        assert any("Too many QB" in e for e in errors)


# ── Roster Summary ───────────────────────────────────────────────────

class TestRosterSummary:
    def test_empty_roster_summary(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        summary = v.get_roster_summary(team)
        assert summary["QB"]["filled"] == 0
        assert summary["QB"]["required"] == 1
        assert summary["QB"]["remaining"] == 1

    def test_partially_filled_summary(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        team.roster["RB"] = ["rb1"]
        summary = v.get_roster_summary(team)
        assert summary["RB"]["filled"] == 1
        assert summary["RB"]["required"] == 2
        assert summary["RB"]["remaining"] == 1

    def test_fully_filled_shows_zero_remaining(self):
        v = RosterValidator(_make_config())
        team = _make_team()
        team.roster["QB"] = ["qb1"]
        summary = v.get_roster_summary(team)
        assert summary["QB"]["remaining"] == 0
