"""Tests for the FantasyPros data transformation module.

Fixtures ``transformer``, ``cleaned_data``, ``merged_projections``, and
``projections_with_scoring`` are provided by conftest.py.
"""

import pandas as pd
import pytest

from src.data_pipeline.transformation import DataTransformer, UNRANKED_OVERALL


# ---------------------------------------------------------------------------
# Merge projections
# ---------------------------------------------------------------------------

class TestMergeProjections:
    def test_all_positions_present(self, merged_projections):
        positions = merged_projections["Position"].unique()
        for pos in ["QB", "RB", "WR", "TE", "K", "DST"]:
            assert pos in positions, f"Missing position: {pos}"

    def test_total_player_count(self, merged_projections):
        # Should have QB + FLEX + K + DST players
        assert len(merged_projections) > 200

    def test_fpts_populated(self, merged_projections):
        assert merged_projections["FPTS"].notna().all()
        # ~11% of players are fringe roster (backup QBs, deep TEs, etc.) with 0
        # projected points; 1 player (Ihmir Smith-Marsette) is legitimately negative.
        # 85% threshold catches data-quality regressions while allowing that tail.
        assert (merged_projections["FPTS"] > 0).sum() > len(merged_projections) * 0.85

    def test_stat_columns_present(self, merged_projections):
        expected = [
            "Pass_Att", "Pass_Yds", "Rush_Att", "Rush_Yds",
            "Rec", "Rec_Yds", "FL", "FG", "FGA", "XPT",
        ]
        for col in expected:
            assert col in merged_projections.columns, f"Missing column: {col}"

    def test_qb_has_passing_stats(self, merged_projections):
        qbs = merged_projections[merged_projections["Position"] == "QB"]
        assert qbs["Pass_Att"].max() > 300
        assert qbs["Pass_Yds"].max() > 3000

    def test_rb_has_rushing_stats(self, merged_projections):
        rbs = merged_projections[merged_projections["Position"] == "RB"]
        assert rbs["Rush_Att"].max() > 200
        assert rbs["Rush_Yds"].max() > 1000

    def test_wr_has_receiving_stats(self, merged_projections):
        wrs = merged_projections[merged_projections["Position"] == "WR"]
        assert wrs["Rec"].max() > 80
        assert wrs["Rec_Yds"].max() > 1000

    def test_k_has_fg_stats(self, merged_projections):
        ks = merged_projections[merged_projections["Position"] == "K"]
        assert ks["FG"].max() > 20

    def test_player_norm_populated(self, merged_projections):
        assert merged_projections["Player_Norm"].notna().all()

    def test_team_abbr_populated(self, merged_projections):
        # DST might have blank Team in the raw CSV but should resolve via Player
        non_dst = merged_projections[merged_projections["Position"] != "DST"]
        assert non_dst["Team_Abbr"].notna().all()


# ---------------------------------------------------------------------------
# Scoring variants
# ---------------------------------------------------------------------------

class TestScoringVariants:
    def test_adds_three_columns(self, transformer, merged_projections):
        result = transformer.calculate_scoring_variants(merged_projections)
        assert "FPTS_Standard" in result.columns
        assert "FPTS_HalfPPR" in result.columns
        assert "FPTS_FullPPR" in result.columns

    def test_full_ppr_equals_fpts(self, transformer, merged_projections):
        result = transformer.calculate_scoring_variants(merged_projections)
        pd.testing.assert_series_equal(
            result["FPTS_FullPPR"], result["FPTS"], check_names=False
        )

    def test_standard_less_than_full_ppr_for_receivers(self, transformer, merged_projections):
        result = transformer.calculate_scoring_variants(merged_projections)
        wrs = result[result["Position"] == "WR"]
        # WRs catch passes, so Standard < Full PPR
        assert (wrs["FPTS_Standard"] <= wrs["FPTS_FullPPR"]).all()

    def test_half_ppr_between_standard_and_full(self, transformer, merged_projections):
        result = transformer.calculate_scoring_variants(merged_projections)
        flex = result[result["Position"].isin(["RB", "WR", "TE"])]
        assert (flex["FPTS_Standard"] <= flex["FPTS_HalfPPR"]).all()
        assert (flex["FPTS_HalfPPR"] <= flex["FPTS_FullPPR"]).all()

    def test_qb_scoring_similar(self, transformer, merged_projections):
        """QBs have very few receptions, so all three formats should be close."""
        result = transformer.calculate_scoring_variants(merged_projections)
        qbs = result[result["Position"] == "QB"]
        diff = (qbs["FPTS_FullPPR"] - qbs["FPTS_Standard"]).abs()
        # Most QBs have 0 receptions; a few dual-threat QBs may have a handful
        assert (diff < 5).all()

    def test_standard_formula(self, transformer, merged_projections):
        """FPTS_Standard = FPTS - Rec (remove full PPR bonus)."""
        result = transformer.calculate_scoring_variants(merged_projections)
        expected = result["FPTS"] - result["Rec"]
        pd.testing.assert_series_equal(
            result["FPTS_Standard"], expected, check_names=False
        )

    def test_half_ppr_formula(self, transformer, merged_projections):
        """FPTS_HalfPPR = FPTS - (Rec * 0.5)."""
        result = transformer.calculate_scoring_variants(merged_projections)
        expected = result["FPTS"] - (result["Rec"] * 0.5)
        pd.testing.assert_series_equal(
            result["FPTS_HalfPPR"], expected, check_names=False
        )


