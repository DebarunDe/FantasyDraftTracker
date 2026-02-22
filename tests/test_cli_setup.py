"""Tests for CLI setup wizard."""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from src.draft_manager.state_persistence import StatePersistence
from src.ui.setup_wizard import SetupWizard


# ── Helpers ──────────────────────────────────────────────────────────


def _make_wizard(responses, persistence=None):
    """Create a SetupWizard with mocked Console.input()."""
    output = StringIO()
    console = Console(file=output, width=120, force_terminal=True)

    # Mock the input method to return our prepared responses
    response_iter = iter(responses)
    original_input = console.input

    def mock_input(prompt=""):
        # Still write the prompt to capture output
        try:
            return next(response_iter)
        except StopIteration:
            raise EOFError("No more responses")

    console.input = mock_input

    if persistence is None:
        persistence = MagicMock(spec=StatePersistence)
        persistence.list_saved_drafts.return_value = []

    return SetupWizard(console, persistence), output


# ── Main menu tests ──────────────────────────────────────────────────


class TestMainMenu:
    def test_quit_returns_quit_action(self):
        wizard, _ = _make_wizard(["3"])
        result = wizard.run()
        assert result == {"action": "quit"}

    def test_invalid_then_quit(self):
        wizard, _ = _make_wizard(["x", "3"])
        result = wizard.run()
        assert result == {"action": "quit"}


# ── League size tests ────────────────────────────────────────────────


class TestConfigureLeagueSize:
    def test_default_value(self):
        wizard, _ = _make_wizard([""])
        result = wizard._configure_league_size()
        assert result == 12

    def test_valid_size(self):
        # Mock to return "8"
        wizard, _ = _make_wizard(["8"])
        result = wizard._configure_league_size()
        assert result == 8

    def test_rejects_odd_number(self):
        wizard, _ = _make_wizard(["7", "8"])
        result = wizard._configure_league_size()
        assert result == 8

    def test_rejects_out_of_range(self):
        wizard, _ = _make_wizard(["30", "10"])
        result = wizard._configure_league_size()
        assert result == 10

    def test_rejects_non_number(self):
        wizard, _ = _make_wizard(["abc", "12"])
        result = wizard._configure_league_size()
        assert result == 12

    def test_empty_returns_default(self):
        wizard, _ = _make_wizard([""])
        result = wizard._configure_league_size()
        assert result == 12


# ── Scoring format tests ─────────────────────────────────────────────


class TestConfigureScoringFormat:
    def test_default_value(self):
        wizard, _ = _make_wizard([""])
        result = wizard._configure_scoring_format()
        assert result == "half_ppr"

    def test_standard(self):
        wizard, _ = _make_wizard(["1"])
        result = wizard._configure_scoring_format()
        assert result == "standard"

    def test_half_ppr(self):
        wizard, _ = _make_wizard(["2"])
        result = wizard._configure_scoring_format()
        assert result == "half_ppr"

    def test_full_ppr(self):
        wizard, _ = _make_wizard(["3"])
        result = wizard._configure_scoring_format()
        assert result == "full_ppr"

    def test_rejects_invalid(self):
        wizard, _ = _make_wizard(["5", "2"])
        result = wizard._configure_scoring_format()
        assert result == "half_ppr"


# ── Roster slots tests ──────────────────────────────────────────────


class TestConfigureRosterSlots:
    def test_default_roster(self):
        wizard, _ = _make_wizard(["Y"])
        result = wizard._configure_roster_slots()
        assert result["QB"] == 1
        assert result["RB"] == 2
        assert result["BENCH"] == 6

    def test_default_on_empty(self):
        wizard, _ = _make_wizard([""])
        result = wizard._configure_roster_slots()
        assert result["QB"] == 1

    def test_custom_roster(self):
        # "n" for custom, then values for each position
        wizard, _ = _make_wizard(["n", "2", "", "", "", "", "", "", ""])
        result = wizard._configure_roster_slots()
        assert result["QB"] == 2
        assert result["RB"] == 2  # Default used for empty


# ── Team names tests ─────────────────────────────────────────────────


