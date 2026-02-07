from pathlib import Path

# Base project directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Scoring system weights (for calculating Standard/Half PPR from Full PPR)
SCORING_FORMATS = {
    "standard": 0.0,   # 0 points per reception
    "half_ppr": 0.5,    # 0.5 points per reception
    "full_ppr": 1.0,    # 1.0 points per reception
}

# VOR baseline counts (12-team league)
VOR_BASELINE_COUNTS = {
    "QB": 12,
    "RB": 36,
    "WR": 36,
    "TE": 12,
    "K": 12,
    "DST": 12,
}

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
    "Player", "Team",
    "Pass_Att", "Pass_Cmp", "Pass_Yds", "Pass_TD", "Pass_Int",
    "Rush_Att", "Rush_Yds", "Rush_TD",
    "FL", "FPTS",
]

FLEX_COLUMNS = [
    "Player", "Team", "POS",
    "Rush_Att", "Rush_Yds", "Rush_TD",
    "Rec", "Rec_Yds", "Rec_TD",
    "FL", "FPTS",
]
