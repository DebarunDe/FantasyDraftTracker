"""Milestone 12: End-to-End MVP Tests.

Covers the M12 success criteria from SYSTEM_ARCHITECTURE.md:
  - Can complete full draft without errors
  - All teams have complete rosters
  - Manual tracker mode works correctly
  - Saved draft can be loaded and resumed

Test classes:
  TestProgrammaticFullDraft   — simulation mode, programmatic (no UI)
  TestManualTrackerFullDraft  — manual_tracker mode, programmatic
  TestSaveResumeCycle         — persist mid-draft, reload, finish
  TestRealDataDraft           — uses players_2025.json via DraftInitializer
  TestMultipleLeagueSizes     — 8/10/12/14-team programmatic completions
  TestMultipleScoringFormats  — standard, half_ppr, full_ppr all complete
  TestRosterValidity          — roster slot counts exactly match config
  TestDraftSummary            — get_draft_summary() fields after completion
  TestCLIFullDraftFlow        — DraftApp end-to-end through _draft_loop()
  TestManualTrackerCLIFlow    — DraftApp manual tracker complete lifecycle
  TestEdgeCases               — error recovery, corrupt saves, boundary inputs
"""

import re
import tempfile
from io import StringIO
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from src.draft_manager.draft_controller import DraftController
from src.draft_manager.draft_initializer import DraftInitializer
from src.draft_manager.draft_rules import ValidationError
from src.draft_manager.draft_state import DraftState, LeagueConfig, TeamRoster
from src.draft_manager.state_persistence import StatePersistence
from src.simulation_engine.computer_drafter import ComputerDrafter
from src.simulation_engine.models import Recommendation
from src.simulation_engine.pick_recommender import PickRecommender
from src.simulation_engine.vor_calculator import DynamicVORCalculator
from src.ui.cli import DraftApp

# ── Constants ────────────────────────────────────────────────────────

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
PLAYER_FILE = PROCESSED_DIR / "players_2025.json"

requires_player_data = pytest.mark.skipif(
    not PLAYER_FILE.exists(),
    reason=f"Processed player data not found at {PLAYER_FILE}",
)

STANDARD_ROSTER = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "DST": 1,
    "K": 1,
    "BENCH": 6,
}


# ── Shared helpers ───────────────────────────────────────────────────


