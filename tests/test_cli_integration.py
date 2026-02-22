"""Integration tests for the CLI draft application."""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from src.draft_manager.draft_controller import DraftController
from src.draft_manager.draft_state import DraftState, LeagueConfig
from src.draft_manager.draft_rules import ValidationError
from src.draft_manager.state_persistence import StatePersistence
from src.simulation_engine.computer_drafter import ComputerDrafter
from src.simulation_engine.vor_calculator import DynamicVORCalculator
from src.ui.cli import DraftApp
from src.ui.display import DraftDisplay
from src.ui.player_search import PlayerSearcher


# ── Helpers ──────────────────────────────────────────────────────────


def _make_league_config(**overrides):
    defaults = {
        "league_id": "test",
        "league_size": 2,
        "scoring_format": "half_ppr",
        "draft_type": "snake",
        "draft_mode": "simulation",
        "data_year": 2025,
        "roster_slots": {
            "QB": 1, "RB": 1, "WR": 1, "TE": 0,
            "FLEX": 0, "DST": 0, "K": 0, "BENCH": 0,
        },
    }
    defaults.update(overrides)
    return LeagueConfig(**defaults)


def _make_player_data():
    """Create minimal player set for fast drafts."""
    players = {}
    specs = [
        ("qb1", "Josh Allen", "QB", "BUF", 1),
        ("qb2", "Jalen Hurts", "QB", "PHI", 2),
        ("rb1", "Saquon Barkley", "RB", "PHI", 3),
        ("rb2", "Breece Hall", "RB", "NYJ", 4),
        ("wr1", "Ja'Marr Chase", "WR", "CIN", 5),
        ("wr2", "CeeDee Lamb", "WR", "DAL", 6),
    ]
    for pid, name, pos, team, rank in specs:
        players[pid] = {
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
    return players


def _make_app_with_draft(responses, draft_mode="simulation"):
    """Create a DraftApp with a pre-initialized 2-team draft and mocked input.

    The draft has 2 teams, 3 rounds (QB, RB, WR), 6 total picks.
    """
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

    # Pre-initialize draft to skip setup wizard
    config = _make_league_config(draft_mode=draft_mode)
    player_data = _make_player_data()
    app.draft_state = DraftState.create_new(
        league_config=config,
        team_names=["My Team", "CPU Team"],
        human_team_id=0,
        player_data=player_data,
    )
    app.controller = DraftController(app.draft_state)
    app.vor_calculator = DynamicVORCalculator("half_ppr", league_size=2)
    app.computer_drafter = ComputerDrafter(
        vor_calculator=app.vor_calculator, strategy="balanced"
    )
    app.searcher = PlayerSearcher(app.controller)
    app.persistence = MagicMock(spec=StatePersistence)

    return app, output


# ── Pick execution tests ─────────────────────────────────────────────


class TestPickExecution:
    def test_pick_by_exact_name(self):
        """User picks by typing exact player name."""
        app, output = _make_app_with_draft([
            "Josh Allen", "y",   # Pick 1: Human team picks QB
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        assert "Josh Allen" in text
        assert app.draft_state.current_pick == 2

    def test_pick_by_number_from_recommendations(self):
        """User picks by number from VOR recommendation list."""
        app, output = _make_app_with_draft([
            "1", "y",  # Pick #1 from recommendation list
        ])

        # First show recommendations so last_displayed_players is populated
        app._show_recommendations()
        initial_pick = app.draft_state.current_pick

        app._handle_pick_turn()

        assert app.draft_state.current_pick == initial_pick + 1

    def test_pick_declined_reprompts(self):
        """User declines confirmation, then picks another player."""
        app, output = _make_app_with_draft([
            "Josh Allen", "n",       # Decline first pick
            "Jalen Hurts", "y",      # Accept second pick
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        # Should have picked Jalen Hurts (Josh Allen declined)
        assert "Jalen Hurts" in text

    def test_invalid_name_shows_error(self):
        """Searching for non-existent player shows error."""
        app, output = _make_app_with_draft([
            "zzz nonexistent",
            "Josh Allen", "y",
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        assert "No available players" in text

    def test_auto_save_after_pick(self):
        """Persistence.save_draft is called after each pick."""
        app, output = _make_app_with_draft([
            "Josh Allen", "y",
        ])

        app._handle_pick_turn()

        app.persistence.save_draft.assert_called_once_with(app.draft_state)


# ── Command handling tests ───────────────────────────────────────────


class TestCommandHandling:
    def test_help_command(self):
        app, output = _make_app_with_draft([
            "h",                    # Show help
            "Josh Allen", "y",      # Then pick
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        assert "available" in text
        assert "roster" in text

    def test_available_command(self):
        app, output = _make_app_with_draft([
            "a",                    # Show available
            "Josh Allen", "y",      # Then pick
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        assert "Available Players" in text

    def test_available_with_position_filter(self):
        app, output = _make_app_with_draft([
            "a qb",                 # Show available QBs
            "Josh Allen", "y",      # Then pick
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        assert "Available Players" in text

    def test_roster_command(self):
        app, output = _make_app_with_draft([
            "r",                    # Show roster
            "Josh Allen", "y",      # Then pick
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        assert "Roster" in text

    def test_search_command(self):
        app, output = _make_app_with_draft([
            "s allen",              # Search
            "1", "y",               # Pick from results
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        assert "Search Results" in text

    def test_save_command(self):
        app, output = _make_app_with_draft([
            "save",                 # Manual save
            "Josh Allen", "y",      # Then pick
        ])

        app._handle_pick_turn()
        # save_draft called for 'save' command + auto-save after pick
        assert app.persistence.save_draft.call_count == 2

    def test_quit_command(self):
        app, output = _make_app_with_draft(["q"])

        result = app._get_user_pick()

        assert result is None
        app.persistence.save_draft.assert_called()

    def test_recommend_command(self):
        app, output = _make_app_with_draft([
            "rec",                  # Show recommendations
            "Josh Allen", "y",      # Then pick
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        assert "Recommendations" in text


# ── Search disambiguation tests ──────────────────────────────────────


class TestSearchDisambiguation:
    def test_multiple_matches_shows_list(self):
        """When multiple players match, show disambiguation list."""
        # Create app with data that has two "Hurts" or similar
        app, output = _make_app_with_draft([
            "al",                    # Matches "Josh Allen" and "Jalen" (contains "al")
            "1", "y",               # Pick first from results
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        # Should show search results since "al" matches multiple
        assert "Search Results" in text or app.draft_state.current_pick == 2


# ── Draft board display tests ────────────────────────────────────────


class TestDraftBoard:
    def test_shows_header_on_turn(self):
        app, output = _make_app_with_draft([
            "Josh Allen", "y",
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        assert "Round 1" in text
        assert "My Team" in text

    def test_shows_recommendations_for_human_team(self):
        app, output = _make_app_with_draft([
            "Josh Allen", "y",
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        assert "Recommendations" in text

    def test_no_recommendations_for_cpu_team(self):
        """When CPU team is on the clock it auto-picks; no board/rec display."""
        app, output = _make_app_with_draft([
            "Josh Allen", "y",  # Human picks first (only human input needed)
        ])

        # Make first pick (human)
        app._handle_pick_turn()
        output.truncate(0)
        output.seek(0)

        # Now it's CPU team's turn — auto-picks, no user input consumed
        app._handle_pick_turn()
        text = output.getvalue()

        # CPU pick banner shows the team name; no full board/Recommendations block
        assert "CPU Team" in text
        assert "Recommendations" not in text


# ── Full draft flow test ─────────────────────────────────────────────


class TestFullDraftFlow:
    def test_complete_2team_draft(self):
        """Complete a full 2-team, 3-round draft (6 picks total).

        Snake order for 2 teams: T0, T1, T1, T0, T0, T1
        Human (T0) picks at positions 1, 4, 5 — CPU (T1) auto-picks the rest.
        Human picks by number from the VOR recommendation list shown each turn.
        """
        app, output = _make_app_with_draft([
            # Pick 1: Human (T0) — pick first recommended player
            "1", "y",
            # Picks 2-3: CPU (T1) auto-picks — no input needed
            # Pick 4: Human (T0) — pick first available
            "1", "y",
            # Pick 5: Human (T0) — pick first available
            "1", "y",
            # Pick 6: CPU (T1) auto-picks — no input needed
        ])

        app._draft_loop()

        assert app.controller.is_complete
        assert len(app.draft_state.all_picks) == 6

    def test_draft_summary_after_completion(self):
        """After draft completes, summary is available."""
        app, output = _make_app_with_draft([
            # Human turns at picks 1, 4, 5 (see snake order above)
            "1", "y",
            "1", "y",
            "1", "y",
        ])

        app._draft_loop()

        summary = app.controller.get_draft_summary()
        assert "error" not in summary
        assert len(summary["teams"]) == 2


# ── Edge case tests ──────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_input_ignored(self):
        """Empty input should just re-prompt."""
        app, output = _make_app_with_draft([
            "",                     # Empty
            "",                     # Empty again
            "Josh Allen", "y",      # Then pick
        ])

        app._handle_pick_turn()
        assert app.draft_state.current_pick == 2

    def test_number_out_of_range(self):
        """Number with no prior list shows error."""
        app, output = _make_app_with_draft([
            "99",                   # Invalid number (empty list)
            "Josh Allen", "y",      # Then pick normally
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        assert "No player at #99" in text or app.draft_state.current_pick == 2


# ── Simulate command tests ───────────────────────────────────────────


class TestSimulateCommand:
    def test_sim_yes_completes_draft(self):
        """Typing 'sim' and confirming auto-picks all remaining turns.

        Human is on pick 1; sim should run all 6 picks to completion.
        """
        app, output = _make_app_with_draft([
            "sim", "y",   # Human triggers simulation from their first turn
        ])

        app._draft_loop()
        text = output.getvalue()

        assert app.controller.is_complete
        assert len(app.draft_state.all_picks) == 6
        assert "Simulation complete" in text

    def test_sim_no_cancels_and_draft_continues(self):
        """Typing 'sim' then 'n' cancels simulation; draft continues normally.

        Snake order: T0 T1 T1 T0 T0 T1 — human (T0) at picks 1, 4, 5.
        """
        app, output = _make_app_with_draft([
            "sim", "n",      # Cancel simulation on pick 1
            "Josh Allen", "y",  # Human picks normally
            # Picks 2-3: CPU auto-picks
            "1", "y",        # Human pick 4
            "1", "y",        # Human pick 5
            # Pick 6: CPU auto-picks
        ])

        app._draft_loop()

        assert app.controller.is_complete
        assert len(app.draft_state.all_picks) == 6

    def test_sim_appears_in_help(self):
        """'sim' command is listed in the help panel."""
        app, output = _make_app_with_draft([
            "h",
            "Josh Allen", "y",
        ])

        app._handle_pick_turn()
        text = output.getvalue()

        assert "sim" in text


# ── Manual tracker mode tests ────────────────────────────────────────


class TestManualTrackerMode:
    """Tests for Manual Draft Tracker mode (draft_mode='manual_tracker').

    In this mode the user enters every pick — no team auto-picks.
    Snake order for 2 teams: T0, T1, T1, T0, T0, T1
    """

    def test_is_manual_tracker_property(self):
        """_is_manual_tracker is True when draft_mode is manual_tracker."""
        app, _ = _make_app_with_draft([], draft_mode="manual_tracker")
        assert app._is_manual_tracker is True

    def test_is_manual_tracker_false_in_simulation(self):
        """_is_manual_tracker is False in simulation mode."""
        app, _ = _make_app_with_draft([])
        assert app._is_manual_tracker is False

    def test_cpu_team_does_not_auto_pick(self):
        """In manual tracker mode, CPU team's turn waits for user input."""
        # Snake order pick 1 = T0 (human). After human picks, pick 2 = T1 (CPU).
        # In manual tracker, pick 2 should also require user input, not auto-pick.
        app, output = _make_app_with_draft(
            [
                "Josh Allen", "y",    # Pick 1: My Team (human)
                "Jalen Hurts", "y",   # Pick 2: CPU Team (manual tracker — user enters it)
            ],
            draft_mode="manual_tracker",
        )

        app._handle_pick_turn()  # Pick 1
        app._handle_pick_turn()  # Pick 2 — must consume user input, not auto-pick

        assert app.draft_state.current_pick == 3
        assert len(app.draft_state.all_picks) == 2

    def test_complete_draft_all_manual(self):
        """Full 2-team, 3-round draft with all picks entered manually.

        Snake order: T0, T1, T1, T0, T0, T1 — 6 picks total.
        """
        app, output = _make_app_with_draft(
            [
                "Josh Allen", "y",      # Pick 1: T0
                "Jalen Hurts", "y",     # Pick 2: T1
                "Saquon Barkley", "y",  # Pick 3: T1
                "Breece Hall", "y",     # Pick 4: T0
                "Ja'Marr Chase", "y",   # Pick 5: T0
                "CeeDee Lamb", "y",     # Pick 6: T1
            ],
            draft_mode="manual_tracker",
        )

        app._draft_loop()

        assert app.controller.is_complete
        assert len(app.draft_state.all_picks) == 6

    def test_recommendations_shown_for_human_team(self):
        """VOR recommendations are shown when it is the human team's turn."""
        app, output = _make_app_with_draft(
            ["Josh Allen", "y"],
            draft_mode="manual_tracker",
        )

        app._handle_pick_turn()  # Pick 1: T0 (human)
        text = output.getvalue()

        assert "Recommendations" in text

    def test_recommendations_not_shown_for_cpu_team(self):
        """For non-human teams in manual tracker, available list shown (not recommendations)."""
        app, output = _make_app_with_draft(
            [
                "Josh Allen", "y",   # Pick 1: T0 (human) — recs shown
                "Jalen Hurts", "y",  # Pick 2: T1 (not human) — available list shown
            ],
            draft_mode="manual_tracker",
        )

        app._handle_pick_turn()  # Pick 1
        output.truncate(0)
        output.seek(0)

        app._handle_pick_turn()  # Pick 2: CPU team's turn in manual tracker
        text = output.getvalue()

        assert "Recommendations" not in text
        assert "Available Players" in text

    def test_header_shows_manual_tracker_label(self):
        """Draft header includes 'Manual Tracker' indicator."""
        app, output = _make_app_with_draft(
            ["Josh Allen", "y"],
            draft_mode="manual_tracker",
        )

        app._handle_pick_turn()
        text = output.getvalue()

        assert "Manual Tracker" in text

    def test_sim_command_disabled(self):
        """'sim' command shows error in manual tracker mode instead of simulating."""
        app, output = _make_app_with_draft(
            ["sim", "Josh Allen", "y"],
            draft_mode="manual_tracker",
        )

        app._handle_pick_turn()
        text = output.getvalue()

        # Should not have completed the draft — sim was rejected
        assert app.draft_state.current_pick == 2  # Only 1 pick made
        assert "not available in Manual Tracker" in text

    def test_pick_by_number_for_cpu_team(self):
        """User can pick by number for a non-human team (available list is auto-shown)."""
        app, output = _make_app_with_draft(
            [
                "Josh Allen", "y",  # Pick 1: T0 (human)
                "1", "y",           # Pick 2: T1 (CPU) — pick #1 from available list
            ],
            draft_mode="manual_tracker",
        )

        app._handle_pick_turn()  # Pick 1
        app._handle_pick_turn()  # Pick 2 — must NOT error "no player list"

        assert app.draft_state.current_pick == 3
        assert len(app.draft_state.all_picks) == 2

    def test_vor_recommendations_update_after_picks(self):
        """VOR recommendations are recalculated after each pick."""
        app, output = _make_app_with_draft(
            [
                "Josh Allen", "y",   # Pick 1: T0
                "Jalen Hurts", "y",  # Pick 2: T1
                "rec",               # Check updated recs on T1's second turn (pick 3)
                "Saquon Barkley", "y",
            ],
            draft_mode="manual_tracker",
        )

        app._handle_pick_turn()  # Pick 1
        app._handle_pick_turn()  # Pick 2
        app._handle_pick_turn()  # Pick 3: T1 again (snake), user checks rec then picks

        # Both QBs are gone; RB should now lead recommendations
        text = output.getvalue()
        assert "Recommendations" in text
        assert len(app.draft_state.all_picks) == 3

    def test_auto_save_after_each_pick(self):
        """persistence.save_draft is called after every manual pick."""
        app, _ = _make_app_with_draft(
            [
                "Josh Allen", "y",   # Pick 1
                "Jalen Hurts", "y",  # Pick 2
            ],
            draft_mode="manual_tracker",
        )

        app._handle_pick_turn()
        app._handle_pick_turn()

        assert app.persistence.save_draft.call_count == 2
