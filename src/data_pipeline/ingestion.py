"""CSV ingestion for FantasyPros data files.

Handles the quirks of each FantasyPros export format:
- Duplicate column names in QB and FLEX files
- Empty placeholder rows after headers
- Comma-formatted numbers (e.g., "3,904.1")
- Mixed quoting in rankings file
"""

import logging
from pathlib import Path

import pandas as pd

from src.data_pipeline.config import FILE_PATTERNS, QB_COLUMNS, FLEX_COLUMNS

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """Raised when CSV ingestion fails."""


def _parse_numeric(value):
    """Parse a numeric string that may contain commas (e.g., '3,904.1' -> 3904.1)."""
    if pd.isna(value):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).replace(",", "").strip().strip('"')
    if s == "" or s.isspace():
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


class FantasyProsIngester:
    """Reads FantasyPros CSV exports with position-aware parsing.

    Each read method returns a cleaned pandas DataFrame with:
    - Unambiguous column names (no duplicates)
    - Numeric columns parsed as floats
    - Empty/placeholder rows removed
    """

    def __init__(self, data_dir: Path, year: int):
        self.data_dir = Path(data_dir)
        self.year = year

    def _resolve_path(self, file_key: str) -> Path:
        """Build the full file path for a given file key, raising if missing."""
        filename = FILE_PATTERNS[file_key].format(year=self.year)
        filepath = self.data_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(
                f"Expected file not found: {filepath}"
            )
        return filepath

    # ------------------------------------------------------------------
    # Rankings
    # ------------------------------------------------------------------
    def read_rankings(self) -> pd.DataFrame:
        """Read the overall rankings file.

        Returns DataFrame with columns:
            RK, TIERS, PLAYER NAME, TEAM, POS, BYE WEEK,
            SOS SEASON, ECR VS. ADP
        """
        filepath = self._resolve_path("rankings")
        logger.info("Reading rankings: %s", filepath.name)

        df = pd.read_csv(filepath, quotechar='"')

        # Strip surrounding quotes from string values
        for col in df.select_dtypes(include=["object", "str"]).columns:
            df[col] = df[col].str.strip('"').str.strip()

        # Ensure RK is numeric
        df["RK"] = pd.to_numeric(df["RK"], errors="coerce")
        df["TIERS"] = pd.to_numeric(df["TIERS"], errors="coerce")

        # Drop rows where RK is NaN (e.g., blank rows)
        df = df.dropna(subset=["RK"])

        logger.info("Loaded %d ranked players", len(df))
        return df

    # ------------------------------------------------------------------
    # QB Projections
    # ------------------------------------------------------------------
    def read_qb_projections(self) -> pd.DataFrame:
        """Read QB projections handling duplicate ATT/YDS/TDS columns.

        Returns DataFrame with columns:
            Player, Team, Pass_Att, Pass_Cmp, Pass_Yds, Pass_TD, Pass_Int,
            Rush_Att, Rush_Yds, Rush_TD, FL, FPTS
        """
        filepath = self._resolve_path("qb")
        logger.info("Reading QB projections: %s", filepath.name)

        # Skip the original header (row 0) so we can assign our own names,
        # then also skip the blank placeholder row (row 1).
        df = pd.read_csv(
            filepath,
            header=None,
            skiprows=2,
            quotechar='"',
            names=QB_COLUMNS,
        )

        df = self._clean_projection_df(df, numeric_cols=QB_COLUMNS[2:])
        logger.info("Loaded %d QB projections", len(df))
        return df

    # ------------------------------------------------------------------
    # FLEX Projections (RB / WR / TE)
    # ------------------------------------------------------------------
    def read_flex_projections(self) -> pd.DataFrame:
        """Read FLEX projections (RB/WR/TE combined) handling duplicate YDS/TDS.

        Returns DataFrame with columns:
            Player, Team, POS, Rush_Att, Rush_Yds, Rush_TD,
            Rec, Rec_Yds, Rec_TD, FL, FPTS
        """
        filepath = self._resolve_path("flex")
        logger.info("Reading FLEX projections: %s", filepath.name)

        df = pd.read_csv(
            filepath,
            header=None,
            skiprows=2,
            quotechar='"',
            names=FLEX_COLUMNS,
        )

        df = self._clean_projection_df(df, numeric_cols=FLEX_COLUMNS[3:])
        logger.info("Loaded %d FLEX projections", len(df))
        return df

    # ------------------------------------------------------------------
    # Kicker Projections
    # ------------------------------------------------------------------
    def read_k_projections(self) -> pd.DataFrame:
        """Read kicker projections.

        Returns DataFrame with columns:
            Player, Team, FG, FGA, XPT, FPTS
        """
        filepath = self._resolve_path("k")
        logger.info("Reading K projections: %s", filepath.name)

        df = pd.read_csv(filepath, quotechar='"')
        df = self._clean_projection_df(df, numeric_cols=["FG", "FGA", "XPT", "FPTS"])
        logger.info("Loaded %d K projections", len(df))
        return df

    # ------------------------------------------------------------------
    # DST Projections
    # ------------------------------------------------------------------
    def read_dst_projections(self) -> pd.DataFrame:
        """Read defense/special teams projections.

        Returns DataFrame with columns:
            Player, Team, SACK, INT, FR, FF, TD, SAFETY, PA, YDS_AGN, FPTS
        """
        filepath = self._resolve_path("dst")
        logger.info("Reading DST projections: %s", filepath.name)

        df = pd.read_csv(filepath, quotechar='"')
        numeric_cols = ["SACK", "INT", "FR", "FF", "TD", "SAFETY", "PA", "YDS_AGN", "FPTS"]
        df = self._clean_projection_df(df, numeric_cols=numeric_cols)
        logger.info("Loaded %d DST projections", len(df))
        return df

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _clean_projection_df(
        self, df: pd.DataFrame, numeric_cols: list[str]
    ) -> pd.DataFrame:
        """Common cleanup for projection DataFrames.

        - Strips whitespace/quotes from string columns
        - Parses comma-formatted numbers
        - Drops rows with no player name
        """
        # Clean string columns
        for col in df.select_dtypes(include=["object", "str"]).columns:
            df[col] = df[col].str.strip('"').str.strip()

        # Drop rows where Player is missing or blank
        df = df[df["Player"].notna() & (df["Player"] != "")]
        df = df.reset_index(drop=True)

        # Parse numeric columns (handles commas like "3,904.1")
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].apply(_parse_numeric)

        return df

    def read_all(self) -> dict[str, pd.DataFrame]:
        """Read all five CSV files and return them as a dict.

        Returns:
            dict with keys: 'rankings', 'qb', 'flex', 'k', 'dst'

        Raises:
            IngestionError: if any file cannot be read.
        """
        try:
            return {
                "rankings": self.read_rankings(),
                "qb": self.read_qb_projections(),
                "flex": self.read_flex_projections(),
                "k": self.read_k_projections(),
                "dst": self.read_dst_projections(),
            }
        except Exception as e:
            raise IngestionError(f"Failed to read CSV files: {e}") from e
