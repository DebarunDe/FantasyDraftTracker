"""Draft initialization - creates new draft instances from player data."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from src.draft_manager.config import (
    DEFAULT_ROSTER_SLOTS,
    DEFAULT_SCORING_FORMAT,
    PROCESSED_DATA_DIR,
)
from src.draft_manager.draft_state import DraftState, LeagueConfig

logger = logging.getLogger(__name__)


class DraftInitializer:
    """Handles creation of new draft instances."""

    VALID_SCORING_FORMATS = {"standard", "half_ppr", "full_ppr"}
    REQUIRED_ROSTER_POSITIONS = {"QB", "RB", "WR", "TE", "FLEX", "BENCH"}

    def __init__(self, processed_data_dir: Optional[Path] = None):
        self.processed_data_dir = processed_data_dir or PROCESSED_DATA_DIR

    def create_draft(
        self,
        league_size: int,
        scoring_format: str,
        roster_slots: Dict[str, int],
        team_names: List[str],
        human_team_id: int = 0,
        draft_mode: str = "simulation",
        data_year: int = 2025,
    ) -> DraftState:
        """
        Create a new draft instance.

        Args:
            league_size: Number of teams (2-20)
            scoring_format: "standard", "half_ppr", or "full_ppr"
            roster_slots: Position limits {"QB": 1, "RB": 2, ...}
            team_names: List of team names (must match league_size)
            human_team_id: Index of human-controlled team (default: 0)
            draft_mode: "simulation" or "manual_tracker"
            data_year: Which season's projections to use

        Returns:
            DraftState ready to begin drafting
        """
        self._validate_inputs(
            league_size, scoring_format, roster_slots, team_names, human_team_id
        )

        player_data = self._load_player_data(data_year)

        league_config = LeagueConfig(
            league_id=f"league_{league_size}team",
            league_size=league_size,
            scoring_format=scoring_format,
            draft_type="snake",
            draft_mode=draft_mode,
            data_year=data_year,
            roster_slots=roster_slots,
        )

        draft_state = DraftState.create_new(
            league_config=league_config,
            team_names=team_names,
            human_team_id=human_team_id,
            player_data=player_data,
        )

        logger.info(
            "Created draft %s: %d teams, %s scoring, %d players available",
            draft_state.draft_id,
            league_size,
            scoring_format,
            len(draft_state.available_players),
        )

        return draft_state

    def _validate_inputs(
        self,
        league_size: int,
        scoring_format: str,
        roster_slots: Dict[str, int],
        team_names: List[str],
        human_team_id: int,
    ):
        """Validate draft configuration inputs."""
        if league_size < 2 or league_size > 20 or league_size % 2 != 0:
            raise ValueError(
                "League size must be an even number between 2 and 20"
            )

        if len(team_names) != league_size:
            raise ValueError(
                f"Number of team names ({len(team_names)}) "
                f"must match league size ({league_size})"
            )

        if human_team_id < 0 or human_team_id >= league_size:
            raise ValueError(
                f"Human team ID ({human_team_id}) "
                f"must be between 0 and {league_size - 1}"
            )

        if scoring_format not in self.VALID_SCORING_FORMATS:
            raise ValueError(
                f"Invalid scoring format '{scoring_format}'. "
                f"Must be one of: {self.VALID_SCORING_FORMATS}"
            )

        if not self.REQUIRED_ROSTER_POSITIONS.issubset(roster_slots.keys()):
            missing = self.REQUIRED_ROSTER_POSITIONS - set(roster_slots.keys())
            raise ValueError(f"Roster slots missing required positions: {missing}")

    def _load_player_data(self, data_year: int) -> Dict[str, Dict]:
        """Load player projections from processed JSON."""
        year_file = self.processed_data_dir / f"players_{data_year}.json"

        if not year_file.exists():
            raise FileNotFoundError(
                f"No player data found for {data_year}. "
                "Run data pipeline first: "
                "python -m src.data_pipeline.run_update"
            )

        with open(year_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        try:
            player_data = {
                player["player_id"]: player for player in data["players"]
            }
        except KeyError as e:
            raise ValueError(
                f"Malformed player data file for {data_year}: missing key {e}. "
                "Re-run data pipeline to regenerate."
            ) from e

        logger.info("Loaded %d players for %d season", len(player_data), data_year)
        return player_data

    @staticmethod
    def get_default_roster_slots() -> Dict[str, int]:
        """Get standard roster configuration."""
        return dict(DEFAULT_ROSTER_SLOTS)

    @staticmethod
    def get_default_scoring_format() -> str:
        """Get default scoring format."""
        return DEFAULT_SCORING_FORMAT
