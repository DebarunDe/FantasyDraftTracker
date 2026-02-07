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
