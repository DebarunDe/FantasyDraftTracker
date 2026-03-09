"""Tests for Milestone 15: Polish & UX features.

Covers: DraftExporter CSV output, CLI board/compare/export commands.
"""

import csv
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from src.draft_manager.draft_state import DraftState, LeagueConfig, Pick
from src.ui.cli import DraftApp
from src.ui.export import DraftExporter, _reach_label

# ── Helpers ──────────────────────────────────────────────────────────


def _make_console():
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
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 1,
            "DST": 1,
            "K": 1,
            "BENCH": 6,
        },
    }
    defaults.update(overrides)
    return LeagueConfig(**defaults)


def _make_player_data():
    players = {}
    specs = [
        ("qb1", "Josh Allen", "QB", "BUF", 5, 300.0),
        ("rb1", "Saquon Barkley", "RB", "PHI", 2, 280.0),
        ("wr1", "Ja'Marr Chase", "WR", "CIN", 10, 260.0),
        ("te1", "Travis Kelce", "TE", "KC", 4, 200.0),
    ]
    for pid, name, pos, team, rank, pts in specs:
        players[pid] = {
            "player_id": pid,
            "name": name,
            "position": pos,
            "team": team,
            "overall_rank": rank,
            "bye_week": 7,
            "projections": {
                "standard": pts,
                "half_ppr": pts + 20,
                "full_ppr": pts + 40,
            },
            "baseline_vor": {"standard": 20.0, "half_ppr": 22.0, "full_ppr": 24.0},
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


# ── _reach_label (pure function) tests ───────────────────────────────


class TestReachLabelPure:
    """Tests for the plain-text reach_label helper in export.py."""

    def test_strong_steal(self):
        assert _reach_label(40) == "STEAL"

    def test_mild_steal(self):
        assert _reach_label(12) == "Value"

    def test_reach(self):
        assert _reach_label(-10) == "REACH"

    def test_within_threshold(self):
        assert _reach_label(3) == ""
        assert _reach_label(-3) == ""

    def test_exact_steal_threshold(self):
        # +8 should get "Value", not blank
        assert _reach_label(8) == "Value"

    def test_exact_strong_steal_threshold(self):
        assert _reach_label(15) == "STEAL"

    def test_exact_reach_threshold(self):
        assert _reach_label(-8) == "REACH"


# ── DraftExporter tests ───────────────────────────────────────────────


class TestDraftExporter:
    def test_creates_csv_file(self, tmp_path):
        state = _make_draft_state()
        pick = Pick.create(pick_number=1, round=1, team_id=0, player_id="qb1", slot="QB")
        state.all_picks.append(pick)
        state.teams[0].picks.append("qb1")

        exporter = DraftExporter()
        path = exporter.export_to_csv(state, "half_ppr", output_dir=str(tmp_path))

        assert path.exists()
        assert path.suffix == ".csv"

    def test_csv_has_header_row(self, tmp_path):
        state = _make_draft_state()
        exporter = DraftExporter()
        path = exporter.export_to_csv(state, "half_ppr", output_dir=str(tmp_path))

        with open(path) as f:
            reader = csv.DictReader(f)
            assert "pick_number" in reader.fieldnames
            assert "player_name" in reader.fieldnames
            assert "reach_delta" in reader.fieldnames
            assert "reach_label" in reader.fieldnames

    def test_csv_contains_pick_data(self, tmp_path):
        state = _make_draft_state()
        pick = Pick.create(pick_number=3, round=1, team_id=0, player_id="qb1", slot="QB")
        state.all_picks.append(pick)

        exporter = DraftExporter()
        path = exporter.export_to_csv(state, "half_ppr", output_dir=str(tmp_path))

        with open(path) as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 1
        row = rows[0]
        assert row["pick_number"] == "3"
        assert row["player_name"] == "Josh Allen"
        assert row["position"] == "QB"
        assert row["nfl_team"] == "BUF"
        assert row["slot"] == "QB"

    def test_csv_calculates_reach_delta(self, tmp_path):
        state = _make_draft_state()
        # qb1 has overall_rank=5; drafted at pick 50 → delta=+45 (STEAL)
        pick = Pick.create(pick_number=50, round=5, team_id=0, player_id="qb1", slot="QB")
        state.all_picks.append(pick)

        exporter = DraftExporter()
        path = exporter.export_to_csv(state, "half_ppr", output_dir=str(tmp_path))

        with open(path) as f:
            rows = list(csv.DictReader(f))

        row = rows[0]
        assert row["adp"] == "5"
        assert row["reach_delta"] == "45"
        assert row["reach_label"] == "STEAL"

    def test_csv_calculates_reach_label(self, tmp_path):
        state = _make_draft_state()
        # rb1 has overall_rank=2; drafted at pick 1 → delta=-1 (within threshold → "")
        pick = Pick.create(pick_number=1, round=1, team_id=0, player_id="rb1", slot="RB")
        state.all_picks.append(pick)

        exporter = DraftExporter()
        path = exporter.export_to_csv(state, "half_ppr", output_dir=str(tmp_path))

        with open(path) as f:
            rows = list(csv.DictReader(f))

        assert rows[0]["reach_label"] == ""

    def test_csv_pick_in_round_column(self, tmp_path):
        state = _make_draft_state()
        # Pick 5 in a 4-team league: round 2, pick_in_round = 1
        pick = Pick.create(pick_number=5, round=2, team_id=3, player_id="rb1", slot="RB")
        state.all_picks.append(pick)

        exporter = DraftExporter()
        path = exporter.export_to_csv(state, "half_ppr", output_dir=str(tmp_path))

        with open(path) as f:
            rows = list(csv.DictReader(f))

        assert rows[0]["pick_in_round"] == "1"

    def test_creates_output_directory(self, tmp_path):
        state = _make_draft_state()
        new_dir = tmp_path / "nested" / "exports"

        exporter = DraftExporter()
        path = exporter.export_to_csv(state, "half_ppr", output_dir=str(new_dir))

        assert new_dir.exists()
        assert path.exists()

    def test_filename_contains_draft_id_prefix(self, tmp_path):
        state = _make_draft_state()
        exporter = DraftExporter()
        path = exporter.export_to_csv(state, "half_ppr", output_dir=str(tmp_path))

        assert state.draft_id[:8] in path.name

    def test_empty_draft_produces_header_only(self, tmp_path):
        state = _make_draft_state()
        exporter = DraftExporter()
        path = exporter.export_to_csv(state, "half_ppr", output_dir=str(tmp_path))

        with open(path) as f:
            rows = list(csv.DictReader(f))

        assert rows == []


# ── CLI board/compare/export command tests ────────────────────────────


def _make_app_with_state():
    """Create a DraftApp with a fully initialised draft state (no I/O)."""
    console, output = _make_console()
    app = DraftApp(console=console)
    state = _make_draft_state()
    app.draft_state = state
    app._init_components()
    return app, output


class TestBoardCommand:
    def test_board_shows_no_picks_message(self):
        app, output = _make_app_with_state()
        app._show_full_board()
        text = output.getvalue()
        assert "No picks yet" in text

    def test_board_shows_picks_after_pick_made(self):
        app, output = _make_app_with_state()
        pick = Pick.create(pick_number=1, round=1, team_id=0, player_id="qb1", slot="QB")
        app.draft_state.all_picks.append(pick)

        app._show_full_board()
        text = output.getvalue()
        assert "Josh Allen" in text


class TestCompareCommand:
    def test_compare_shows_all_teams(self):
        app, output = _make_app_with_state()
        app._handle_compare()
        text = output.getvalue()
        assert "My Team" in text
        assert "CPU 1" in text

    def test_compare_shows_title(self):
        app, output = _make_app_with_state()
        app._handle_compare()
        text = output.getvalue()
        assert "Team Comparison" in text


class TestExportCommand:
    def test_export_shows_success_message(self, tmp_path):
        app, output = _make_app_with_state()
        exporter = DraftExporter()

        with patch.object(
            exporter, "export_to_csv", return_value=tmp_path / "test.csv"
        ) as mock_exp:
            (tmp_path / "test.csv").touch()
            # Patch DraftExporter constructor to return our mock
            with patch("src.ui.cli.DraftExporter", return_value=exporter):
                app._handle_export()

        text = output.getvalue()
        assert "exported" in text.lower() or "test.csv" in text

    def test_export_creates_file(self, tmp_path):
        app, output = _make_app_with_state()
        exporter = DraftExporter()
        path = exporter.export_to_csv(app.draft_state, "half_ppr", output_dir=str(tmp_path))
        assert path.exists()