class TestConfigureTeamNames:
    def test_auto_generate(self):
        wizard, _ = _make_wizard(["Y"])
        result = wizard._configure_team_names(4)
        assert result == ["Team 1", "Team 2", "Team 3", "Team 4"]

    def test_auto_generate_on_empty(self):
        wizard, _ = _make_wizard([""])
        result = wizard._configure_team_names(4)
        assert result == ["Team 1", "Team 2", "Team 3", "Team 4"]

    def test_custom_names(self):
        wizard, _ = _make_wizard(["n", "Alpha", "Beta", "", "Delta"])
        result = wizard._configure_team_names(4)
        assert result == ["Alpha", "Beta", "Team 3", "Delta"]


# ── Draft position tests ────────────────────────────────────────────


class TestConfigureDraftPosition:
    def test_default_position(self):
        wizard, _ = _make_wizard([""])
        result = wizard._configure_draft_position(12)
        assert result == 0  # 1-based "1" → 0-based 0

    def test_specific_position(self):
        wizard, _ = _make_wizard(["5"])
        result = wizard._configure_draft_position(12)
        assert result == 4  # 1-based "5" → 0-based 4

    def test_last_position(self):
        wizard, _ = _make_wizard(["12"])
        result = wizard._configure_draft_position(12)
        assert result == 11

    def test_rejects_out_of_range(self):
        wizard, _ = _make_wizard(["15", "3"])
        result = wizard._configure_draft_position(12)
        assert result == 2

    def test_rejects_zero(self):
        wizard, _ = _make_wizard(["0", "1"])
        result = wizard._configure_draft_position(12)
        assert result == 0


# ── Data year tests ──────────────────────────────────────────────────


class TestConfigureDataYear:
    def test_default_year(self):
        wizard, _ = _make_wizard([""])
        result = wizard._configure_data_year()
        assert result == 2025

    def test_custom_year(self):
        wizard, _ = _make_wizard(["2024"])
        result = wizard._configure_data_year()
        assert result == 2024


# ── Resume menu tests ───────────────────────────────────────────────


