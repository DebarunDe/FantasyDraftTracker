"""Data cleaning for FantasyPros CSV data.

Handles standardization across the five CSV files:
- Extract base position from rank format (WR1 -> WR)
- Extract numeric position rank (WR1 -> 1)
- Standardize team names (full names -> abbreviations)
- Normalize player names for cross-file matching
"""

import logging
import re
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Full team name -> standard abbreviation
TEAM_NAME_TO_ABBR = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAC",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}

# Valid base positions
_VALID_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DST"}

# Aliases that map to canonical position names
_POSITION_ALIASES = {
    "PK": "K",
    "DEF": "DST",
}

# Regex: one or more letters followed by optional digits
_POS_PATTERN = re.compile(r"^([A-Za-z]+?)(\d+)?$")


class DataCleaner:
    """Cleans and standardizes FantasyPros data for cross-file merging."""

    # ------------------------------------------------------------------
    # Position helpers
    # ------------------------------------------------------------------
    @staticmethod
    def extract_base_position(pos_str: str) -> Optional[str]:
        """Extract the base position from a rank-embedded string.

        Examples:
            "WR1"  -> "WR"
            "RB23" -> "RB"
            "QB1"  -> "QB"
            "K5"   -> "K"
        """
        if pd.isna(pos_str):
            return None

        m = _POS_PATTERN.match(str(pos_str).strip())
        if not m:
            return None

        letters = m.group(1).upper()
        canonical = _POSITION_ALIASES.get(letters, letters)
        return canonical if canonical in _VALID_POSITIONS else None

    @staticmethod
    def extract_position_rank(pos_str: str) -> Optional[int]:
        """Extract the numeric rank from a position string.

        Examples:
            "WR1"  -> 1
            "RB23" -> 23
            "K5"   -> 5
            "QB"   -> None
        """
        if pd.isna(pos_str):
            return None

        m = _POS_PATTERN.match(str(pos_str).strip())
        if not m or m.group(2) is None:
            return None

        return int(m.group(2))

    # ------------------------------------------------------------------
    # Team name standardization
    # ------------------------------------------------------------------
    @staticmethod
    def standardize_team_name(team: str) -> Optional[str]:
        """Standardize a team identifier to its abbreviation.

        Handles both full names ("Philadelphia Eagles" -> "PHI")
        and abbreviations that are already correct ("PHI" -> "PHI").

        Returns None for missing / blank values.
        """
        if pd.isna(team):
            return None
        team = str(team).strip().strip('"')
        if team == "":
            return None

        # Full name lookup
        if team in TEAM_NAME_TO_ABBR:
            return TEAM_NAME_TO_ABBR[team]

        # Already an abbreviation
        return team

    # ------------------------------------------------------------------
    # Player name normalization
    # ------------------------------------------------------------------
    @staticmethod
    def normalize_player_name(name: str) -> Optional[str]:
        """Normalize a player name for consistent cross-file matching.

        - Strips quotes and extra whitespace
        - Preserves suffixes (Jr., III, etc.)
        - Standardizes apostrophes and hyphens
        """
        if pd.isna(name):
            return None

        name = str(name).strip().strip('"')
        if name == "":
            return None

        # Standardize apostrophe variants to ASCII straight quote
        name = name.replace("\u2019", "'")   # right single curly '
        name = name.replace("\u2018", "'")   # left single curly '
        name = name.replace("\u02BC", "'")   # modifier letter apostrophe ʼ

        # Standardize dash variants to ASCII hyphen-minus
        name = name.replace("\u2013", "-")   # en dash –
        name = name.replace("\u2014", "-")   # em dash —

        # Collapse whitespace
        name = " ".join(name.split())

        return name

    # ------------------------------------------------------------------
    # DataFrame-level cleaning
    # ------------------------------------------------------------------
    def clean_rankings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean the rankings DataFrame.

        Adds columns:
            Position  - base position (WR, RB, ...)
            Pos_Rank  - numeric position rank
            Team_Abbr - standardized team abbreviation
            Player_Norm - normalized player name for matching
        """
        out = df.copy()
        out["Position"] = out["POS"].apply(self.extract_base_position)
        out["Pos_Rank"] = out["POS"].apply(self.extract_position_rank)
        out["Team_Abbr"] = out["TEAM"].apply(self.standardize_team_name)
        out["Player_Norm"] = out["PLAYER NAME"].apply(self.normalize_player_name)
        logger.info("Cleaned rankings: %d rows", len(out))
        return out

    def clean_qb_projections(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean QB projections. Adds Position, Team_Abbr, Player_Norm."""
        out = df.copy()
        out["Position"] = "QB"
        out["Team_Abbr"] = out["Team"].apply(self.standardize_team_name)
        out["Player_Norm"] = out["Player"].apply(self.normalize_player_name)
        logger.info("Cleaned QB projections: %d rows", len(out))
        return out

    def clean_flex_projections(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean FLEX projections. Adds Position, Pos_Rank, Team_Abbr, Player_Norm."""
        out = df.copy()
        out["Position"] = out["POS"].apply(self.extract_base_position)
        out["Pos_Rank"] = out["POS"].apply(self.extract_position_rank)
        out["Team_Abbr"] = out["Team"].apply(self.standardize_team_name)
        out["Player_Norm"] = out["Player"].apply(self.normalize_player_name)
        logger.info("Cleaned FLEX projections: %d rows", len(out))
        return out

    def clean_k_projections(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean kicker projections. Adds Position, Team_Abbr, Player_Norm."""
        out = df.copy()
        out["Position"] = "K"
        out["Team_Abbr"] = out["Team"].apply(self.standardize_team_name)
        out["Player_Norm"] = out["Player"].apply(self.normalize_player_name)
        logger.info("Cleaned K projections: %d rows", len(out))
        return out

    def clean_dst_projections(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean DST projections. Adds Position, Team_Abbr, Player_Norm.

        For DSTs the Player column contains full team names, so Team_Abbr
        is derived from the Player column.
        """
        out = df.copy()
        out["Position"] = "DST"
        out["Team_Abbr"] = out["Player"].apply(self.standardize_team_name)
        out["Player_Norm"] = out["Player"].apply(self.normalize_player_name)
        logger.info("Cleaned DST projections: %d rows", len(out))
        return out

    def clean_all(
        self, data: dict[str, pd.DataFrame]
    ) -> dict[str, pd.DataFrame]:
        """Clean all five DataFrames returned by FantasyProsIngester.read_all().

        Expects keys: rankings, qb, flex, k, dst.
        Returns a dict with the same keys, each cleaned.
        """
        return {
            "rankings": self.clean_rankings(data["rankings"]),
            "qb": self.clean_qb_projections(data["qb"]),
            "flex": self.clean_flex_projections(data["flex"]),
            "k": self.clean_k_projections(data["k"]),
            "dst": self.clean_dst_projections(data["dst"]),
        }
