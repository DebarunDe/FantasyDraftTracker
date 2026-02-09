"""Tests for src.data_pipeline.vor_calculation."""

import pandas as pd
import pytest

from src.data_pipeline.config import VOR_BASELINE_COUNTS


# ── Synthetic data helpers ────────────────────────────────────────────


def _make_players(position: str, count: int, base_fpts: float = 200.0):
    """Return a minimal DataFrame for *count* players at *position*.

    FPTS decrease linearly: player 0 gets *base_fpts*, player N gets
    base_fpts - N * 5.  Rec is 0 for non-receivers so scoring variants
    are identical (except for WR/RB/TE).
    """
    rows = []
    for i in range(count):
        rec = (60 - i) if position in ("WR", "RB", "TE") else 0
        fpts = base_fpts - i * 5  # Full PPR
        rows.append({
            "Player": f"{position}_Player_{i}",
            "Player_Norm": f"{position.lower()}_player_{i}",
            "Team_Abbr": "TST",
            "Position": position,
            "FPTS": fpts,
            "Rec": rec,
            "FPTS_FullPPR": fpts,
            "FPTS_HalfPPR": fpts - rec * 0.5,
            "FPTS_Standard": fpts - rec,
        })
    return pd.DataFrame(rows)


def _make_multi_position_df():
    """Build a DataFrame with players at all six positions."""
    frames = [
        _make_players("QB", 40, base_fpts=350),
        _make_players("RB", 60, base_fpts=250),
        _make_players("WR", 60, base_fpts=240),
        _make_players("TE", 30, base_fpts=180),
        _make_players("K", 20, base_fpts=140),
        _make_players("DST", 20, base_fpts=130),
    ]
    return pd.concat(frames, ignore_index=True)


# ── Tests with synthetic data ─────────────────────────────────────────


class TestCalculateBaselineVOR:
    """Tests using deterministic synthetic data."""

    def test_adds_vor_columns(self, vor_calculator):
        df = _make_multi_position_df()
        result = vor_calculator.calculate_baseline_vor(df)

        assert "VOR_Standard" in result.columns
        assert "VOR_HalfPPR" in result.columns
        assert "VOR_FullPPR" in result.columns

    def test_top_player_has_highest_vor(self, vor_calculator):
        df = _make_multi_position_df()
        result = vor_calculator.calculate_baseline_vor(df)

        for position in VOR_BASELINE_COUNTS:
            pos_df = result[result["Position"] == position]
            if pos_df.empty:
                continue
            top = pos_df.sort_values("VOR_FullPPR", ascending=False).iloc[0]
            assert top["VOR_FullPPR"] > 0, f"Top {position} should have positive VOR"

    def test_replacement_player_has_zero_vor(self, vor_calculator):
        """The player at the baseline index should have VOR ≈ 0."""
        df = _make_multi_position_df()
        result = vor_calculator.calculate_baseline_vor(df)

        for position, baseline in VOR_BASELINE_COUNTS.items():
            pos_df = result[result["Position"] == position].sort_values(
                "VOR_FullPPR", ascending=False
            )
            if len(pos_df) <= baseline:
                continue
            repl = pos_df.iloc[baseline]
            assert repl["VOR_FullPPR"] == pytest.approx(0, abs=0.01), (
                f"{position} replacement player should have ~0 VOR"
            )

    def test_below_replacement_is_negative(self, vor_calculator):
        """Players below the replacement line should have negative VOR."""
        df = _make_multi_position_df()
        result = vor_calculator.calculate_baseline_vor(df)

        for position, baseline in VOR_BASELINE_COUNTS.items():
            pos_df = result[result["Position"] == position].sort_values(
                "VOR_FullPPR", ascending=False
            )
            if len(pos_df) <= baseline + 1:
                continue
            below = pos_df.iloc[baseline + 1]
            assert below["VOR_FullPPR"] < 0, (
                f"Below-replacement {position} should have negative VOR"
            )

    def test_vor_ordering_across_scoring_formats(self, vor_calculator):
        """For receivers, Full PPR VOR > Half PPR VOR > Standard VOR."""
        df = _make_multi_position_df()
        result = vor_calculator.calculate_baseline_vor(df)

        # Pick top WR (has receptions, so scoring differs)
        top_wr = result[result["Position"] == "WR"].sort_values(
            "VOR_FullPPR", ascending=False
        ).iloc[0]

        assert top_wr["VOR_FullPPR"] > top_wr["VOR_HalfPPR"]
        assert top_wr["VOR_HalfPPR"] > top_wr["VOR_Standard"]

    def test_does_not_mutate_input(self, vor_calculator):
        df = _make_multi_position_df()
        original_cols = set(df.columns)
        vor_calculator.calculate_baseline_vor(df)

        assert set(df.columns) == original_cols, "Input DataFrame should not be mutated"

    def test_handles_fewer_players_than_baseline(self, vor_calculator):
        """If a position has fewer players than the baseline count,
        the last player is used as the replacement level."""
        # Only 5 QBs, baseline is 12
        df = _make_players("QB", 5, base_fpts=300)
        # Need scoring variant columns
        result = vor_calculator.calculate_baseline_vor(df)

        # Top player should still have positive VOR
        top = result.sort_values("VOR_FullPPR", ascending=False).iloc[0]
        assert top["VOR_FullPPR"] > 0

        # Last player = replacement, should have VOR ≈ 0
        last = result.sort_values("VOR_FullPPR", ascending=False).iloc[-1]
        assert last["VOR_FullPPR"] == pytest.approx(0, abs=0.01)

    def test_empty_position_skipped(self, vor_calculator):
        """Positions with no players should not cause errors."""
        df = _make_players("QB", 20, base_fpts=300)
        result = vor_calculator.calculate_baseline_vor(df)

        assert "VOR_FullPPR" in result.columns
        assert len(result) == 20

    def test_all_positions_get_vor(self, vor_calculator):
        df = _make_multi_position_df()
        result = vor_calculator.calculate_baseline_vor(df)

        for position in VOR_BASELINE_COUNTS:
            pos_df = result[result["Position"] == position]
            assert pos_df["VOR_FullPPR"].notna().all(), (
                f"All {position} players should have VOR"
            )


