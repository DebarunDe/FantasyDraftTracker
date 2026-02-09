"""Tests for the FantasyPros data cleaning module.

Fixtures ``cleaner`` and ``ingester`` are provided by conftest.py.
"""

from src.data_pipeline.cleaning import TEAM_NAME_TO_ABBR


# ---------------------------------------------------------------------------
# Position extraction
# ---------------------------------------------------------------------------

class TestExtractBasePosition:
    def test_wr(self, cleaner):
        assert cleaner.extract_base_position("WR1") == "WR"

    def test_rb(self, cleaner):
        assert cleaner.extract_base_position("RB23") == "RB"

    def test_qb(self, cleaner):
        assert cleaner.extract_base_position("QB1") == "QB"

    def test_te(self, cleaner):
        assert cleaner.extract_base_position("TE12") == "TE"

    def test_k(self, cleaner):
        assert cleaner.extract_base_position("K5") == "K"

    def test_dst(self, cleaner):
        assert cleaner.extract_base_position("DST1") == "DST"

    def test_pk_alias(self, cleaner):
        assert cleaner.extract_base_position("PK3") == "K"

    def test_def_alias(self, cleaner):
        assert cleaner.extract_base_position("DEF1") == "DST"

    def test_none_input(self, cleaner):
        assert cleaner.extract_base_position(None) is None

    def test_nan_input(self, cleaner):
        assert cleaner.extract_base_position(float("nan")) is None

    def test_bare_position_no_rank(self, cleaner):
        assert cleaner.extract_base_position("QB") == "QB"

    def test_invalid_position(self, cleaner):
        assert cleaner.extract_base_position("XY1") is None


class TestExtractPositionRank:
    def test_wr1(self, cleaner):
        assert cleaner.extract_position_rank("WR1") == 1

    def test_rb23(self, cleaner):
        assert cleaner.extract_position_rank("RB23") == 23

    def test_no_rank(self, cleaner):
        assert cleaner.extract_position_rank("QB") is None

    def test_none(self, cleaner):
        assert cleaner.extract_position_rank(None) is None


# ---------------------------------------------------------------------------
# Team name standardization
# ---------------------------------------------------------------------------

class TestStandardizeTeamName:
    def test_full_name(self, cleaner):
        assert cleaner.standardize_team_name("Philadelphia Eagles") == "PHI"

    def test_abbreviation_passthrough(self, cleaner):
        assert cleaner.standardize_team_name("PHI") == "PHI"

    def test_all_teams_mapped(self, cleaner):
        for full, abbr in TEAM_NAME_TO_ABBR.items():
            assert cleaner.standardize_team_name(full) == abbr

    def test_none_input(self, cleaner):
        assert cleaner.standardize_team_name(None) is None

    def test_blank_input(self, cleaner):
        assert cleaner.standardize_team_name("") is None
        assert cleaner.standardize_team_name("  ") is None

    def test_quoted_value(self, cleaner):
        assert cleaner.standardize_team_name('"CIN"') == "CIN"


# ---------------------------------------------------------------------------
# Player name normalization
# ---------------------------------------------------------------------------

class TestNormalizePlayerName:
    def test_basic_name(self, cleaner):
        assert cleaner.normalize_player_name("Ja'Marr Chase") == "Ja'Marr Chase"

    def test_strips_quotes(self, cleaner):
        assert cleaner.normalize_player_name('"Saquon Barkley"') == "Saquon Barkley"

    def test_collapses_whitespace(self, cleaner):
        assert cleaner.normalize_player_name("  Bijan   Robinson  ") == "Bijan Robinson"

    def test_none(self, cleaner):
        assert cleaner.normalize_player_name(None) is None

    def test_blank(self, cleaner):
        assert cleaner.normalize_player_name("") is None

    def test_suffix_preserved(self, cleaner):
        """normalize_player_name keeps suffixes; strip_name_suffix removes them."""
        assert cleaner.normalize_player_name("Odell Beckham Jr.") == "Odell Beckham Jr."
        assert cleaner.normalize_player_name("James Cook III") == "James Cook III"
        assert cleaner.normalize_player_name("Patrick Mahomes II") == "Patrick Mahomes II"

    def test_strip_name_suffix(self, cleaner):
        assert cleaner.strip_name_suffix("Odell Beckham Jr.") == "Odell Beckham"
        assert cleaner.strip_name_suffix("James Cook III") == "James Cook"
        assert cleaner.strip_name_suffix("Patrick Mahomes II") == "Patrick Mahomes"
        assert cleaner.strip_name_suffix("Aaron Jones Sr.") == "Aaron Jones"
        assert cleaner.strip_name_suffix("Stetson Bennett IV") == "Stetson Bennett"
        assert cleaner.strip_name_suffix("David Sills V") == "David Sills"
        # No suffix — unchanged
        assert cleaner.strip_name_suffix("Ja'Marr Chase") == "Ja'Marr Chase"
        assert cleaner.strip_name_suffix(None) is None

    def test_hyphenated_name(self, cleaner):
        assert cleaner.normalize_player_name("Amon-Ra St. Brown") == "Amon-Ra St. Brown"

    def test_curly_apostrophe_normalized(self, cleaner):
        assert cleaner.normalize_player_name("Ja\u2019Marr Chase") == "Ja'Marr Chase"

    def test_left_curly_apostrophe_normalized(self, cleaner):
        assert cleaner.normalize_player_name("O\u2018Brien") == "O'Brien"

    def test_modifier_apostrophe_normalized(self, cleaner):
        assert cleaner.normalize_player_name("Ja\u02BCMarr Chase") == "Ja'Marr Chase"

    def test_en_dash_normalized(self, cleaner):
        assert cleaner.normalize_player_name("Amon\u2013Ra St. Brown") == "Amon-Ra St. Brown"

    def test_em_dash_normalized(self, cleaner):
        assert cleaner.normalize_player_name("Amon\u2014Ra St. Brown") == "Amon-Ra St. Brown"