class TestResumeMenu:
    def test_no_saved_drafts(self):
        persistence = MagicMock(spec=StatePersistence)
        persistence.list_saved_drafts.return_value = []
        wizard, _ = _make_wizard([], persistence=persistence)

        result = wizard._show_resume_menu()
        assert result is None

    def test_back_returns_none(self):
        persistence = MagicMock(spec=StatePersistence)
        persistence.list_saved_drafts.return_value = [
            {
                "draft_id": "abc-123",
                "start_time": "2025-01-01T10:00:00",
                "is_complete": False,
                "current_round": 3,
                "current_pick": 25,
                "league_size": 12,
                "scoring_format": "half_ppr",
            }
        ]
        wizard, _ = _make_wizard(["back"], persistence=persistence)

        result = wizard._show_resume_menu()
        assert result is None

    def test_select_draft(self):
        mock_state = MagicMock()
        persistence = MagicMock(spec=StatePersistence)
        persistence.list_saved_drafts.return_value = [
            {
                "draft_id": "abc-123",
                "start_time": "2025-01-01T10:00:00",
                "is_complete": False,
                "current_round": 3,
                "current_pick": 25,
                "league_size": 12,
                "scoring_format": "half_ppr",
            }
        ]
        persistence.load_draft.return_value = mock_state
        wizard, _ = _make_wizard(["1"], persistence=persistence)

        result = wizard._show_resume_menu()
        assert result is not None
        assert result["action"] == "resume"
        assert result["draft_state"] is mock_state

    def test_sections_separated(self):
        """In-progress and completed drafts appear in separate tables."""
        persistence = MagicMock(spec=StatePersistence)
        persistence.list_saved_drafts.return_value = [
            {
                "draft_id": "in-progress-1",
                "start_time": "2025-01-02T10:00:00",
                "is_complete": False,
                "current_round": 3,
                "current_pick": 25,
                "league_size": 12,
                "scoring_format": "half_ppr",
            },
            {
                "draft_id": "completed-1",
                "start_time": "2025-01-01T10:00:00",
                "is_complete": True,
                "current_round": 15,
                "current_pick": 180,
                "league_size": 12,
                "scoring_format": "standard",
            },
        ]
        wizard, output = _make_wizard(["back"], persistence=persistence)

        wizard._show_resume_menu()
        text = output.getvalue()
        assert "In Progress" in text
        assert "Completed" in text
        # In-progress should appear before completed
        assert text.index("In Progress") < text.index("Completed")

    def test_only_in_progress_drafts(self):
        """When all drafts are in-progress, only that section shows."""
        persistence = MagicMock(spec=StatePersistence)
        persistence.list_saved_drafts.return_value = [
            {
                "draft_id": "ip-1",
                "start_time": "2025-01-01T10:00:00",
                "is_complete": False,
                "current_round": 2,
                "current_pick": 15,
                "league_size": 10,
                "scoring_format": "half_ppr",
            },
        ]
        wizard, output = _make_wizard(["back"], persistence=persistence)

        wizard._show_resume_menu()
        text = output.getvalue()
        assert "In Progress" in text
        assert "Completed" not in text

    def test_only_completed_drafts(self):
        """When all drafts are completed, only that section shows."""
        persistence = MagicMock(spec=StatePersistence)
        persistence.list_saved_drafts.return_value = [
            {
                "draft_id": "done-1",
                "start_time": "2025-01-01T10:00:00",
                "is_complete": True,
                "current_round": 15,
                "current_pick": 180,
                "league_size": 12,
                "scoring_format": "full_ppr",
            },
        ]
        wizard, output = _make_wizard(["back"], persistence=persistence)

        wizard._show_resume_menu()
        text = output.getvalue()
        assert "In Progress" not in text
        assert "Completed" in text

    def test_continuous_numbering_across_sections(self):
        """Numbers are continuous: in-progress get 1-N, completed get N+1-M."""
        persistence = MagicMock(spec=StatePersistence)
        persistence.list_saved_drafts.return_value = [
            {
                "draft_id": "ip-1",
                "start_time": "2025-01-02T10:00:00",
                "is_complete": False,
                "current_round": 3,
                "current_pick": 25,
                "league_size": 12,
                "scoring_format": "half_ppr",
            },
            {
                "draft_id": "done-1",
                "start_time": "2025-01-01T10:00:00",
                "is_complete": True,
                "current_round": 15,
                "current_pick": 180,
                "league_size": 12,
                "scoring_format": "standard",
            },
        ]
        # Select #2 (the completed draft)
        mock_state = MagicMock()
        persistence.load_draft.return_value = mock_state
        wizard, _ = _make_wizard(["2"], persistence=persistence)

        result = wizard._show_resume_menu()
        assert result is not None
        persistence.load_draft.assert_called_once_with("done-1")

    def test_delete_draft_confirmed(self):
        """Deleting a draft with 'y' confirmation calls persistence.delete_draft."""
        persistence = MagicMock(spec=StatePersistence)
        persistence.list_saved_drafts.side_effect = [
            [
                {
                    "draft_id": "abc-123",
                    "start_time": "2025-01-01T10:00:00",
                    "is_complete": False,
                    "current_round": 3,
                    "current_pick": 25,
                    "league_size": 12,
                    "scoring_format": "half_ppr",
                },
            ],
            [],  # After deletion, no drafts remain
        ]
        persistence.delete_draft.return_value = True
        # "d 1" to delete, "y" to confirm, then empty list returns None
        wizard, output = _make_wizard(["d 1", "y"], persistence=persistence)

        result = wizard._show_resume_menu()
        persistence.delete_draft.assert_called_once_with("abc-123")
        text = output.getvalue()
        assert "deleted" in text.lower()

    def test_delete_draft_cancelled(self):
        """Cancelling a delete does not call persistence.delete_draft."""
        persistence = MagicMock(spec=StatePersistence)
        persistence.list_saved_drafts.return_value = [
            {
                "draft_id": "abc-123",
                "start_time": "2025-01-01T10:00:00",
                "is_complete": False,
                "current_round": 3,
                "current_pick": 25,
                "league_size": 12,
                "scoring_format": "half_ppr",
            },
        ]
        # "d 1" to delete, "n" to cancel, then "back"
        wizard, output = _make_wizard(["d 1", "n", "back"], persistence=persistence)

        result = wizard._show_resume_menu()
        persistence.delete_draft.assert_not_called()
        assert result is None
        text = output.getvalue()
        assert "Cancelled" in text

    def test_delete_invalid_number(self):
        """Deleting with out-of-range number shows error."""
        persistence = MagicMock(spec=StatePersistence)
        persistence.list_saved_drafts.return_value = [
            {
                "draft_id": "abc-123",
                "start_time": "2025-01-01T10:00:00",
                "is_complete": False,
                "current_round": 3,
                "current_pick": 25,
                "league_size": 12,
                "scoring_format": "half_ppr",
            },
        ]
        wizard, output = _make_wizard(["d 5", "back"], persistence=persistence)

        result = wizard._show_resume_menu()
        assert result is None
        persistence.delete_draft.assert_not_called()

    def test_delete_no_number(self):
        """Typing 'd' without a number shows help message."""
        persistence = MagicMock(spec=StatePersistence)
        persistence.list_saved_drafts.return_value = [
            {
                "draft_id": "abc-123",
                "start_time": "2025-01-01T10:00:00",
                "is_complete": False,
                "current_round": 3,
                "current_pick": 25,
                "league_size": 12,
                "scoring_format": "half_ppr",
            },
        ]
        wizard, output = _make_wizard(["d", "back"], persistence=persistence)

        result = wizard._show_resume_menu()
        assert result is None
        text = output.getvalue()
        assert "to delete a draft" in text