# ── Tests with real 2025 data ─────────────────────────────────────────


class TestVORWithRealData:
    """Integration tests using real 2025 CSV data."""

    def test_vor_on_transformed_data(self, vor_calculator, transformed_data):
        result = vor_calculator.calculate_baseline_vor(transformed_data)

        assert "VOR_Standard" in result.columns
        assert "VOR_HalfPPR" in result.columns
        assert "VOR_FullPPR" in result.columns
        assert len(result) == len(transformed_data)

    def test_top_vor_players_are_stars(self, vor_calculator, transformed_data):
        """Top VOR players should be recognizable stars."""
        result = vor_calculator.calculate_baseline_vor(transformed_data)
        top5 = result.nlargest(5, "VOR_HalfPPR")

        # All top-5 should have substantial VOR
        for _, row in top5.iterrows():
            assert row["VOR_HalfPPR"] > 20, (
                f"{row['Player']} VOR too low: {row['VOR_HalfPPR']:.1f}"
            )

    def test_every_position_has_positive_vor_players(
        self, vor_calculator, transformed_data
    ):
        result = vor_calculator.calculate_baseline_vor(transformed_data)

        for position in VOR_BASELINE_COUNTS:
            pos_positive = result[
                (result["Position"] == position) & (result["VOR_HalfPPR"] > 0)
            ]
            assert len(pos_positive) > 0, (
                f"No positive-VOR players at {position}"
            )

    def test_negative_vor_exists(self, vor_calculator, transformed_data):
        """There should be below-replacement players with negative VOR."""
        result = vor_calculator.calculate_baseline_vor(transformed_data)
        negative = result[result["VOR_HalfPPR"] < 0]
        assert len(negative) > 0, "Expected some below-replacement players"

    def test_receiver_vor_higher_in_ppr(self, vor_calculator, transformed_data):
        """Across all WRs, average Full PPR VOR should exceed Standard VOR."""
        result = vor_calculator.calculate_baseline_vor(transformed_data)
        wrs = result[result["Position"] == "WR"]

        avg_ppr = wrs["VOR_FullPPR"].mean()
        avg_std = wrs["VOR_Standard"].mean()
        # Mean VOR should be roughly 0 for both (it's relative), but
        # the top players' VOR spread should be wider in PPR
        top_ppr = wrs.nlargest(10, "VOR_FullPPR")["VOR_FullPPR"].mean()
        top_std = wrs.nlargest(10, "VOR_Standard")["VOR_Standard"].mean()
        assert top_ppr > top_std, "Top WR VOR should be higher in Full PPR"