# ---------------------------------------------------------------------------
# Merge with rankings
# ---------------------------------------------------------------------------

class TestMergeWithRankings:
    def test_adds_overall_rank(self, transformer, projections_with_scoring, cleaned_data):
        result = transformer.merge_with_rankings(projections_with_scoring, cleaned_data["rankings"])
        assert "Overall_Rank" in result.columns

    def test_adds_bye_week(self, transformer, projections_with_scoring, cleaned_data):
        result = transformer.merge_with_rankings(projections_with_scoring, cleaned_data["rankings"])
        assert "Bye_Week" in result.columns

    def test_adds_tier(self, transformer, projections_with_scoring, cleaned_data):
        result = transformer.merge_with_rankings(projections_with_scoring, cleaned_data["rankings"])
        assert "Tier" in result.columns

    def test_top_players_have_rank(self, transformer, projections_with_scoring, cleaned_data):
        result = transformer.merge_with_rankings(projections_with_scoring, cleaned_data["rankings"])
        # Some players should have real ranks (not the unranked sentinel)
        assert (result["Overall_Rank"] < UNRANKED_OVERALL).any()

    def test_unranked_players_get_sentinel(self, transformer, projections_with_scoring, cleaned_data):
        result = transformer.merge_with_rankings(projections_with_scoring, cleaned_data["rankings"])
        # Some fringe players won't be in rankings
        assert (result["Overall_Rank"] == UNRANKED_OVERALL).any()

    def test_no_duplicate_rows(self, transformer, projections_with_scoring, cleaned_data):
        result = transformer.merge_with_rankings(projections_with_scoring, cleaned_data["rankings"])
        # Should not create extra rows from many-to-many join
        assert len(result) == len(projections_with_scoring)


# ---------------------------------------------------------------------------
# Player IDs
# ---------------------------------------------------------------------------

class TestGeneratePlayerIds:
    def test_adds_player_id_column(self, transformer, merged_projections):
        result = transformer.generate_player_ids(merged_projections)
        assert "player_id" in result.columns

    def test_ids_are_lowercase(self, transformer, merged_projections):
        result = transformer.generate_player_ids(merged_projections)
        assert (result["player_id"] == result["player_id"].str.lower()).all()

    def test_ids_no_spaces(self, transformer, merged_projections):
        result = transformer.generate_player_ids(merged_projections)
        assert not result["player_id"].str.contains(" ").any()

    def test_id_format(self, transformer, merged_projections):
        result = transformer.generate_player_ids(merged_projections)
        # Pick the first player and verify the ID encodes name, position, team
        row = result.iloc[0]
        pid = row["player_id"]
        pos = row["Position"].lower()
        team = row["Team_Abbr"].lower()
        assert pos in pid, f"Expected position '{pos}' in player_id '{pid}'"
        assert team in pid, f"Expected team '{team}' in player_id '{pid}'"

    def test_ids_all_unique(self, transformer, merged_projections):
        result = transformer.generate_player_ids(merged_projections)
        # Dedup suffixes guarantee uniqueness
        assert not result["player_id"].duplicated().any()


# ---------------------------------------------------------------------------
# Full transform pipeline
# ---------------------------------------------------------------------------

class TestFullTransform:
    def test_end_to_end(self, transformer, cleaned_data):
        result = transformer.transform(cleaned_data)
        assert len(result) > 200

        # Has all expected columns
        for col in [
            "Player", "Position", "FPTS_Standard", "FPTS_HalfPPR",
            "FPTS_FullPPR", "Overall_Rank", "player_id",
        ]:
            assert col in result.columns, f"Missing column: {col}"

    def test_all_positions_present(self, transformer, cleaned_data):
        result = transformer.transform(cleaned_data)
        for pos in ["QB", "RB", "WR", "TE", "K", "DST"]:
            assert pos in result["Position"].values

    def test_top_player_has_rank_1(self, transformer, cleaned_data):
        result = transformer.transform(cleaned_data)
        assert result["Overall_Rank"].min() == 1

    def test_scoring_ordering(self, transformer, cleaned_data):
        """For WR/RB/TE: Standard <= Half PPR <= Full PPR."""
        result = transformer.transform(cleaned_data)
        flex = result[result["Position"].isin(["RB", "WR", "TE"])]
        assert (flex["FPTS_Standard"] <= flex["FPTS_HalfPPR"]).all()
        assert (flex["FPTS_HalfPPR"] <= flex["FPTS_FullPPR"]).all()

    def test_missing_key_raises(self, transformer):
        incomplete = {"qb": None, "flex": None}
        with pytest.raises(ValueError, match="Missing required DataFrames"):
            transformer.transform(incomplete)


# ---------------------------------------------------------------------------
# _safe_float edge cases
# ---------------------------------------------------------------------------

class TestSafeFloat:
    def test_none_returns_default(self):
        assert DataTransformer._safe_float(None) == 0.0

    def test_nan_returns_default(self):
        assert DataTransformer._safe_float(float("nan")) == 0.0

    def test_pd_na_returns_default(self):
        assert DataTransformer._safe_float(pd.NA) == 0.0

    def test_numeric_value_passes_through(self):
        assert DataTransformer._safe_float(3.5) == 3.5

    def test_custom_default(self):
        assert DataTransformer._safe_float(None, default=-1.0) == -1.0
