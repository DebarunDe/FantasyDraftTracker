"""Tests for the FantasyPros CSV ingestion module."""

import textwrap
from pathlib import Path

import pandas as pd
import pytest

from src.data_pipeline.ingestion import FantasyProsIngester, IngestionError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "2025"


@pytest.fixture
def ingester():
    """Ingester pointing at the real 2025 data directory."""
    return FantasyProsIngester(DATA_DIR, year=2025)


@pytest.fixture
def tmp_ingester(tmp_path):
    """Ingester pointing at a temporary directory for isolation tests."""
    return FantasyProsIngester(tmp_path, year=2025)


# ---------------------------------------------------------------------------
# Rankings tests
# ---------------------------------------------------------------------------

class TestReadRankings:
    def test_loads_all_players(self, ingester):
        df = ingester.read_rankings()
        assert len(df) > 500, f"Expected 500+ players, got {len(df)}"

    def test_expected_columns(self, ingester):
        df = ingester.read_rankings()
        expected = {"RK", "TIERS", "PLAYER NAME", "TEAM", "POS", "BYE WEEK"}
        assert expected.issubset(set(df.columns))

    def test_rk_is_numeric(self, ingester):
        df = ingester.read_rankings()
        assert pd.api.types.is_numeric_dtype(df["RK"])
        assert df["RK"].min() == 1

    def test_positions_embedded_in_pos(self, ingester):
        df = ingester.read_rankings()
        # POS should look like WR1, RB2, QB1 (letters + digits)
        sample = df["POS"].head(20)
        for pos in sample:
            assert any(c.isdigit() for c in pos), f"Expected rank in POS: {pos}"

    def test_no_blank_player_names(self, ingester):
        df = ingester.read_rankings()
        assert df["PLAYER NAME"].notna().all()
        assert (df["PLAYER NAME"].str.strip() != "").all()


# ---------------------------------------------------------------------------
# QB projection tests
# ---------------------------------------------------------------------------

class TestReadQBProjections:
    def test_loads_qbs(self, ingester):
        df = ingester.read_qb_projections()
        assert len(df) > 30, f"Expected 30+ QBs, got {len(df)}"

    def test_no_duplicate_columns(self, ingester):
        df = ingester.read_qb_projections()
        assert len(df.columns) == len(set(df.columns))

    def test_disambiguated_column_names(self, ingester):
        df = ingester.read_qb_projections()
        assert "Pass_Att" in df.columns
        assert "Rush_Att" in df.columns
        assert "Pass_Yds" in df.columns
        assert "Rush_Yds" in df.columns

    def test_numeric_stats(self, ingester):
        df = ingester.read_qb_projections()
        for col in ["Pass_Att", "Pass_Yds", "Rush_Yds", "FPTS"]:
            assert pd.api.types.is_numeric_dtype(df[col]), f"{col} should be numeric"

    def test_comma_numbers_parsed(self, ingester):
        """Values like '3,904.1' should parse to 3904.1."""
        df = ingester.read_qb_projections()
        # Top QBs pass for 3000+ yards
        assert df["Pass_Yds"].max() > 3000

    def test_no_blank_rows(self, ingester):
        df = ingester.read_qb_projections()
        assert df["Player"].notna().all()
        assert (df["Player"].str.strip() != "").all()


# ---------------------------------------------------------------------------
# FLEX projection tests (RB/WR/TE)
# ---------------------------------------------------------------------------

class TestReadFlexProjections:
    def test_loads_flex_players(self, ingester):
        df = ingester.read_flex_projections()
        assert len(df) > 200, f"Expected 200+ FLEX, got {len(df)}"

    def test_no_duplicate_columns(self, ingester):
        df = ingester.read_flex_projections()
        assert len(df.columns) == len(set(df.columns))

    def test_disambiguated_column_names(self, ingester):
        df = ingester.read_flex_projections()
        assert "Rush_Yds" in df.columns
        assert "Rec_Yds" in df.columns
        assert "Rush_TD" in df.columns
        assert "Rec_TD" in df.columns

    def test_pos_column_present(self, ingester):
        df = ingester.read_flex_projections()
        assert "POS" in df.columns
        sample = df["POS"].head(10)
        for pos in sample:
            assert any(c.isdigit() for c in str(pos)), f"Expected rank in POS: {pos}"

    def test_contains_multiple_positions(self, ingester):
        df = ingester.read_flex_projections()
        positions = df["POS"].str.extract(r"([A-Z]+)", expand=False).unique()
        assert "RB" in positions
        assert "WR" in positions
        assert "TE" in positions

    def test_numeric_stats(self, ingester):
        df = ingester.read_flex_projections()
        for col in ["Rush_Yds", "Rec_Yds", "Rec", "FPTS"]:
            assert pd.api.types.is_numeric_dtype(df[col]), f"{col} should be numeric"


# ---------------------------------------------------------------------------
# Kicker projection tests
# ---------------------------------------------------------------------------

class TestReadKProjections:
    def test_loads_kickers(self, ingester):
        df = ingester.read_k_projections()
        assert len(df) > 20, f"Expected 20+ kickers, got {len(df)}"

    def test_expected_columns(self, ingester):
        df = ingester.read_k_projections()
        assert {"Player", "Team", "FG", "FGA", "XPT", "FPTS"}.issubset(set(df.columns))

    def test_numeric_stats(self, ingester):
        df = ingester.read_k_projections()
        for col in ["FG", "FGA", "XPT", "FPTS"]:
            assert pd.api.types.is_numeric_dtype(df[col]), f"{col} should be numeric"


# ---------------------------------------------------------------------------
# DST projection tests
# ---------------------------------------------------------------------------

class TestReadDSTProjections:
    def test_loads_dsts(self, ingester):
        df = ingester.read_dst_projections()
        assert len(df) > 20, f"Expected 20+ DSTs, got {len(df)}"

    def test_expected_columns(self, ingester):
        df = ingester.read_dst_projections()
        expected = {"Player", "SACK", "INT", "FR", "TD", "FPTS"}
        assert expected.issubset(set(df.columns))

    def test_player_is_team_name(self, ingester):
        df = ingester.read_dst_projections()
        # DST "Player" column should be full team names
        assert any("Eagles" in p for p in df["Player"])

    def test_numeric_stats(self, ingester):
        df = ingester.read_dst_projections()
        for col in ["SACK", "INT", "FPTS"]:
            assert pd.api.types.is_numeric_dtype(df[col]), f"{col} should be numeric"


# ---------------------------------------------------------------------------
# read_all convenience method
# ---------------------------------------------------------------------------

class TestReadAll:
    def test_returns_all_keys(self, ingester):
        data = ingester.read_all()
        assert set(data.keys()) == {"rankings", "qb", "flex", "k", "dst"}

    def test_all_dataframes_non_empty(self, ingester):
        data = ingester.read_all()
        for key, df in data.items():
            assert len(df) > 0, f"{key} DataFrame is empty"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_missing_file_raises_file_not_found(self, tmp_ingester):
        with pytest.raises(FileNotFoundError):
            tmp_ingester.read_rankings()

    def test_read_all_wraps_errors(self, tmp_ingester):
        with pytest.raises(IngestionError):
            tmp_ingester.read_all()

    def test_missing_qb_file_raises(self, tmp_ingester):
        with pytest.raises(FileNotFoundError):
            tmp_ingester.read_qb_projections()
