import os
from pathlib import Path

# Base project directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Data directories
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
DRAFTS_DIR = PROJECT_ROOT / "data" / "drafts"

# Default roster configuration
DEFAULT_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "DST": 1,
    "K": 1,
    "BENCH": 6,
}

# Default league settings
DEFAULT_LEAGUE_SIZE = 12
DEFAULT_SCORING_FORMAT = "half_ppr"
DEFAULT_DRAFT_TYPE = "snake"

# Player DB connection settings (DistributedDatabaseSystem integration)
PLAYER_DB_URL = os.getenv("PLAYER_DB_URL", "http://localhost:8090")
PLAYER_DB_API_KEY = os.getenv("PLAYER_DB_API_KEY", "fantasy-draft-key")
USE_PLAYER_DB = os.getenv("USE_PLAYER_DB", "false").lower() == "true"
