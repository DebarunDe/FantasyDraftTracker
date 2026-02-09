"""Tests for src.data_pipeline.run_update (full pipeline integration)."""

import json
from pathlib import Path

import pytest

from src.data_pipeline.run_update import run_pipeline

# Required keys in every player dict
_REQUIRED_PLAYER_KEYS = {
    "player_id", "name", "position", "team",
    "bye_week", "tier", "overall_rank", "position_rank",
    "stats", "projections", "baseline_vor",
}

_REQUIRED_STAT_KEYS = {
    "pass_att", "pass_cmp", "pass_yds", "pass_td", "pass_int",
    "rush_att", "rush_yds", "rush_td",
    "rec", "rec_yds", "rec_td", "fl",
    "fg", "fga", "xpt",
}

_SCORING_KEYS = {"standard", "half_ppr", "full_ppr"}


# ── Pipeline execution ────────────────────────────────────────────────


class TestRunPipeline:
    """End-to-end integration tests for the complete pipeline."""

    @pytest.fixture(scope="class")
    def pipeline_output(self, tmp_path_factory):
        """Run the pipeline once, writing output to a temp directory."""
        from src.data_pipeline.config import RAW_DATA_DIR

        tmp_dir = tmp_path_factory.mktemp("processed")
        data_dir = RAW_DATA_DIR / "2025"

        if not data_dir.is_dir():
            pytest.skip(f"Test CSV data not found at {data_dir}")

        output_path = run_pipeline(year=2025, data_dir=data_dir, output_dir=tmp_dir)

        with open(output_path) as f:
            data = json.load(f)

        return data, output_path, tmp_dir

    def test_pipeline_produces_file(self, pipeline_output):
        _, output_path, _ = pipeline_output
        assert output_path.exists()

    def test_latest_symlink_created(self, pipeline_output):
        _, _, tmp_dir = pipeline_output
        latest = tmp_dir / "players_latest.json"
        assert latest.is_symlink()

    def test_metadata_structure(self, pipeline_output):
        data, _, _ = pipeline_output
        meta = data["metadata"]

        assert meta["version"] == "1.0"
        assert meta["source"] == "FantasyPros"
        assert meta["season"] == 2025
        assert meta["league_size"] == 12
        assert meta["scoring_systems"] == ["standard", "half_ppr", "full_ppr"]
        assert meta["total_players"] > 200

    def test_total_player_count_matches(self, pipeline_output):
        data, _, _ = pipeline_output
        assert data["metadata"]["total_players"] == len(data["players"])

    def test_all_positions_present(self, pipeline_output):
        data, _, _ = pipeline_output
        positions = {p["position"] for p in data["players"]}
        assert positions == {"QB", "RB", "WR", "TE", "K", "DST"}

    def test_position_counts_reasonable(self, pipeline_output):
        data, _, _ = pipeline_output
        counts = {}
        for p in data["players"]:
            counts[p["position"]] = counts.get(p["position"], 0) + 1

        assert counts["QB"] >= 20
        assert counts["RB"] >= 50
        assert counts["WR"] >= 50
        assert counts["TE"] >= 20
        assert counts["K"] >= 10
        assert counts["DST"] >= 10

    def test_vor_values_present(self, pipeline_output):
        data, _, _ = pipeline_output
        for p in data["players"][:10]:
            vor = p["baseline_vor"]
            assert "standard" in vor
            assert "half_ppr" in vor
            assert "full_ppr" in vor
            assert isinstance(vor["half_ppr"], (int, float))

    def test_top_vor_players_sensible(self, pipeline_output):
        data, _, _ = pipeline_output
        sorted_by_vor = sorted(
            data["players"],
            key=lambda p: p["baseline_vor"]["half_ppr"],
            reverse=True,
        )
        top5 = sorted_by_vor[:5]

        # Top 5 should all have significant VOR
        for p in top5:
            assert p["baseline_vor"]["half_ppr"] > 10, (
                f"Top player {p['name']} has low VOR"
            )

        # Top 5 should include skill positions (QB/RB/WR/TE)
        top_positions = {p["position"] for p in top5}
        assert top_positions & {"QB", "RB", "WR", "TE"}, (
            "Top VOR players should include skill positions"
        )

    def test_missing_data_dir_raises(self):
        with pytest.raises(FileNotFoundError):
            run_pipeline(year=9999, data_dir=Path("/nonexistent"))


# ── Output format validation ──────────────────────────────────────────


class TestOutputFormat:
    """Validate the JSON structure of individual player dicts."""

    @pytest.fixture(scope="class")
    def players(self, tmp_path_factory):
        """Run pipeline and return the players list."""
        from src.data_pipeline.config import RAW_DATA_DIR

        tmp_dir = tmp_path_factory.mktemp("format_test")
        data_dir = RAW_DATA_DIR / "2025"

        if not data_dir.is_dir():
            pytest.skip(f"Test CSV data not found at {data_dir}")

        output_path = run_pipeline(year=2025, data_dir=data_dir, output_dir=tmp_dir)

        with open(output_path) as f:
            return json.load(f)["players"]

    def test_player_has_all_required_keys(self, players):
        for p in players[:20]:
            missing = _REQUIRED_PLAYER_KEYS - p.keys()
            assert not missing, f"{p.get('name', '?')} missing keys: {missing}"

    def test_stats_dict_has_expected_keys(self, players):
        for p in players[:20]:
            missing = _REQUIRED_STAT_KEYS - p["stats"].keys()
            assert not missing, f"{p['name']} stats missing: {missing}"

    def test_projections_has_three_formats(self, players):
        for p in players[:20]:
            assert set(p["projections"].keys()) == _SCORING_KEYS

    def test_baseline_vor_has_three_formats(self, players):
        for p in players[:20]:
            assert set(p["baseline_vor"].keys()) == _SCORING_KEYS

    def test_stat_values_are_numeric(self, players):
        for p in players[:20]:
            for key, val in p["stats"].items():
                assert isinstance(val, (int, float)), (
                    f"{p['name']} stat {key} is {type(val)}"
                )

    def test_player_ids_are_unique(self, players):
        ids = [p["player_id"] for p in players]
        assert len(ids) == len(set(ids)), "Player IDs should be unique"

    def test_projections_ordering(self, players):
        """For receivers, Full PPR >= Half PPR >= Standard."""
        for p in players:
            if p["position"] in ("WR", "RB", "TE") and p["stats"]["rec"] > 0:
                proj = p["projections"]
                assert proj["full_ppr"] >= proj["half_ppr"] - 0.01
                assert proj["half_ppr"] >= proj["standard"] - 0.01