# ── Draft mode tests ────────────────────────────────────────────────


class TestConfigureDraftMode:
    def test_default_returns_simulation(self):
        wizard, _ = _make_wizard([""])
        result = wizard._configure_draft_mode()
        assert result == "simulation"

    def test_option_1_returns_simulation(self):
        wizard, _ = _make_wizard(["1"])
        result = wizard._configure_draft_mode()
        assert result == "simulation"

    def test_option_2_returns_manual_tracker(self):
        wizard, _ = _make_wizard(["2"])
        result = wizard._configure_draft_mode()
        assert result == "manual_tracker"

    def test_rejects_invalid_then_accepts(self):
        wizard, _ = _make_wizard(["3", "x", "2"])
        result = wizard._configure_draft_mode()
        assert result == "manual_tracker"

    def test_confirmation_panel_shows_mode(self):
        """Confirmation panel includes the mode display string."""
        responses = [
            "1",   # New Draft
            "2",   # Manual Tracker
            "",    # League size default
            "",    # Scoring default
            "",    # Roster default
            "",    # Team names default
            "",    # Draft position default
            "",    # Data year default
            "Y",   # Confirm
        ]
        wizard, output = _make_wizard(responses)
        wizard.run()
        text = output.getvalue()
        assert "Manual Tracker" in text


# ── Full new draft flow test ─────────────────────────────────────────


class TestNewDraftFlow:
    def test_new_draft_with_defaults(self):
        """Walk through new draft setup with all defaults."""
        responses = [
            "1",   # New Draft
            "",    # Default draft mode (simulation)
            "",    # Default league size (12)
            "",    # Default scoring (half_ppr)
            "",    # Default roster (Y)
            "",    # Auto team names (Y)
            "",    # Default position (1)
            "",    # Default year (2025)
            "Y",   # Confirm
        ]
        wizard, _ = _make_wizard(responses)
        result = wizard.run()

        assert result["action"] == "new"
        assert result["draft_mode"] == "simulation"
        assert result["league_size"] == 12
        assert result["scoring_format"] == "half_ppr"
        assert result["human_team_id"] == 0
        assert len(result["team_names"]) == 12
        assert result["data_year"] == 2025

    def test_new_draft_manual_tracker_mode(self):
        """Selecting mode 2 sets draft_mode to manual_tracker."""
        responses = [
            "1",   # New Draft
            "2",   # Manual Tracker mode
            "",    # Default league size (12)
            "",    # Default scoring (half_ppr)
            "",    # Default roster (Y)
            "",    # Auto team names (Y)
            "",    # Default position (1)
            "",    # Default year (2025)
            "Y",   # Confirm
        ]
        wizard, _ = _make_wizard(responses)
        result = wizard.run()

        assert result["action"] == "new"
        assert result["draft_mode"] == "manual_tracker"

    def test_new_draft_cancel_goes_back(self):
        """Cancelling at confirmation returns to main menu."""
        responses = [
            "1",   # New Draft
            "",    # Default draft mode
            "",    # Default league size
            "",    # Default scoring
            "",    # Default roster
            "",    # Auto team names
            "",    # Default position
            "",    # Default year
            "n",   # Cancel
            "3",   # Quit
        ]
        wizard, _ = _make_wizard(responses)
        result = wizard.run()

        assert result == {"action": "quit"}
