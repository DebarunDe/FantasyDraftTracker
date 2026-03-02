"""Tests for CLI display components."""

from io import StringIO

import pytest
from rich.console import Console

from src.draft_manager.draft_state import DraftState, LeagueConfig, Pick
from src.ui.display import DraftDisplay


# ── Helpers ──────────────────────────────────────────────────────────


def _make_console():
    """Create a console that captures output to a StringIO buffer."""
    output = StringIO()
    console = Console(file=output, width=120, force_terminal=True)
    return console, output


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
    players = {}
    specs = [
        ("qb1", "Josh Allen", "QB", "BUF", 1),
        ("rb1", "Saquon Barkley", "RB", "PHI", 2),
        ("wr1", "Ja'Marr Chase", "WR", "CIN", 3),
        ("te1", "Travis Kelce", "TE", "KC", 4),
        ("k1", "Tyler Bass", "K", "BUF", 5),
        ("dst1", "Eagles", "DST", "PHI", 6),
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
                "standard": 100.0 + rank,
                "half_ppr": 110.0 + rank,
                "full_ppr": 120.0 + rank,
            },
            "baseline_vor": {
                "standard": 20.0,
                "half_ppr": 22.0,
                "full_ppr": 24.0,
            },
        }
    return players


def _make_draft_state():
    config = _make_league_config()
    player_data = _make_player_data()
    team_names = ["My Team", "CPU 1", "CPU 2", "CPU 3"]
    return DraftState.create_new(
        league_config=config,
        team_names=team_names,
        human_team_id=0,
        player_data=player_data,
    )


# ── show_draft_header tests ──────────────────────────────────────────