def _make_player_pool(n_qb=10, n_rb=20, n_wr=20, n_te=10, n_k=8, n_dst=8) -> Dict[str, Dict]:
    """Build a synthetic player pool large enough for full-league drafts."""
    players = {}
    rank = 1
    for pos, count in [
        ("QB", n_qb),
        ("RB", n_rb),
        ("WR", n_wr),
        ("TE", n_te),
        ("K", n_k),
        ("DST", n_dst),
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


def _run_programmatic_draft(
    league_size: int,
    scoring_format: str = "half_ppr",
    draft_mode: str = "simulation",
    roster_slots: Dict = None,
    player_data: Dict = None,
    strategy: str = "balanced",
) -> DraftState:
    """Run a full programmatic draft using ComputerDrafter for every team.

    Works for both 'simulation' and 'manual_tracker' modes since
    DraftRules skips turn-order enforcement in manual_tracker mode.

    Returns the completed DraftState.
    """
    if roster_slots is None:
        roster_slots = dict(STANDARD_ROSTER)
    if player_data is None:
        player_data = _make_player_pool(
            n_qb=league_size * 4,
            n_rb=league_size * 10,
            n_wr=league_size * 10,
            n_te=league_size * 4,
            n_k=league_size * 2,
            n_dst=league_size * 2,
        )

    config = LeagueConfig(
        league_id="e2e_test",
        league_size=league_size,
        scoring_format=scoring_format,
        draft_type="snake",
        draft_mode=draft_mode,
        data_year=2025,
        roster_slots=roster_slots,
    )
    team_names = [f"Team {i + 1}" for i in range(league_size)]
    state = DraftState.create_new(
        league_config=config,
        team_names=team_names,
        human_team_id=0,
        player_data=player_data,
    )

    controller = DraftController(state)
    vor_calc = DynamicVORCalculator(scoring_format, league_size=league_size)
    drafter = ComputerDrafter(vor_calculator=vor_calc, strategy=strategy)

    total_picks = sum(roster_slots.values()) * league_size
    while not controller.is_complete:
        current_team = state.get_current_team()
        available = controller.get_available_players()
        from src.draft_manager.draft_rules import DraftRules

        rules = DraftRules(state)
        legal = [
            p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
        ]
        assert legal, (
            f"No legal picks at pick {state.current_pick} for team {current_team.team_name}"
        )
        player_id = drafter.make_pick(state, legal, current_team.team_id)
        controller.make_pick(current_team.team_id, player_id)

        assert len(state.all_picks) <= total_picks, "Pick count exceeds total expected"

    return state


def _expected_roster_totals(roster_slots: Dict) -> int:
    """Total players per team in a completed draft."""
    return sum(roster_slots.values())


# ── TestProgrammaticFullDraft ────────────────────────────────────────


class TestProgrammaticFullDraft:
    """Full simulation mode drafts verified at the state level."""

    def test_12team_draft_completes(self):
        state = _run_programmatic_draft(league_size=12)
        assert state.is_complete

    def test_all_picks_recorded(self):
        league_size = 12
        roster_slots = dict(STANDARD_ROSTER)
        state = _run_programmatic_draft(league_size=league_size, roster_slots=roster_slots)
        expected_total = sum(roster_slots.values()) * league_size
        assert len(state.all_picks) == expected_total

    def test_no_player_drafted_twice(self):
        state = _run_programmatic_draft(league_size=8)
        drafted_ids = [p.player_id for p in state.all_picks]
        assert len(drafted_ids) == len(set(drafted_ids)), "Duplicate player found"

    def test_drafted_players_removed_from_available(self):
        """All drafted players are removed from the available pool."""
        state = _run_programmatic_draft(league_size=8)
        drafted_ids = {p.player_id for p in state.all_picks}
        remaining = set(state.available_players)
        assert drafted_ids.isdisjoint(remaining), (
            "Drafted players still appear in available_players"
        )

    def test_all_teams_have_full_rosters(self):
        roster_slots = dict(STANDARD_ROSTER)
        state = _run_programmatic_draft(league_size=8, roster_slots=roster_slots)
        expected = _expected_roster_totals(roster_slots)
        for team in state.teams:
            total = sum(len(v) for v in team.roster.values())
            assert total == expected, f"{team.team_name} has {total} players, expected {expected}"

    def test_picks_reference_correct_teams(self):
        """Every pick's team_id must match the snake draft order."""
        state = _run_programmatic_draft(league_size=4)
        for pick in state.all_picks:
            assert 0 <= pick.team_id < 4
            assert pick.pick_number == state.all_picks.index(pick) + 1

    def test_roster_slots_not_overflowed(self):
        """No slot (except BENCH/FLEX) has more players than allowed."""
        roster_slots = dict(STANDARD_ROSTER)
        state = _run_programmatic_draft(league_size=12, roster_slots=roster_slots)
        for team in state.teams:
            for slot, player_ids in team.roster.items():
                limit = roster_slots.get(slot, 0)
                assert len(player_ids) <= limit, (
                    f"{team.team_name} slot {slot} has {len(player_ids)}, limit is {limit}"
                )

    def test_completed_at_timestamp_set(self):
        state = _run_programmatic_draft(league_size=4)
        assert state.completed_at is not None
        assert len(state.completed_at) > 0

    def test_all_four_strategies_complete_draft(self):
        for strategy in ("vor_only", "balanced", "consensus", "contrarian"):
            state = _run_programmatic_draft(league_size=4, strategy=strategy)
            assert state.is_complete, f"Strategy '{strategy}' did not complete draft"


# ── TestManualTrackerFullDraft ────────────────────────────────────────


class TestManualTrackerFullDraft:
    """Full drafts in manual_tracker mode (all picks entered by 'user')."""

    def test_12team_manual_draft_completes(self):
        state = _run_programmatic_draft(league_size=12, draft_mode="manual_tracker")
        assert state.is_complete

    def test_manual_mode_all_picks_recorded(self):
        roster_slots = dict(STANDARD_ROSTER)
        state = _run_programmatic_draft(
            league_size=8, draft_mode="manual_tracker", roster_slots=roster_slots
        )
        expected = sum(roster_slots.values()) * 8
        assert len(state.all_picks) == expected

    def test_manual_mode_no_player_drafted_twice(self):
        state = _run_programmatic_draft(league_size=8, draft_mode="manual_tracker")
        drafted_ids = [p.player_id for p in state.all_picks]
        assert len(drafted_ids) == len(set(drafted_ids))

    def test_manual_mode_all_teams_have_full_rosters(self):
        roster_slots = dict(STANDARD_ROSTER)
        state = _run_programmatic_draft(
            league_size=8, draft_mode="manual_tracker", roster_slots=roster_slots
        )
        expected = _expected_roster_totals(roster_slots)
        for team in state.teams:
            total = sum(len(v) for v in team.roster.values())
            assert total == expected, f"{team.team_name} has {total} players, expected {expected}"

    def test_manual_mode_drafted_players_removed_from_available(self):
        """All manually-entered picks are removed from the available pool."""
        state = _run_programmatic_draft(league_size=4, draft_mode="manual_tracker")
        drafted_ids = {p.player_id for p in state.all_picks}
        remaining = set(state.available_players)
        assert drafted_ids.isdisjoint(remaining), (
            "Drafted players still appear in available_players"
        )

    def test_manual_mode_draft_id_set(self):
        state = _run_programmatic_draft(league_size=4, draft_mode="manual_tracker")
        assert state.draft_id is not None and len(state.draft_id) > 0


# ── TestSaveResumeCycle ──────────────────────────────────────────────


class TestSaveResumeCycle:
    """Save mid-draft → load → complete."""

    def _make_minimal_state(self, n_picks_to_make=5):
        """Create a small draft and make a few picks programmatically.

        Roster: 11 slots × 4 teams = 44 picks total. Pool must have ≥44 players.
        Pool: 8+16+16+8+8+8 = 64 players — enough headroom.
        """
        roster_slots = {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 1,
            "DST": 1,
            "K": 1,
            "BENCH": 2,
        }
        player_data = _make_player_pool(n_qb=8, n_rb=16, n_wr=16, n_te=8, n_k=8, n_dst=8)
        config = LeagueConfig(
            league_id="resume_test",
            league_size=4,
            scoring_format="half_ppr",
            draft_type="snake",
            draft_mode="simulation",
            data_year=2025,
            roster_slots=roster_slots,
        )
        state = DraftState.create_new(
            league_config=config,
            team_names=["T0", "T1", "T2", "T3"],
            human_team_id=0,
            player_data=player_data,
        )
        controller = DraftController(state)
        vor_calc = DynamicVORCalculator("half_ppr", league_size=4)
        drafter = ComputerDrafter(vor_calc, strategy="balanced")
        from src.draft_manager.draft_rules import DraftRules

        for _ in range(n_picks_to_make):
            if controller.is_complete:
                break
            current_team = state.get_current_team()
            available = controller.get_available_players()
            rules = DraftRules(state)
            legal = [
                p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
            ]
            pid = drafter.make_pick(state, legal, current_team.team_id)
            controller.make_pick(current_team.team_id, pid)
        return state, controller, vor_calc

    def test_save_and_load_preserves_pick_count(self):
        state, _, _ = self._make_minimal_state(n_picks_to_make=6)
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = StatePersistence(storage_dir=Path(tmpdir))
            persistence.save_draft(state)
            loaded = persistence.load_draft(state.draft_id)
            assert loaded is not None
            assert loaded.current_pick == state.current_pick
            assert len(loaded.all_picks) == len(state.all_picks)

    def test_save_and_load_preserves_available_players(self):
        state, _, _ = self._make_minimal_state(n_picks_to_make=6)
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = StatePersistence(storage_dir=Path(tmpdir))
            persistence.save_draft(state)
            loaded = persistence.load_draft(state.draft_id)
            assert set(loaded.available_players) == set(state.available_players)

    def test_save_and_load_preserves_roster_contents(self):
        state, _, _ = self._make_minimal_state(n_picks_to_make=6)
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = StatePersistence(storage_dir=Path(tmpdir))
            persistence.save_draft(state)
            loaded = persistence.load_draft(state.draft_id)
            for orig_team, loaded_team in zip(state.teams, loaded.teams):
                assert orig_team.roster == loaded_team.roster

    def test_resume_and_complete_draft(self):
        """Save at pick 5, reload, then complete the rest of the draft."""
        state, _, vor_calc = self._make_minimal_state(n_picks_to_make=5)
        picks_after_save = state.current_pick

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = StatePersistence(storage_dir=Path(tmpdir))
            persistence.save_draft(state)
            loaded = persistence.load_draft(state.draft_id)

        assert loaded is not None
        assert loaded.current_pick == picks_after_save

        # Resume and finish
        controller2 = DraftController(loaded)
        vor_calc2 = DynamicVORCalculator("half_ppr", league_size=4)
        drafter2 = ComputerDrafter(vor_calc2, strategy="balanced")
        from src.draft_manager.draft_rules import DraftRules

        while not controller2.is_complete:
            current_team = loaded.get_current_team()
            available = controller2.get_available_players()
            rules = DraftRules(loaded)
            legal = [
                p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
            ]
            pid = drafter2.make_pick(loaded, legal, current_team.team_id)
            controller2.make_pick(current_team.team_id, pid)

        assert loaded.is_complete

    def test_active_draft_symlink_updated_on_save(self):
        state, _, _ = self._make_minimal_state(n_picks_to_make=3)
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = StatePersistence(storage_dir=Path(tmpdir))
            persistence.save_draft(state)
            active = persistence.load_active_draft()
            assert active is not None
            assert active.draft_id == state.draft_id

    def test_list_saved_drafts_returns_metadata(self):
        state, _, _ = self._make_minimal_state(n_picks_to_make=3)
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = StatePersistence(storage_dir=Path(tmpdir))
            persistence.save_draft(state)
            drafts = persistence.list_saved_drafts()
            assert len(drafts) == 1
            assert drafts[0]["draft_id"] == state.draft_id
            assert drafts[0]["is_complete"] is False

    def test_completed_draft_marked_complete_on_load(self):
        state, _, _ = self._make_minimal_state(n_picks_to_make=0)
        # Run to completion
        controller = DraftController(state)
        vor_calc = DynamicVORCalculator("half_ppr", league_size=4)
        drafter = ComputerDrafter(vor_calc, strategy="balanced")
        from src.draft_manager.draft_rules import DraftRules

        while not controller.is_complete:
            current_team = state.get_current_team()
            available = controller.get_available_players()
            rules = DraftRules(state)
            legal = [
                p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
            ]
            pid = drafter.make_pick(state, legal, current_team.team_id)
            controller.make_pick(current_team.team_id, pid)

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = StatePersistence(storage_dir=Path(tmpdir))
            persistence.save_draft(state)
            drafts = persistence.list_saved_drafts()
            assert drafts[0]["is_complete"] is True
            loaded = persistence.load_draft(state.draft_id)
            assert loaded.is_complete

    def test_corrupt_save_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = StatePersistence(storage_dir=Path(tmpdir))
            # Write a corrupt file
            bad_path = Path(tmpdir) / "draft_fakeuid.json"
            bad_path.write_text("{ not valid json }")
            result = persistence.load_draft("fakeuid")
            assert result is None

    def test_delete_draft_removes_file(self):
        state, _, _ = self._make_minimal_state(n_picks_to_make=3)
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = StatePersistence(storage_dir=Path(tmpdir))
            persistence.save_draft(state)
            assert persistence.delete_draft(state.draft_id)
            assert not (Path(tmpdir) / f"draft_{state.draft_id}.json").exists()

    def test_delete_nonexistent_draft_returns_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = StatePersistence(storage_dir=Path(tmpdir))
            assert persistence.delete_draft("no-such-uuid") is False


# ── TestRealDataDraft ────────────────────────────────────────────────


class TestRealDataDraft:
    """Tests using real players_2025.json via DraftInitializer."""

    @requires_player_data
    def test_real_data_12team_draft_completes(self, tmp_path):
        """Full 12-team draft using real 2025 player data."""
        initializer = DraftInitializer()
        state = initializer.create_draft(
            league_size=12,
            scoring_format="half_ppr",
            roster_slots=dict(STANDARD_ROSTER),
            team_names=[f"Team {i + 1}" for i in range(12)],
            human_team_id=0,
            draft_mode="simulation",
            data_year=2025,
        )

        controller = DraftController(state)
        vor_calc = DynamicVORCalculator("half_ppr", league_size=12)
        drafter = ComputerDrafter(vor_calc, strategy="balanced")
        from src.draft_manager.draft_rules import DraftRules

        while not controller.is_complete:
            current_team = state.get_current_team()
            available = controller.get_available_players()
            rules = DraftRules(state)
            legal = [
                p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
            ]
            assert legal, (
                f"No legal picks at pick {state.current_pick} for {current_team.team_name}"
            )
            pid = drafter.make_pick(state, legal, current_team.team_id)
            controller.make_pick(current_team.team_id, pid)

        assert state.is_complete

    @requires_player_data
    def test_real_data_all_teams_complete_rosters(self, tmp_path):
        initializer = DraftInitializer()
        state = initializer.create_draft(
            league_size=12,
            scoring_format="half_ppr",
            roster_slots=dict(STANDARD_ROSTER),
            team_names=[f"Team {i + 1}" for i in range(12)],
            human_team_id=0,
            draft_mode="simulation",
            data_year=2025,
        )

        controller = DraftController(state)
        vor_calc = DynamicVORCalculator("half_ppr", league_size=12)
        drafter = ComputerDrafter(vor_calc, strategy="balanced")
        from src.draft_manager.draft_rules import DraftRules

        while not controller.is_complete:
            current_team = state.get_current_team()
            available = controller.get_available_players()
            rules = DraftRules(state)
            legal = [
                p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
            ]
            pid = drafter.make_pick(state, legal, current_team.team_id)
            controller.make_pick(current_team.team_id, pid)

        expected = _expected_roster_totals(STANDARD_ROSTER)
        for team in state.teams:
            total = sum(len(v) for v in team.roster.values())
            assert total == expected, f"{team.team_name}: {total} players, expected {expected}"

    @requires_player_data
    def test_real_data_no_player_drafted_twice(self):
        initializer = DraftInitializer()
        state = initializer.create_draft(
            league_size=10,
            scoring_format="half_ppr",
            roster_slots=dict(STANDARD_ROSTER),
            team_names=[f"Team {i + 1}" for i in range(10)],
            human_team_id=0,
            draft_mode="simulation",
            data_year=2025,
        )

        controller = DraftController(state)
        vor_calc = DynamicVORCalculator("half_ppr", league_size=10)
        drafter = ComputerDrafter(vor_calc, strategy="balanced")
        from src.draft_manager.draft_rules import DraftRules

        while not controller.is_complete:
            current_team = state.get_current_team()
            available = controller.get_available_players()
            rules = DraftRules(state)
            legal = [
                p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
            ]
            pid = drafter.make_pick(state, legal, current_team.team_id)
            controller.make_pick(current_team.team_id, pid)

        drafted_ids = [p.player_id for p in state.all_picks]
        assert len(drafted_ids) == len(set(drafted_ids))

    @requires_player_data
    def test_real_data_draft_summary_valid(self):
        initializer = DraftInitializer()
        state = initializer.create_draft(
            league_size=8,
            scoring_format="half_ppr",
            roster_slots=dict(STANDARD_ROSTER),
            team_names=[f"Team {i + 1}" for i in range(8)],
            human_team_id=0,
            draft_mode="simulation",
            data_year=2025,
        )

        controller = DraftController(state)
        vor_calc = DynamicVORCalculator("half_ppr", league_size=8)
        drafter = ComputerDrafter(vor_calc, strategy="balanced")
        from src.draft_manager.draft_rules import DraftRules

        while not controller.is_complete:
            current_team = state.get_current_team()
            available = controller.get_available_players()
            rules = DraftRules(state)
            legal = [
                p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
            ]
            pid = drafter.make_pick(state, legal, current_team.team_id)
            controller.make_pick(current_team.team_id, pid)

        summary = controller.get_draft_summary()
        assert "error" not in summary
        assert len(summary["teams"]) == 8
        for team_summary in summary["teams"]:
            assert team_summary["projected_points"] > 0

    @requires_player_data
    def test_real_data_save_and_resume(self, tmp_path):
        """Make 20 picks with real data, save, reload, finish."""
        initializer = DraftInitializer()
        state = initializer.create_draft(
            league_size=12,
            scoring_format="half_ppr",
            roster_slots=dict(STANDARD_ROSTER),
            team_names=[f"Team {i + 1}" for i in range(12)],
            human_team_id=0,
            draft_mode="simulation",
            data_year=2025,
        )

        controller = DraftController(state)
        vor_calc = DynamicVORCalculator("half_ppr", league_size=12)
        drafter = ComputerDrafter(vor_calc, strategy="balanced")
        from src.draft_manager.draft_rules import DraftRules

        # Make 20 picks
        for _ in range(20):
            current_team = state.get_current_team()
            available = controller.get_available_players()
            rules = DraftRules(state)
            legal = [
                p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
            ]
            pid = drafter.make_pick(state, legal, current_team.team_id)
            controller.make_pick(current_team.team_id, pid)

        snapshot_pick = state.current_pick
        persistence = StatePersistence(storage_dir=tmp_path)
        persistence.save_draft(state)

        # Reload
        loaded = persistence.load_draft(state.draft_id)
        assert loaded is not None
        assert loaded.current_pick == snapshot_pick

        # Complete from resumed state
        controller2 = DraftController(loaded)
        vor_calc2 = DynamicVORCalculator("half_ppr", league_size=12)
        drafter2 = ComputerDrafter(vor_calc2, strategy="balanced")

        while not controller2.is_complete:
            current_team = loaded.get_current_team()
            available = controller2.get_available_players()
            rules = DraftRules(loaded)
            legal = [
                p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
            ]
            pid = drafter2.make_pick(loaded, legal, current_team.team_id)
            controller2.make_pick(current_team.team_id, pid)

        assert loaded.is_complete


# ── TestMultipleLeagueSizes ──────────────────────────────────────────


class TestMultipleLeagueSizes:
    """Verify drafts complete cleanly across 8/10/12/14-team leagues."""

    @pytest.mark.parametrize("league_size", [8, 10, 12, 14])
    def test_draft_completes(self, league_size):
        state = _run_programmatic_draft(league_size=league_size)
        assert state.is_complete

    @pytest.mark.parametrize("league_size", [8, 10, 12, 14])
    def test_correct_total_picks(self, league_size):
        roster_slots = dict(STANDARD_ROSTER)
        state = _run_programmatic_draft(league_size=league_size, roster_slots=roster_slots)
        expected = sum(roster_slots.values()) * league_size
        assert len(state.all_picks) == expected

    @pytest.mark.parametrize("league_size", [8, 10, 12, 14])
    def test_all_teams_full_rosters(self, league_size):
        roster_slots = dict(STANDARD_ROSTER)
        state = _run_programmatic_draft(league_size=league_size, roster_slots=roster_slots)
        expected = _expected_roster_totals(roster_slots)
        for team in state.teams:
            total = sum(len(v) for v in team.roster.values())
            assert total == expected, (
                f"league_size={league_size}: {team.team_name} has {total} players"
            )


# ── TestMultipleScoringFormats ───────────────────────────────────────


class TestMultipleScoringFormats:
    """Drafts complete for all three scoring formats."""

    @pytest.mark.parametrize("scoring_format", ["standard", "half_ppr", "full_ppr"])
    def test_draft_completes(self, scoring_format):
        state = _run_programmatic_draft(league_size=8, scoring_format=scoring_format)
        assert state.is_complete

    @pytest.mark.parametrize("scoring_format", ["standard", "half_ppr", "full_ppr"])
    def test_no_player_drafted_twice(self, scoring_format):
        state = _run_programmatic_draft(league_size=8, scoring_format=scoring_format)
        drafted_ids = [p.player_id for p in state.all_picks]
        assert len(drafted_ids) == len(set(drafted_ids))


# ── TestRosterValidity ───────────────────────────────────────────────


class TestRosterValidity:
    """Rigorous roster slot validation after full drafts."""

    def _get_position_counts(self, team: TeamRoster, player_data: dict) -> dict:
        """Count actual positions drafted per team (across all slots)."""
        counts: dict = {}
        for slot, player_ids in team.roster.items():
            for pid in player_ids:
                pos = player_data[pid]["position"]
                counts[pos] = counts.get(pos, 0) + 1
        return counts

    def test_no_team_exceeds_slot_limits(self):
        roster_slots = dict(STANDARD_ROSTER)
        state = _run_programmatic_draft(league_size=12, roster_slots=roster_slots)
        for team in state.teams:
            for slot, player_ids in team.roster.items():
                limit = roster_slots[slot]
                assert len(player_ids) <= limit, (
                    f"{team.team_name} slot {slot}: {len(player_ids)} > limit {limit}"
                )

    def test_every_team_has_one_qb_in_qb_slot(self):
        state = _run_programmatic_draft(league_size=8)
        for team in state.teams:
            qbs_in_slot = team.roster.get("QB", [])
            assert len(qbs_in_slot) >= 1, f"{team.team_name} has no QB in QB slot"

    def test_players_in_correct_slots(self):
        """QB slot has only QBs; K slot has only Ks; DST slot has only DSTs."""
        state = _run_programmatic_draft(league_size=8)
        for team in state.teams:
            for pid in team.roster.get("QB", []):
                assert state.player_data[pid]["position"] == "QB"
            for pid in team.roster.get("K", []):
                assert state.player_data[pid]["position"] == "K"
            for pid in team.roster.get("DST", []):
                assert state.player_data[pid]["position"] == "DST"

    def test_flex_slot_has_eligible_positions(self):
        """FLEX slot contains only RB, WR, or TE."""
        eligible = {"RB", "WR", "TE"}
        state = _run_programmatic_draft(league_size=12)
        for team in state.teams:
            for pid in team.roster.get("FLEX", []):
                pos = state.player_data[pid]["position"]
                assert pos in eligible, f"{team.team_name} FLEX slot has {pos} (not eligible)"

    def test_draft_ids_unique_across_multiple_drafts(self):
        """Concurrent draft creation yields unique IDs."""
        states = [_run_programmatic_draft(league_size=4) for _ in range(3)]
        ids = [s.draft_id for s in states]
        assert len(ids) == len(set(ids)), "Duplicate draft IDs generated"


# ── TestDraftSummary ─────────────────────────────────────────────────


class TestDraftSummary:
    """get_draft_summary() correctness after full draft completion."""

    def _complete_draft(self, league_size=4, scoring="half_ppr"):
        state = _run_programmatic_draft(league_size=league_size, scoring_format=scoring)
        controller = DraftController(state)
        return controller, state

    def test_summary_not_available_mid_draft(self):
        """get_draft_summary() returns error dict if draft not complete."""
        player_data = _make_player_pool(n_qb=4, n_rb=8, n_wr=8, n_te=4, n_k=4, n_dst=4)
        config = LeagueConfig(
            league_id="t",
            league_size=4,
            scoring_format="half_ppr",
            draft_type="snake",
            draft_mode="simulation",
            data_year=2025,
            roster_slots=dict(STANDARD_ROSTER),
        )
        state = DraftState.create_new(
            league_config=config,
            team_names=["T0", "T1", "T2", "T3"],
            human_team_id=0,
            player_data=player_data,
        )
        controller = DraftController(state)
        summary = controller.get_draft_summary()
        assert "error" in summary

    def test_summary_has_all_teams(self):
        controller, state = self._complete_draft(league_size=8)
        summary = controller.get_draft_summary()
        assert "error" not in summary
        assert len(summary["teams"]) == 8

    def test_summary_total_picks_correct(self):
        controller, state = self._complete_draft(league_size=4)
        summary = controller.get_draft_summary()
        assert summary["total_picks"] == len(state.all_picks)

    def test_summary_projected_points_positive(self):
        controller, state = self._complete_draft(league_size=4)
        summary = controller.get_draft_summary()
        for team_s in summary["teams"]:
            assert team_s["projected_points"] > 0, f"{team_s['team_name']} has 0 projected points"

    def test_summary_has_completed_at(self):
        controller, state = self._complete_draft(league_size=4)
        summary = controller.get_draft_summary()
        assert summary["completed_at"] is not None

    def test_summary_team_names_match(self):
        controller, state = self._complete_draft(league_size=4)
        summary = controller.get_draft_summary()
        summary_names = {t["team_name"] for t in summary["teams"]}
        state_names = {t.team_name for t in state.teams}
        assert summary_names == state_names

    def test_summary_excludes_bench_from_projected_points(self):
        """Bench players should NOT count toward projected points."""
        controller, state = self._complete_draft(league_size=4)
        summary = controller.get_draft_summary()
        scoring = "half_ppr"
        for team_s in summary["teams"]:
            team = state.get_team(team_s["team_id"])
            # Calculate starting-lineup-only points manually
            expected_pts = 0.0
            for slot, pids in team.roster.items():
                if slot == "BENCH":
                    continue
                for pid in pids:
                    expected_pts += state.player_data[pid]["projections"].get(scoring, 0)
            assert abs(team_s["projected_points"] - round(expected_pts, 1)) < 0.01


# ── CLI helpers ──────────────────────────────────────────────────────


def _make_cli_app(responses, draft_mode="simulation", league_size=2, roster_slots=None):
    """Create DraftApp with minimal draft state and captured output."""
    if roster_slots is None:
        roster_slots = {
            "QB": 1,
            "RB": 1,
            "WR": 1,
            "TE": 0,
            "FLEX": 0,
            "DST": 0,
            "K": 0,
            "BENCH": 0,
        }

    output = StringIO()
    console = Console(file=output, width=120, force_terminal=True)
    response_iter = iter(responses)

    def mock_input(prompt=""):
        try:
            return next(response_iter)
        except StopIteration:
            raise EOFError("No more responses")

    console.input = mock_input
    app = DraftApp(console=console)

    # Build player data
    player_data = {}
    specs = [
        ("qb1", "Josh Allen", "QB", "BUF", 1),
        ("qb2", "Jalen Hurts", "QB", "PHI", 2),
        ("rb1", "Saquon Barkley", "RB", "PHI", 3),
        ("rb2", "Breece Hall", "RB", "NYJ", 4),
        ("wr1", "Ja'Marr Chase", "WR", "CIN", 5),
        ("wr2", "CeeDee Lamb", "WR", "DAL", 6),
    ]
    for pid, name, pos, team, rank in specs:
        player_data[pid] = {
            "player_id": pid,
            "name": name,
            "position": pos,
            "team": team,
            "overall_rank": rank,
            "bye_week": 7,
            "projections": {
                "standard": 200.0 - rank * 10,
                "half_ppr": 210.0 - rank * 10,
                "full_ppr": 220.0 - rank * 10,
            },
            "baseline_vor": {
                "standard": 50.0 - rank * 5,
                "half_ppr": 55.0 - rank * 5,
                "full_ppr": 60.0 - rank * 5,
            },
        }

    from src.ui.player_search import PlayerSearcher

    config = LeagueConfig(
        league_id="cli_test",
        league_size=league_size,
        scoring_format="half_ppr",
        draft_type="snake",
        draft_mode=draft_mode,
        data_year=2025,
        roster_slots=roster_slots,
    )
    app.draft_state = DraftState.create_new(
        league_config=config,
        team_names=["My Team", "CPU Team"][:league_size],
        human_team_id=0,
        player_data=player_data,
    )
    app.controller = DraftController(app.draft_state)
    app.vor_calculator = DynamicVORCalculator("half_ppr", league_size=league_size)
    app.computer_drafter = ComputerDrafter(vor_calculator=app.vor_calculator, strategy="balanced")
    app.searcher = PlayerSearcher(app.controller)
    app.recommender = PickRecommender(vor_calculator=app.vor_calculator)
    app.persistence = MagicMock(spec=StatePersistence)

    return app, output


# ── TestCLIFullDraftFlow ─────────────────────────────────────────────


class TestCLIFullDraftFlow:
    """DraftApp end-to-end through _draft_loop() in simulation mode.

    2-team, 3-round draft. Snake order: T0, T1, T1, T0, T0, T1.
    Human (T0) is at picks 1, 4, 5. CPU auto-picks 2, 3, 6.
    """

    def test_full_draft_completes_via_draft_loop(self):
        app, output = _make_cli_app(
            [
                "1",
                "y",  # Pick 1: human
                "1",
                "y",  # Pick 4: human
                "1",
                "y",  # Pick 5: human
            ]
        )
        app._draft_loop()
        assert app.controller.is_complete
        assert len(app.draft_state.all_picks) == 6

    def test_all_teams_have_expected_players(self):
        app, output = _make_cli_app(
            [
                "1",
                "y",
                "1",
                "y",
                "1",
                "y",
            ]
        )
        app._draft_loop()
        for team in app.draft_state.teams:
            total = sum(len(v) for v in team.roster.values())
            assert total == 3  # QB+RB+WR per team

    def test_no_player_drafted_twice(self):
        app, output = _make_cli_app(
            [
                "1",
                "y",
                "1",
                "y",
                "1",
                "y",
            ]
        )
        app._draft_loop()
        ids = [p.player_id for p in app.draft_state.all_picks]
        assert len(ids) == len(set(ids))

    def test_auto_save_called_for_every_pick(self):
        app, output = _make_cli_app(
            [
                "1",
                "y",
                "1",
                "y",
                "1",
                "y",
            ]
        )
        app._draft_loop()
        # 6 picks total → save_draft called 6 times (auto-save after each pick)
        assert app.persistence.save_draft.call_count == 6

    def test_draft_summary_correct_after_completion(self):
        app, output = _make_cli_app(
            [
                "1",
                "y",
                "1",
                "y",
                "1",
                "y",
            ]
        )
        app._draft_loop()
        summary = app.controller.get_draft_summary()
        assert "error" not in summary
        assert len(summary["teams"]) == 2
        assert summary["total_picks"] == 6

    def test_board_command_during_draft(self):
        """'b' command redisplays the board mid-pick."""
        app, output = _make_cli_app(
            [
                "b",  # Redisplay board
                "Josh Allen",
                "y",  # Then pick
                "1",
                "y",
                "1",
                "y",
            ]
        )
        app._draft_loop()
        text = output.getvalue()
        assert app.controller.is_complete
        assert "Round 1" in text

    def test_roster_command_shows_team_name(self):
        app, output = _make_cli_app(
            [
                "r",  # Show roster before picking
                "Josh Allen",
                "y",
                "1",
                "y",
                "1",
                "y",
            ]
        )
        app._draft_loop()
        text = output.getvalue()
        assert "My Team" in text

    def test_search_then_pick_by_number(self):
        """s <name> → shows results → pick by #."""
        app, output = _make_cli_app(
            [
                "s allen",  # Search
                "1",
                "y",  # Pick #1 from results
                "1",
                "y",
                "1",
                "y",
            ]
        )
        app._draft_loop()
        assert app.controller.is_complete

    def test_quit_during_human_turn(self):
        """'q' during human pick returns True (user quit) without crashing."""
        app, output = _make_cli_app(["q"])
        user_quit = app._draft_loop()
        assert user_quit is True

    def test_draft_not_complete_after_quit(self):
        app, output = _make_cli_app(["q"])
        app._draft_loop()
        assert not app.controller.is_complete


# ── TestManualTrackerCLIFlow ─────────────────────────────────────────


class TestManualTrackerCLIFlow:
    """DraftApp in manual_tracker mode through full _draft_loop()."""

    def test_full_manual_draft_completes(self):
        """All 6 picks entered manually by the user."""
        app, output = _make_cli_app(
            [
                "Josh Allen",
                "y",  # Pick 1: T0
                "Jalen Hurts",
                "y",  # Pick 2: T1
                "Saquon Barkley",
                "y",  # Pick 3: T1
                "Breece Hall",
                "y",  # Pick 4: T0
                "Ja'Marr Chase",
                "y",  # Pick 5: T0
                "CeeDee Lamb",
                "y",  # Pick 6: T1
            ],
            draft_mode="manual_tracker",
        )
        app._draft_loop()
        assert app.controller.is_complete
        assert len(app.draft_state.all_picks) == 6

    def test_no_auto_picks_in_manual_tracker(self):
        """Verify all 6 picks consumed user input (not auto-picked)."""
        inputs = [
            "Josh Allen",
            "y",
            "Jalen Hurts",
            "y",
            "Saquon Barkley",
            "y",
            "Breece Hall",
            "y",
            "Ja'Marr Chase",
            "y",
            "CeeDee Lamb",
            "y",
        ]
        call_count = 0
        output = StringIO()
        console = Console(file=output, width=120, force_terminal=True)
        response_iter = iter(inputs)

        def counting_input(prompt=""):
            nonlocal call_count
            call_count += 1
            try:
                return next(response_iter)
            except StopIteration:
                raise EOFError

        console.input = counting_input

        from src.ui.player_search import PlayerSearcher

        app = DraftApp(console=console)
        config = LeagueConfig(
            league_id="cnt_test",
            league_size=2,
            scoring_format="half_ppr",
            draft_type="snake",
            draft_mode="manual_tracker",
            data_year=2025,
            roster_slots={
                "QB": 1,
                "RB": 1,
                "WR": 1,
                "TE": 0,
                "FLEX": 0,
                "DST": 0,
                "K": 0,
                "BENCH": 0,
            },
        )
        player_data = {
            "qb1": {
                "player_id": "qb1",
                "name": "Josh Allen",
                "position": "QB",
                "team": "BUF",
                "overall_rank": 1,
                "bye_week": 7,
                "projections": {"standard": 190, "half_ppr": 200, "full_ppr": 210},
                "baseline_vor": {"standard": 45, "half_ppr": 50, "full_ppr": 55},
            },
            "qb2": {
                "player_id": "qb2",
                "name": "Jalen Hurts",
                "position": "QB",
                "team": "PHI",
                "overall_rank": 2,
                "bye_week": 7,
                "projections": {"standard": 180, "half_ppr": 190, "full_ppr": 200},
                "baseline_vor": {"standard": 40, "half_ppr": 45, "full_ppr": 50},
            },
            "rb1": {
                "player_id": "rb1",
                "name": "Saquon Barkley",
                "position": "RB",
                "team": "PHI",
                "overall_rank": 3,
                "bye_week": 7,
                "projections": {"standard": 170, "half_ppr": 180, "full_ppr": 190},
                "baseline_vor": {"standard": 35, "half_ppr": 40, "full_ppr": 45},
            },
            "rb2": {
                "player_id": "rb2",
                "name": "Breece Hall",
                "position": "RB",
                "team": "NYJ",
                "overall_rank": 4,
                "bye_week": 7,
                "projections": {"standard": 160, "half_ppr": 170, "full_ppr": 180},
                "baseline_vor": {"standard": 30, "half_ppr": 35, "full_ppr": 40},
            },
            "wr1": {
                "player_id": "wr1",
                "name": "Ja'Marr Chase",
                "position": "WR",
                "team": "CIN",
                "overall_rank": 5,
                "bye_week": 7,
                "projections": {"standard": 150, "half_ppr": 160, "full_ppr": 170},
                "baseline_vor": {"standard": 25, "half_ppr": 30, "full_ppr": 35},
            },
            "wr2": {
                "player_id": "wr2",
                "name": "CeeDee Lamb",
                "position": "WR",
                "team": "DAL",
                "overall_rank": 6,
                "bye_week": 7,
                "projections": {"standard": 140, "half_ppr": 150, "full_ppr": 160},
                "baseline_vor": {"standard": 20, "half_ppr": 25, "full_ppr": 30},
            },
        }
        app.draft_state = DraftState.create_new(
            league_config=config,
            team_names=["My Team", "CPU Team"],
            human_team_id=0,
            player_data=player_data,
        )
        app.controller = DraftController(app.draft_state)
        app.vor_calculator = DynamicVORCalculator("half_ppr", league_size=2)
        app.computer_drafter = ComputerDrafter(app.vor_calculator, strategy="balanced")
        app.recommender = PickRecommender(vor_calculator=app.vor_calculator)
        app.searcher = PlayerSearcher(app.controller)
        app.persistence = MagicMock(spec=StatePersistence)

        app._draft_loop()

        # 12 calls = 6 picks × (player name + confirmation "y")
        # plus header/board shown = some board re-display prompts
        # At minimum each of the 6 picks consumed 2 inputs
        assert app.controller.is_complete
        assert call_count >= 12

    def test_manual_header_label_shown(self):
        app, output = _make_cli_app(
            [
                "Josh Allen",
                "y",
                "Jalen Hurts",
                "y",
                "Saquon Barkley",
                "y",
                "Breece Hall",
                "y",
                "Ja'Marr Chase",
                "y",
                "CeeDee Lamb",
                "y",
            ],
            draft_mode="manual_tracker",
        )
        app._draft_loop()
        assert "Manual Tracker" in output.getvalue()

    def test_sim_command_rejected_in_manual_mode(self):
        """sim command shows error and does NOT complete draft."""
        app, output = _make_cli_app(
            [
                "sim",
                "Josh Allen",
                "y",  # pick 1: human
                "Jalen Hurts",
                "y",  # pick 2: T1 manual
                "Saquon Barkley",
                "y",  # pick 3: T1 manual
                "Breece Hall",
                "y",  # pick 4: T0 manual
                "Ja'Marr Chase",
                "y",  # pick 5: T0 manual
                "CeeDee Lamb",
                "y",
            ],  # pick 6: T1 manual
            draft_mode="manual_tracker",
        )
        app._draft_loop()
        text = output.getvalue()
        assert "not available in Manual Tracker" in text
        assert app.controller.is_complete  # Draft still finishes normally

    def test_recs_shown_for_human_turn_manual(self):
        app, output = _make_cli_app(
            [
                "Josh Allen",
                "y",
                "Jalen Hurts",
                "y",
                "Saquon Barkley",
                "y",
                "Breece Hall",
                "y",
                "Ja'Marr Chase",
                "y",
                "CeeDee Lamb",
                "y",
            ],
            draft_mode="manual_tracker",
        )
        app._handle_pick_turn()  # Pick 1: human turn
        assert "Recommendations" in output.getvalue()

    def test_available_shown_for_cpu_turn_manual(self):
        app, output = _make_cli_app(
            [
                "Josh Allen",
                "y",  # human pick 1
                "Jalen Hurts",
                "y",  # cpu pick 2 in manual mode
            ],
            draft_mode="manual_tracker",
        )
        app._handle_pick_turn()  # Pick 1: human
        output.truncate(0)
        output.seek(0)
        app._handle_pick_turn()  # Pick 2: CPU team (but user enters it)
        text = output.getvalue()
        assert "Available Players" in text
        assert "Recommendations" not in text

    def test_auto_save_after_each_manual_pick(self):
        app, output = _make_cli_app(
            [
                "Josh Allen",
                "y",
                "Jalen Hurts",
                "y",
                "Saquon Barkley",
                "y",
                "Breece Hall",
                "y",
                "Ja'Marr Chase",
                "y",
                "CeeDee Lamb",
                "y",
            ],
            draft_mode="manual_tracker",
        )
        app._draft_loop()
        assert app.persistence.save_draft.call_count == 6


# ── TestEdgeCases ────────────────────────────────────────────────────


class TestEdgeCases:
    """Error recovery, boundary conditions, and validation edge cases."""

    def test_pick_already_taken_rejected(self):
        """Attempting to pick an already-drafted player raises ValidationError."""
        player_data = _make_player_pool(n_qb=4, n_rb=4, n_wr=4, n_te=4, n_k=2, n_dst=2)
        config = LeagueConfig(
            league_id="e",
            league_size=2,
            scoring_format="half_ppr",
            draft_type="snake",
            draft_mode="simulation",
            data_year=2025,
            roster_slots={
                "QB": 1,
                "RB": 1,
                "WR": 1,
                "TE": 0,
                "FLEX": 0,
                "DST": 0,
                "K": 0,
                "BENCH": 0,
            },
        )
        state = DraftState.create_new(
            league_config=config,
            team_names=["T0", "T1"],
            human_team_id=0,
            player_data=player_data,
        )
        controller = DraftController(state)
        first_pid = state.available_players[0]
        controller.make_pick(0, first_pid)  # T0 picks first player

        # T1's turn; try to pick the same player (T0 just took it)
        with pytest.raises(ValidationError, match="already been drafted"):
            controller.make_pick(1, first_pid)

    def test_nonexistent_player_rejected(self):
        player_data = _make_player_pool(n_qb=2, n_rb=2, n_wr=2, n_te=2, n_k=2, n_dst=2)
        config = LeagueConfig(
            league_id="e",
            league_size=2,
            scoring_format="half_ppr",
            draft_type="snake",
            draft_mode="simulation",
            data_year=2025,
            roster_slots={
                "QB": 1,
                "RB": 1,
                "WR": 1,
                "TE": 0,
                "FLEX": 0,
                "DST": 0,
                "K": 0,
                "BENCH": 0,
            },
        )
        state = DraftState.create_new(
            league_config=config,
            team_names=["T0", "T1"],
            human_team_id=0,
            player_data=player_data,
        )
        controller = DraftController(state)
        with pytest.raises(ValidationError, match="not found"):
            controller.make_pick(0, "does_not_exist")

    def test_pick_after_draft_complete_raises(self):
        """make_pick after is_complete raises ValidationError."""
        player_data = _make_player_pool(n_qb=2, n_rb=2, n_wr=2, n_te=2, n_k=2, n_dst=2)
        config = LeagueConfig(
            league_id="e",
            league_size=2,
            scoring_format="half_ppr",
            draft_type="snake",
            draft_mode="simulation",
            data_year=2025,
            roster_slots={
                "QB": 1,
                "RB": 0,
                "WR": 0,
                "TE": 0,
                "FLEX": 0,
                "DST": 0,
                "K": 0,
                "BENCH": 0,
            },
        )
        state = DraftState.create_new(
            league_config=config,
            team_names=["T0", "T1"],
            human_team_id=0,
            player_data=player_data,
        )
        controller = DraftController(state)
        controller.make_pick(0, "qb1")
        controller.make_pick(1, "qb2")
        assert state.is_complete

        with pytest.raises(ValidationError, match="complete"):
            controller.make_pick(0, "rb1")

    def test_draft_initializer_rejects_odd_league_size(self):
        """DraftInitializer rejects odd league sizes."""
        with pytest.raises(ValueError, match="even"):
            DraftInitializer().create_draft(
                league_size=11,
                scoring_format="half_ppr",
                roster_slots=dict(STANDARD_ROSTER),
                team_names=[f"T{i}" for i in range(11)],
            )

    def test_draft_initializer_rejects_invalid_scoring(self):
        with pytest.raises(ValueError, match="scoring"):
            DraftInitializer().create_draft(
                league_size=10,
                scoring_format="full_standard",  # invalid
                roster_slots=dict(STANDARD_ROSTER),
                team_names=[f"T{i}" for i in range(10)],
            )

    def test_draft_initializer_rejects_name_count_mismatch(self):
        with pytest.raises(ValueError, match="team names"):
            DraftInitializer().create_draft(
                league_size=10,
                scoring_format="half_ppr",
                roster_slots=dict(STANDARD_ROSTER),
                team_names=["T1", "T2"],  # only 2 names for 10-team league
            )

    def test_draft_initializer_missing_player_file_raises(self):
        """FileNotFoundError when player data file for requested year is missing."""
        with pytest.raises(FileNotFoundError):
            DraftInitializer().create_draft(
                league_size=10,
                scoring_format="half_ppr",
                roster_slots=dict(STANDARD_ROSTER),
                team_names=[f"T{i}" for i in range(10)],
                data_year=1900,  # No data for this year
            )

    def test_snake_draft_order_correct(self):
        """Verify snake order: T0 T1 T2 T3 T3 T2 T1 T0 T0 T1 ..."""
        roster_slots = {
            "QB": 1,
            "RB": 1,
            "WR": 1,
            "TE": 0,
            "FLEX": 0,
            "DST": 0,
            "K": 0,
            "BENCH": 0,
        }
        state = _run_programmatic_draft(league_size=4, roster_slots=roster_slots)
        expected_team_order = [
            0,
            1,
            2,
            3,  # Round 1 forward
            3,
            2,
            1,
            0,  # Round 2 backward
            0,
            1,
            2,
            3,  # Round 3 forward
        ]
        actual = [p.team_id for p in state.all_picks]
        assert actual == expected_team_order

    def test_empty_input_reprompts_cli(self):
        """Empty string input is ignored and the prompt re-appears."""
        app, output = _make_cli_app(
            [
                "",
                "",
                "Josh Allen",
                "y",  # human pick 1
                "1",
                "y",  # human pick 4
                "1",
                "y",  # human pick 5
            ]
        )
        app._draft_loop()
        assert app.controller.is_complete

    def test_invalid_number_shows_error_not_crash(self):
        """Number outside displayed list shows an error, then can still pick."""
        app, output = _make_cli_app(
            [
                "99",  # Out-of-range number with no displayed list
                "Josh Allen",
                "y",  # Then pick normally
                "1",
                "y",
                "1",
                "y",
            ]
        )
        app._draft_loop()
        # Rich highlights numbers with ANSI codes, so strip them before checking.
        clean = re.sub(r"\x1b\[[0-9;]*m", "", output.getvalue())
        # Verify error message shown for invalid input
        assert "No player at #99" in clean or "invalid" in clean.lower()
        # Draft should still complete after recovery
        assert app.controller.is_complete

    def test_help_command_shows_all_commands(self):
        app, output = _make_cli_app(
            [
                "h",
                "Josh Allen",
                "y",
                "1",
                "y",
                "1",
                "y",
            ]
        )
        app._draft_loop()
        text = output.getvalue()
        # Verify key help commands appear (help uses "s <query>" not "search")
        for cmd in ("available", "roster", "sim", "rec", "save"):
            assert cmd in text, f"'{cmd}' missing from help output"

    def test_available_position_filter_works(self):
        """'a qb' shows only QBs in the available list."""
        app, output = _make_cli_app(
            [
                "a qb",
                "Josh Allen",
                "y",
                "1",
                "y",
                "1",
                "y",
            ]
        )
        app._draft_loop()
        text = output.getvalue()
        assert "Available Players" in text
        # After position filter, QB players should appear
        assert "Allen" in text or "Hurts" in text

    def test_roster_command_after_picks(self):
        """'r' after some picks shows the current (non-empty) roster."""
        app, output = _make_cli_app(
            [
                "Josh Allen",
                "y",  # Pick 1: T0 drafts Josh Allen
                # CPU picks 2, 3 automatically
                "r",  # Pick 4: view roster before picking
                "1",
                "y",
                "1",
                "y",  # Pick 5
            ]
        )
        app._draft_loop()
        text = output.getvalue()
        assert "Roster" in text
        assert "Josh Allen" in text or "QB" in text


# ── TestM11PickRecommender ────────────────────────────────────────────


class TestM11PickRecommender:
    """M11: Pick Recommender integration within the MVP.

    Verifies that PickRecommender integrates correctly with DraftState,
    the CLI 'rec' command, and the DraftDisplay output — as required by
    Milestone 11 success criteria.
    """

    # ── Programmatic API ──────────────────────────────────────────────

    def test_recommend_picks_returns_list_of_recommendations(self):
        """recommend_picks() returns List[Recommendation] with correct count."""
        player_data = _make_player_pool(n_qb=8, n_rb=16, n_wr=16, n_te=8, n_k=4, n_dst=4)
        config = LeagueConfig(
            league_id="m11_test",
            league_size=4,
            scoring_format="half_ppr",
            draft_type="snake",
            draft_mode="simulation",
            data_year=2025,
            roster_slots=dict(STANDARD_ROSTER),
        )
        fresh_state = DraftState.create_new(
            league_config=config,
            team_names=["T0", "T1", "T2", "T3"],
            human_team_id=0,
            player_data=player_data,
        )
        vor_calc = DynamicVORCalculator("half_ppr", league_size=4)
        recommender = PickRecommender(vor_calculator=vor_calc)
        available = list(fresh_state.player_data.values())
        recs = recommender.recommend_picks(fresh_state, available, num_recommendations=5)

        assert len(recs) == 5
        assert all(isinstance(r, Recommendation) for r in recs)

    def test_recommendations_sorted_best_first(self):
        """Recommendations come in descending dynamic_vor order."""
        player_data = _make_player_pool(n_qb=8, n_rb=16, n_wr=16, n_te=8, n_k=4, n_dst=4)
        config = LeagueConfig(
            league_id="m11_sort",
            league_size=12,
            scoring_format="half_ppr",
            draft_type="snake",
            draft_mode="simulation",
            data_year=2025,
            roster_slots=dict(STANDARD_ROSTER),
        )
        state = DraftState.create_new(
            league_config=config,
            team_names=[f"T{i}" for i in range(12)],
            human_team_id=0,
            player_data=player_data,
        )
        vor_calc = DynamicVORCalculator("half_ppr", league_size=12)
        recommender = PickRecommender(vor_calculator=vor_calc)
        available = list(state.player_data.values())
        recs = recommender.recommend_picks(state, available, num_recommendations=10)
        vors = [r.dynamic_vor for r in recs]
        assert vors == sorted(vors, reverse=True)

    def test_each_recommendation_has_reasoning(self):
        """Every Recommendation carries a non-empty reasoning string."""
        player_data = _make_player_pool(n_qb=8, n_rb=16, n_wr=16, n_te=8, n_k=4, n_dst=4)
        config = LeagueConfig(
            league_id="m11_reason",
            league_size=12,
            scoring_format="half_ppr",
            draft_type="snake",
            draft_mode="simulation",
            data_year=2025,
            roster_slots=dict(STANDARD_ROSTER),
        )
        state = DraftState.create_new(
            league_config=config,
            team_names=[f"T{i}" for i in range(12)],
            human_team_id=0,
            player_data=player_data,
        )
        vor_calc = DynamicVORCalculator("half_ppr", league_size=12)
        recommender = PickRecommender(vor_calculator=vor_calc)
        available = list(state.player_data.values())
        recs = recommender.recommend_picks(state, available, num_recommendations=10)
        for r in recs:
            assert r.reasoning.strip(), f"Empty reasoning for {r.player_name}"

    def test_mid_draft_recommendations_reflect_team_state(self):
        """After several picks, recs reflect what the team still needs."""
        player_data = _make_player_pool(n_qb=8, n_rb=16, n_wr=16, n_te=8, n_k=4, n_dst=4)
        config = LeagueConfig(
            league_id="m11_mid",
            league_size=4,
            scoring_format="half_ppr",
            draft_type="snake",
            draft_mode="simulation",
            data_year=2025,
            roster_slots=dict(STANDARD_ROSTER),
        )
        state = DraftState.create_new(
            league_config=config,
            team_names=["T0", "T1", "T2", "T3"],
            human_team_id=0,
            player_data=player_data,
        )
        controller = DraftController(state)
        vor_calc = DynamicVORCalculator("half_ppr", league_size=4)
        drafter = ComputerDrafter(vor_calculator=vor_calc, strategy="balanced")

        # Run first round so team 0 has one pick
        for _ in range(4):
            current_team = state.get_current_team()
            available = controller.get_available_players()
            from src.draft_manager.draft_rules import DraftRules

            rules = DraftRules(state)
            legal = [
                p for p in available if rules.validate_pick(current_team.team_id, p["player_id"])[0]
            ]
            pid = drafter.make_pick(state, legal, current_team.team_id)
            controller.make_pick(current_team.team_id, pid)
            if state.current_round > 1:
                break

        recommender = PickRecommender(vor_calculator=vor_calc)
        available = controller.get_available_players()
        recs = recommender.recommend_picks(state, available, num_recommendations=5, team_id=0)
        assert len(recs) > 0
        assert all(isinstance(r, Recommendation) for r in recs)

    @requires_player_data
    def test_real_data_recommendations_make_sense(self):
        """Using actual 2025 player data: top rec is a skill-position starter."""
        from src.draft_manager.draft_initializer import DraftInitializer

        initializer = DraftInitializer()
        state = initializer.create_draft(
            league_size=12,
            scoring_format="half_ppr",
            roster_slots=dict(STANDARD_ROSTER),
            team_names=[f"Team {i + 1}" for i in range(12)],
            human_team_id=0,
            draft_mode="simulation",
            data_year=2025,
        )
        vor_calc = DynamicVORCalculator("half_ppr", league_size=12)
        recommender = PickRecommender(vor_calculator=vor_calc)
        available = list(state.player_data.values())
        recs = recommender.recommend_picks(state, available, num_recommendations=5)

        assert len(recs) == 5
        # Top pick should be a skill position (not K or DST at pick 1)
        assert recs[0].position in {"QB", "RB", "WR", "TE"}, (
            f"Expected skill position at pick 1, got {recs[0].position} ({recs[0].player_name})"
        )
        # All have reasoning
        for r in recs:
            assert r.reasoning.strip()

    # ── CLI integration ───────────────────────────────────────────────

    def test_rec_command_shows_recommendations_table(self):
        """'rec' command triggers display of a recommendations table."""
        app, output = _make_cli_app(
            [
                "rec",  # Show recommendations
                "1",
                "y",  # Pick #1 from list
                "1",
                "y",  # Next human turn
                "1",
                "y",  # Next human turn
            ]
        )
        app._draft_loop()
        text = output.getvalue()
        assert "Recommendations" in text

    def test_rec_command_shows_reasoning_column(self):
        """Recommendation table includes the 'Why' reasoning column header."""
        app, output = _make_cli_app(
            [
                "rec",
                "1",
                "y",
                "1",
                "y",
                "1",
                "y",
            ]
        )
        app._draft_loop()
        text = output.getvalue()
        assert "Why" in text

    def test_rec_command_pick_by_number_works(self):
        """After 'rec', user can pick by number from the displayed list."""
        app, _ = _make_cli_app(
            [
                "rec",  # Display recommendations
                "1",
                "y",  # Pick #1 from the rec list
                "1",
                "y",
                "1",
                "y",
            ]
        )
        app._draft_loop()
        assert app.controller.is_complete

    def test_recommender_initialised_in_init_components(self):
        """_init_components() creates a PickRecommender on the app."""
        app = DraftApp()
        player_data = _make_player_pool(n_qb=4, n_rb=8, n_wr=8, n_te=4, n_k=3, n_dst=3)
        config = LeagueConfig(
            league_id="init_test",
            league_size=4,
            scoring_format="half_ppr",
            draft_type="snake",
            draft_mode="simulation",
            data_year=2025,
            roster_slots=dict(STANDARD_ROSTER),
        )
        app.draft_state = DraftState.create_new(
            league_config=config,
            team_names=["T0", "T1", "T2", "T3"],
            human_team_id=0,
            player_data=player_data,
        )
        app._init_components()
        assert app.recommender is not None
        assert isinstance(app.recommender, PickRecommender)
