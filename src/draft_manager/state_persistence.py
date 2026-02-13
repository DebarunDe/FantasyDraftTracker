"""State persistence - save and load draft state to/from JSON files."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from src.draft_manager.config import DRAFTS_DIR
from src.draft_manager.draft_state import DraftState, LeagueConfig, Pick, TeamRoster

logger = logging.getLogger(__name__)


class StatePersistence:
    """Handles saving and loading draft state to/from JSON files."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or DRAFTS_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_draft(self, draft_state: DraftState) -> Path:
        """Save draft state to JSON file.

        Args:
            draft_state: The complete draft state to persist.

        Returns:
            Path to the saved file.
        """
        filename = f"draft_{draft_state.draft_id}.json"
        filepath = self.storage_dir / filename

        state_dict = self._draft_state_to_dict(draft_state)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state_dict, f, indent=2)

        self._update_active_link(filepath)

        logger.info(
            "Saved draft %s (pick %d, round %d) to %s",
            draft_state.draft_id,
            draft_state.current_pick,
            draft_state.current_round,
            filepath,
        )

        return filepath

    def load_draft(self, draft_id: str) -> Optional[DraftState]:
        """Load draft state from JSON file.

        Args:
            draft_id: UUID of the draft to load.

        Returns:
            DraftState if found, None otherwise.
        """
        filename = f"draft_{draft_id}.json"
        filepath = self.storage_dir / filename

        if not filepath.exists():
            logger.warning("Draft file not found: %s", filepath)
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                state_dict = json.load(f)
        except json.JSONDecodeError as e:
            logger.warning("Corrupt draft file %s: %s", filepath, e)
            return None

        logger.info("Loaded draft %s from %s", draft_id, filepath)
        return self._dict_to_draft_state(state_dict)

    def load_active_draft(self) -> Optional[DraftState]:
        """Load the currently active draft.

        Returns:
            DraftState if an active draft exists, None otherwise.
        """
        active_link = self.storage_dir / "active_draft.json"

        if not active_link.exists() and not active_link.is_symlink():
            return None

        if active_link.is_symlink():
            actual_file = active_link.resolve()
            if not actual_file.exists():
                logger.warning(
                    "Active draft symlink points to missing file: %s", actual_file
                )
                return None

            with open(actual_file, "r", encoding="utf-8") as f:
                state_dict = json.load(f)

            logger.info("Loaded active draft from %s", actual_file)
            return self._dict_to_draft_state(state_dict)

        return None

    def list_saved_drafts(self) -> List[Dict]:
        """List all saved drafts with metadata.

        Returns:
            List of dicts with draft_id, start_time, is_complete,
            current_round, current_pick, league_size, scoring_format.
            Sorted by start_time descending (most recent first).
        """
        drafts = []

        for filepath in self.storage_dir.glob("draft_*.json"):
            if filepath.name == "active_draft.json":
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                drafts.append(
                    {
                        "draft_id": data["draft_id"],
                        "start_time": data["draft_start_time"],
                        "is_complete": data.get("is_complete", False),
                        "current_round": data.get("current_round", 1),
                        "current_pick": data.get("current_pick", 1),
                        "league_size": data.get("league_config", {}).get(
                            "league_size", 0
                        ),
                        "scoring_format": data.get("league_config", {}).get(
                            "scoring_format", ""
                        ),
                    }
                )
            except (json.JSONDecodeError, OSError, KeyError) as e:
                logger.warning("Skipping corrupt draft file %s: %s", filepath, e)
                continue

        return sorted(drafts, key=lambda x: x["start_time"], reverse=True)

    def delete_draft(self, draft_id: str) -> bool:
        """Delete a saved draft file.

        Args:
            draft_id: UUID of the draft to delete.

        Returns:
            True if deleted, False if not found.
        """
        filename = f"draft_{draft_id}.json"
        filepath = self.storage_dir / filename

        if not filepath.exists():
            return False

        # If this is the active draft, remove the symlink
        active_link = self.storage_dir / "active_draft.json"
        if active_link.is_symlink():
            target = active_link.resolve()
            if target == filepath.resolve():
                active_link.unlink()

        filepath.unlink()
        logger.info("Deleted draft %s", draft_id)
        return True

    def _draft_state_to_dict(self, state: DraftState) -> Dict:
        """Convert DraftState to JSON-serializable dict."""
        return {
            "draft_id": state.draft_id,
            "league_config": {
                "league_id": state.league_config.league_id,
                "league_size": state.league_config.league_size,
                "scoring_format": state.league_config.scoring_format,
                "draft_type": state.league_config.draft_type,
                "draft_mode": state.league_config.draft_mode,
                "data_year": state.league_config.data_year,
                "roster_slots": state.league_config.roster_slots,
            },
            "draft_start_time": state.draft_start_time,
            "current_pick": state.current_pick,
            "current_round": state.current_round,
            "current_team_id": state.current_team_id,
            "draft_order": state.draft_order,
            "teams": [
                {
                    "team_id": team.team_id,
                    "team_name": team.team_name,
                    "is_human": team.is_human,
                    "roster": team.roster,
                    "picks": team.picks,
                }
                for team in state.teams
            ],
            "all_picks": [
                {
                    "pick_number": pick.pick_number,
                    "round": pick.round,
                    "team_id": pick.team_id,
                    "player_id": pick.player_id,
                    "timestamp": pick.timestamp,
                    "slot": pick.slot,
                }
                for pick in state.all_picks
            ],
            "available_players": state.available_players,
            "player_data": state.player_data,
            "is_complete": state.is_complete,
            "completed_at": state.completed_at,
        }

    def _dict_to_draft_state(self, data: Dict) -> DraftState:
        """Reconstruct DraftState from dict."""
        lc = data["league_config"]
        league_config = LeagueConfig(
            league_id=lc["league_id"],
            league_size=lc["league_size"],
            scoring_format=lc["scoring_format"],
            draft_type=lc.get("draft_type", "snake"),
            draft_mode=lc.get("draft_mode", "simulation"),
            data_year=lc.get("data_year", 2025),
            roster_slots=lc["roster_slots"],
        )

        teams = [
            TeamRoster(
                team_id=td["team_id"],
                team_name=td["team_name"],
                is_human=td["is_human"],
                roster=td["roster"],
                picks=td["picks"],
            )
            for td in data["teams"]
        ]

        all_picks = [
            Pick(
                pick_number=pd["pick_number"],
                round=pd["round"],
                team_id=pd["team_id"],
                player_id=pd["player_id"],
                timestamp=pd["timestamp"],
                slot=pd.get("slot"),
            )
            for pd in data["all_picks"]
        ]

        return DraftState(
            draft_id=data["draft_id"],
            league_config=league_config,
            draft_start_time=data["draft_start_time"],
            current_pick=data["current_pick"],
            current_round=data["current_round"],
            current_team_id=data["current_team_id"],
            draft_order=data["draft_order"],
            teams=teams,
            all_picks=all_picks,
            available_players=data["available_players"],
            player_data=data["player_data"],
            is_complete=data.get("is_complete", False),
            completed_at=data.get("completed_at"),
        )

    def _update_active_link(self, filepath: Path):
        """Update symlink to the currently active draft."""
        active_link = self.storage_dir / "active_draft.json"

        if active_link.exists() or active_link.is_symlink():
            active_link.unlink()

        active_link.symlink_to(filepath.name)