class TestShowDraftHeader:
    def test_displays_round_and_pick(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()

        display.show_draft_header(state)
        text = output.getvalue()

        assert "Round 1" in text
        assert "Overall: 1" in text

    def test_displays_team_name(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()

        display.show_draft_header(state)
        text = output.getvalue()

        assert "My Team" in text

    def test_displays_human_indicator(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()

        display.show_draft_header(state)
        text = output.getvalue()

        assert "YOU" in text

    def test_displays_scoring_format(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()

        display.show_draft_header(state)
        text = output.getvalue()

        assert "Half PPR" in text

    def test_displays_league_size(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()

        display.show_draft_header(state)
        text = output.getvalue()

        assert "4 Teams" in text


# ── show_pick_banner tests ───────────────────────────────────────────


class TestShowPickBanner:
    def test_displays_player_name(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        pick = Pick.create(pick_number=1, round=1, team_id=0, player_id="qb1", slot="QB")
        player_info = {"name": "Josh Allen", "position": "QB", "team": "BUF"}

        display.show_pick_banner(pick, player_info, "My Team")
        text = output.getvalue()

        assert "Josh Allen" in text
        assert "QB" in text
        assert "BUF" in text

    def test_displays_pick_number(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        pick = Pick.create(pick_number=5, round=2, team_id=1, player_id="rb1", slot="RB")
        player_info = {"name": "Saquon Barkley", "position": "RB", "team": "PHI"}

        display.show_pick_banner(pick, player_info, "CPU 1")
        text = output.getvalue()

        assert "#5" in text
        assert "Round 2" in text
        assert "CPU 1" in text


# ── show_recent_picks tests ──────────────────────────────────────────


class TestShowRecentPicks:
    def test_no_picks_message(self):
        console, output = _make_console()
        display = DraftDisplay(console)

        display.show_recent_picks([], {}, [])
        text = output.getvalue()

        assert "No picks yet" in text

    def test_displays_pick_info(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()
        pick = Pick.create(pick_number=1, round=1, team_id=0, player_id="qb1", slot="QB")

        display.show_recent_picks(
            [pick], state.player_data, state.teams
        )
        text = output.getvalue()

        assert "Josh Allen" in text
        assert "My Team" in text

    def test_respects_limit(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()
        picks = [
            Pick.create(pick_number=i, round=1, team_id=0, player_id="qb1", slot="QB")
            for i in range(1, 20)
        ]

        display.show_recent_picks(picks, state.player_data, state.teams, limit=5)
        text = output.getvalue()

        # Should show "Recent Picks" header regardless
        assert "Recent Picks" in text


# ── show_available_players tests ─────────────────────────────────────


class TestShowAvailablePlayers:
    def test_returns_displayed_list(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        players = list(_make_player_data().values())

        result = display.show_available_players(players, "half_ppr", limit=3)

        assert len(result) == 3

    def test_respects_limit(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        players = list(_make_player_data().values())

        result = display.show_available_players(players, "half_ppr", limit=2)

        assert len(result) == 2

    def test_displays_column_headers(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        players = list(_make_player_data().values())

        display.show_available_players(players, "half_ppr")
        text = output.getvalue()

        assert "Name" in text
        assert "Pos" in text
        assert "Team" in text

    def test_displays_player_names(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        players = list(_make_player_data().values())

        display.show_available_players(players, "half_ppr")
        text = output.getvalue()

        assert "Josh Allen" in text
        assert "Saquon Barkley" in text

    def test_shows_count_info(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        players = list(_make_player_data().values())

        display.show_available_players(players, "half_ppr", limit=3)
        text = output.getvalue()

        assert "3" in text
        assert str(len(players)) in text


# ── show_team_roster tests ───────────────────────────────────────────


class TestShowTeamRoster:
    def test_shows_empty_slots(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        roster_slots = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "DST": 1, "K": 1, "BENCH": 6}
        roster = {slot: [] for slot in roster_slots}

        display.show_team_roster("My Team", roster, "half_ppr", roster_slots)
        text = output.getvalue()

        assert "empty" in text
        assert "My Team" in text

    def test_shows_filled_slots(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        player_data = _make_player_data()
        roster_slots = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "DST": 1, "K": 1, "BENCH": 6}
        roster = {slot: [] for slot in roster_slots}
        roster["QB"] = [player_data["qb1"]]

        display.show_team_roster("My Team", roster, "half_ppr", roster_slots)
        text = output.getvalue()

        assert "Josh Allen" in text


# ── show_search_results tests ────────────────────────────────────────


class TestShowSearchResults:
    def test_no_results_message(self):
        console, output = _make_console()
        display = DraftDisplay(console)

        display.show_search_results([], "half_ppr")
        text = output.getvalue()

        assert "No players found" in text

    def test_displays_results(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        results = [_make_player_data()["qb1"]]

        display.show_search_results(results, "half_ppr")
        text = output.getvalue()

        assert "Josh Allen" in text
        assert "Search Results" in text


# ── show_help tests ──────────────────────────────────────────────────


class TestShowHelp:
    def test_lists_commands(self):
        console, output = _make_console()
        display = DraftDisplay(console)

        display.show_help()
        text = output.getvalue()

        assert "available" in text
        assert "roster" in text
        assert "Search" in text
        assert "help" in text
        assert "quit" in text


# ── show_error / show_success tests ──────────────────────────────────


class TestShowErrorSuccess:
    def test_show_error(self):
        console, output = _make_console()
        display = DraftDisplay(console)

        display.show_error("Something went wrong")
        text = output.getvalue()

        assert "Something went wrong" in text
        assert "Error" in text

    def test_show_success(self):
        console, output = _make_console()
        display = DraftDisplay(console)

        display.show_success("All good!")
        text = output.getvalue()

        assert "All good!" in text


# ── show_draft_summary tests ────────────────────────────────────────


class TestShowDraftSummary:
    def test_displays_complete_message(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        summary = {
            "teams": [
                {"team_name": "Team 1", "is_human": True, "projected_points": 1500.0},
                {"team_name": "Team 2", "is_human": False, "projected_points": 1400.0},
            ]
        }

        display.show_draft_summary(summary, "half_ppr")
        text = output.getvalue()

        assert "DRAFT COMPLETE" in text

    def test_sorted_by_points(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        summary = {
            "teams": [
                {"team_name": "Low Team", "is_human": False, "projected_points": 1000.0},
                {"team_name": "High Team", "is_human": True, "projected_points": 2000.0},
            ]
        }

        display.show_draft_summary(summary, "half_ppr")
        text = output.getvalue()

        high_pos = text.index("High Team")
        low_pos = text.index("Low Team")
        assert high_pos < low_pos  # Higher points should appear first

    def test_marks_human_team(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        summary = {
            "teams": [
                {"team_name": "My Team", "is_human": True, "projected_points": 1500.0},
                {"team_name": "CPU", "is_human": False, "projected_points": 1400.0},
            ]
        }

        display.show_draft_summary(summary, "half_ppr")
        text = output.getvalue()

        assert "Your Team" in text


# ── show_vor_recommendations tests ───────────────────────────────────


class TestShowVorRecommendations:
    def test_returns_displayed_list(self):
        from src.simulation_engine.models import VORResult

        console, output = _make_console()
        display = DraftDisplay(console)
        player_data = _make_player_data()

        vor_results = {
            "qb1": VORResult(
                player_id="qb1", base_vor=20.0, dynamic_vor=30.0,
                scarcity_multiplier=1.2, need_multiplier=1.25,
                position="QB", position_rank=1,
            ),
            "rb1": VORResult(
                player_id="rb1", base_vor=22.0, dynamic_vor=35.0,
                scarcity_multiplier=1.5, need_multiplier=1.1,
                position="RB", position_rank=1,
            ),
        }

        result = display.show_vor_recommendations(
            vor_results, player_data, "half_ppr", limit=5
        )

        assert len(result) == 2
        # Sorted by dynamic VOR: rb1 (35.0) > qb1 (30.0)
        assert result[0]["player_id"] == "rb1"
        assert result[1]["player_id"] == "qb1"

    def test_displays_recommendations_header(self):
        from src.simulation_engine.models import VORResult

        console, output = _make_console()
        display = DraftDisplay(console)
        player_data = _make_player_data()

        vor_results = {
            "qb1": VORResult(
                player_id="qb1", base_vor=20.0, dynamic_vor=30.0,
                scarcity_multiplier=1.0, need_multiplier=1.0,
                position="QB", position_rank=1,
            ),
        }

        display.show_vor_recommendations(vor_results, player_data, "half_ppr")
        text = output.getvalue()

        assert "Recommendations" in text
        assert "Josh Allen" in text


# ── _reach_label tests ───────────────────────────────────────────────


class TestReachLabel:
    def test_strong_steal(self):
        label = DraftDisplay._reach_label(50, 20)  # +30 picks past ADP
        assert "STEAL" in label
        assert "30" in label

    def test_mild_steal(self):
        label = DraftDisplay._reach_label(30, 20)  # +10 picks past ADP
        assert "Value" in label
        assert "10" in label

    def test_reach(self):
        label = DraftDisplay._reach_label(10, 25)  # -15 picks before ADP
        assert "REACH" in label
        assert "15" in label

    def test_within_threshold_returns_empty(self):
        label = DraftDisplay._reach_label(10, 13)  # -3 picks (within ±7)
        assert label == ""

    def test_no_adp_returns_empty(self):
        label = DraftDisplay._reach_label(10, 0)
        assert label == ""


# ── show_pick_banner with reach/steal tests ──────────────────────────


class TestShowPickBannerReachSteal:
    def test_shows_adp_when_present(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        pick = Pick.create(pick_number=1, round=1, team_id=0, player_id="qb1", slot="QB")
        player_info = {
            "name": "Josh Allen", "position": "QB", "team": "BUF", "overall_rank": 5
        }
        display.show_pick_banner(pick, player_info, "My Team")
        text = output.getvalue()
        assert "ADP #5" in text

    def test_shows_steal_label(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        pick = Pick.create(pick_number=50, round=5, team_id=0, player_id="qb1", slot="QB")
        player_info = {
            "name": "Josh Allen", "position": "QB", "team": "BUF", "overall_rank": 10
        }
        display.show_pick_banner(pick, player_info, "My Team")
        text = output.getvalue()
        assert "STEAL" in text

    def test_shows_reach_label(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        pick = Pick.create(pick_number=5, round=1, team_id=0, player_id="qb1", slot="QB")
        player_info = {
            "name": "Josh Allen", "position": "QB", "team": "BUF", "overall_rank": 30
        }
        display.show_pick_banner(pick, player_info, "My Team")
        text = output.getvalue()
        assert "REACH" in text

    def test_no_adp_omits_label(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        pick = Pick.create(pick_number=1, round=1, team_id=0, player_id="qb1", slot="QB")
        player_info = {"name": "Josh Allen", "position": "QB", "team": "BUF"}
        display.show_pick_banner(pick, player_info, "My Team")
        text = output.getvalue()
        assert "ADP" not in text
        assert "STEAL" not in text
        assert "REACH" not in text


# ── show_full_draft_board tests ──────────────────────────────────────


class TestShowFullDraftBoard:
    def test_no_picks_shows_message(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        display.show_full_draft_board([], {}, [])
        assert "No picks yet" in output.getvalue()

    def test_shows_all_picks(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()
        picks = [
            Pick.create(pick_number=1, round=1, team_id=0, player_id="qb1", slot="QB"),
            Pick.create(pick_number=2, round=1, team_id=1, player_id="rb1", slot="RB"),
        ]
        display.show_full_draft_board(picks, state.player_data, state.teams)
        text = output.getvalue()
        assert "Josh Allen" in text
        assert "Saquon Barkley" in text

    def test_shows_reach_column(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()
        picks = [
            Pick.create(pick_number=1, round=1, team_id=0, player_id="qb1", slot="QB"),
        ]
        display.show_full_draft_board(picks, state.player_data, state.teams)
        text = output.getvalue()
        assert "ADP" in text or "Δ" in text

    def test_shows_pick_count_in_title(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()
        picks = [
            Pick.create(pick_number=1, round=1, team_id=0, player_id="qb1", slot="QB"),
        ]
        display.show_full_draft_board(picks, state.player_data, state.teams)
        text = output.getvalue()
        assert "1 pick" in text


# ── show_team_comparison tests ───────────────────────────────────────


class TestShowTeamComparison:
    def _make_roster_slots(self):
        return {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "DST": 1, "K": 1, "BENCH": 6}

    def test_shows_all_teams(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()
        display.show_team_comparison(
            state.teams,
            state.player_data,
            "half_ppr",
            self._make_roster_slots(),
            [],
        )
        text = output.getvalue()
        assert "My Team" in text
        assert "CPU 1" in text
        assert "CPU 2" in text

    def test_shows_comparison_title(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()
        display.show_team_comparison(
            state.teams,
            state.player_data,
            "half_ppr",
            self._make_roster_slots(),
            [],
        )
        text = output.getvalue()
        assert "Team Comparison" in text

    def test_shows_steal_for_large_delta(self):
        console, output = _make_console()
        display = DraftDisplay(console)
        state = _make_draft_state()
        # Pick #50 for a player with ADP=10 → +40 = strong steal
        state.player_data["qb1"]["overall_rank"] = 10
        state.teams[0].picks = ["qb1"]
        state.teams[0].roster["QB"] = ["qb1"]
        pick = Pick.create(pick_number=50, round=5, team_id=0, player_id="qb1", slot="QB")
        display.show_team_comparison(
            state.teams,
            state.player_data,
            "half_ppr",
            self._make_roster_slots(),
            [pick],
        )
        text = output.getvalue()
        assert "Josh Allen" in text
        assert "+40" in text
