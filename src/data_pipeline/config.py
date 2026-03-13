from pathlib import Path

# Base project directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Scoring system weights (for calculating Standard/Half PPR from Full PPR)
SCORING_FORMATS = {
    "standard": 0.0,  # 0 points per reception
    "half_ppr": 0.5,  # 0.5 points per reception
    "full_ppr": 1.0,  # 1.0 points per reception
}

# VOR baseline calculation weights (per-team multipliers)
# Based on Petersen's pick-100 methodology, adapted for league-size scaling
#
# Formula: baseline_count = per_team_weight * league_size
#
# These weights represent the empirically-derived replacement player for each
# position (FFTradingRoom 15-season analysis, flex-adjusted):
# - QB: QB18 is the effective replacement in 1-QB leagues (BEER+ streaming methodology)
# - RB: RB28 flex-adjusted replacement (2 starters + FLEX share, empirically 28.3)
# - WR: WR41 flex-adjusted replacement (WRs dominate 75% of flex spots historically)
# - TE: TE14 replacement (1 starter + minimal FLEX share)
# - K/DST: minimal depth; streaming-only positions
VOR_PER_TEAM_WEIGHTS = {
    "QB": 1.5,  # QB18: BEER+ streaming-adjusted replacement (above QB12 starter cutoff)
    "RB": 2.33,  # RB28: flex-adjusted empirical replacement (was 3.3/RB40 — too deep)
    "WR": 3.4,  # WR41: flex-dominant replacement (WRs fill ~75% of flex spots)
    "TE": 1.2,  # TE14: just above starter cutoff
    "K": 0.75,  # 1 starter, minimal bench (devalued per research)
    "DST": 0.75,  # 1 starter, minimal bench (devalued per research)
}


def calculate_baseline_count(position: str, league_size: int) -> int:
    """Calculate VOR baseline count for a position based on league size.

    Uses per-team weights calibrated to Petersen's pick-100 methodology.

    Args:
        position: Player position (QB, RB, WR, TE, K, DST).
        league_size: Number of teams in the league.

    Returns:
        Number of players at this position to use as replacement baseline.

    Examples:
        >>> calculate_baseline_count("QB", 12)
        18
        >>> calculate_baseline_count("RB", 10)
        33
        >>> calculate_baseline_count("K", 8)
        6
    """
    weight = VOR_PER_TEAM_WEIGHTS.get(position, 1.0)
    return int(round(weight * league_size))


# FantasyPros CSV file name patterns (use .format(year=YYYY))
FILE_PATTERNS = {
    "rankings": "FantasyPros_{year}_Draft_ALL_Rankings.csv",
    "qb": "FantasyPros_Fantasy_Football_Projections_QB.csv",
    "flex": "FantasyPros_Fantasy_Football_Projections_FLX.csv",
    "k": "FantasyPros_Fantasy_Football_Projections_K.csv",
    "dst": "FantasyPros_Fantasy_Football_Projections_DST.csv",
}

# Column name mappings for files with duplicate headers
QB_COLUMNS = [
    "Player",
    "Team",
    "Pass_Att",
    "Pass_Cmp",
    "Pass_Yds",
    "Pass_TD",
    "Pass_Int",
    "Rush_Att",
    "Rush_Yds",
    "Rush_TD",
    "FL",
    "FPTS",
]

FLEX_COLUMNS = [
    "Player",
    "Team",
    "POS",
    "Rush_Att",
    "Rush_Yds",
    "Rush_TD",
    "Rec",
    "Rec_Yds",
    "Rec_TD",
    "FL",
    "FPTS",
]