# ---------------------------------------------------------------------------
# DataFrame-level cleaning (integration with real data)
# ---------------------------------------------------------------------------

class TestCleanRankings:
    def test_adds_expected_columns(self, cleaner, ingester):
        raw = ingester.read_rankings()
        cleaned = cleaner.clean_rankings(raw)
        assert "Position" in cleaned.columns
        assert "Pos_Rank" in cleaned.columns
        assert "Team_Abbr" in cleaned.columns
        assert "Player_Norm" in cleaned.columns

    def test_all_positions_valid(self, cleaner, ingester):
        raw = ingester.read_rankings()
        cleaned = cleaner.clean_rankings(raw)
        valid = {"QB", "RB", "WR", "TE", "K", "DST"}
        positions = cleaned["Position"].dropna().unique()
        for pos in positions:
            assert pos in valid, f"Unexpected position: {pos}"

    def test_position_rank_numeric(self, cleaner, ingester):
        raw = ingester.read_rankings()
        cleaned = cleaner.clean_rankings(raw)
        ranks = cleaned["Pos_Rank"].dropna()
        assert (ranks > 0).all()
        assert (ranks == ranks.astype(int)).all()

    def test_team_abbr_short(self, cleaner, ingester):
        raw = ingester.read_rankings()
        cleaned = cleaner.clean_rankings(raw)
        abbrs = cleaned["Team_Abbr"].dropna()
        # All abbreviations should be 2-3 characters
        assert (abbrs.str.len() >= 2).all()
        assert (abbrs.str.len() <= 3).all()


class TestCleanQBProjections:
    def test_position_is_qb(self, cleaner, ingester):
        raw = ingester.read_qb_projections()
        cleaned = cleaner.clean_qb_projections(raw)
        assert (cleaned["Position"] == "QB").all()

    def test_player_norm_populated(self, cleaner, ingester):
        raw = ingester.read_qb_projections()
        cleaned = cleaner.clean_qb_projections(raw)
        assert cleaned["Player_Norm"].notna().all()


class TestCleanFlexProjections:
    def test_positions_extracted(self, cleaner, ingester):
        raw = ingester.read_flex_projections()
        cleaned = cleaner.clean_flex_projections(raw)
        positions = cleaned["Position"].dropna().unique()
        assert "RB" in positions
        assert "WR" in positions
        assert "TE" in positions

    def test_pos_rank_populated(self, cleaner, ingester):
        raw = ingester.read_flex_projections()
        cleaned = cleaner.clean_flex_projections(raw)
        assert cleaned["Pos_Rank"].notna().any()


class TestCleanKProjections:
    def test_position_is_k(self, cleaner, ingester):
        raw = ingester.read_k_projections()
        cleaned = cleaner.clean_k_projections(raw)
        assert (cleaned["Position"] == "K").all()

    def test_player_norm_populated(self, cleaner, ingester):
        raw = ingester.read_k_projections()
        cleaned = cleaner.clean_k_projections(raw)
        assert cleaned["Player_Norm"].notna().all()

    def test_team_abbr_populated(self, cleaner, ingester):
        raw = ingester.read_k_projections()
        cleaned = cleaner.clean_k_projections(raw)
        assert cleaned["Team_Abbr"].notna().all()


class TestCleanDSTProjections:
    def test_position_is_dst(self, cleaner, ingester):
        raw = ingester.read_dst_projections()
        cleaned = cleaner.clean_dst_projections(raw)
        assert (cleaned["Position"] == "DST").all()

    def test_team_abbr_from_player(self, cleaner, ingester):
        raw = ingester.read_dst_projections()
        cleaned = cleaner.clean_dst_projections(raw)
        # Should resolve full team names to abbreviations
        assert "PHI" in cleaned["Team_Abbr"].values


class TestCleanAll:
    def test_returns_all_keys(self, cleaner, ingester):
        raw = ingester.read_all()
        cleaned = cleaner.clean_all(raw)
        assert set(cleaned.keys()) == {"rankings", "qb", "flex", "k", "dst"}

    def test_all_have_player_norm(self, cleaner, ingester):
        raw = ingester.read_all()
        cleaned = cleaner.clean_all(raw)
        for key in cleaned:
            assert "Player_Norm" in cleaned[key].columns, f"{key} missing Player_Norm"

    def test_all_have_position(self, cleaner, ingester):
        raw = ingester.read_all()
        cleaned = cleaner.clean_all(raw)
        for key in cleaned:
            assert "Position" in cleaned[key].columns, f"{key} missing Position"
