"""Draft controller - orchestrates pick flow and state updates."""

import logging
from typing import Dict, List, Optional

from src.draft_manager.draft_rules import DraftRules, ValidationError
from src.draft_manager.draft_state import DraftState, Pick, TeamRoster
from src.draft_manager.roster_validator import RosterValidator

logger = logging.getLogger(__name__)


class DraftController:
    """Main controller for draft orchestration.

    Coordinates between DraftRules (validation), RosterValidator (slot
    assignment), and DraftState (state mutation) to execute picks.
    """

    def __init__(self, draft_state: DraftState):
        self.draft_state = draft_state
        self.rules = DraftRules(draft_state)
        self.validator = RosterValidator(draft_state.league_config)

    def make_pick(self, team_id: int, player_id: str) -> Pick:
        """Validate and execute a draft pick.

        Args:
            team_id: ID of the team making the pick.
            player_id: ID of the player being drafted.

        Returns:
            The Pick record with all details including assigned roster slot.

        Raises:
            ValidationError: If the pick is illegal (wrong turn, player
                already drafted, position full, draft complete, etc.)
        """
        if self.draft_state.is_complete:
            raise ValidationError("Draft is already complete")

        is_valid, error_msg = self.rules.validate_pick(team_id, player_id)
        if not is_valid:
            logger.warning("Invalid pick attempted: %s", error_msg)
            raise ValidationError(error_msg)

        player_info = self.draft_state.get_player_info(player_id)
        team = self.draft_state.get_team(team_id)
        slot = self.validator.determine_roster_slot(team, player_info["position"])

        pick = Pick.create(
            pick_number=self.draft_state.current_pick,
            round=self.draft_state.current_round,
            team_id=team_id,
            player_id=player_id,
            slot=slot,
        )

        team.add_player(player_id, slot)
        self.draft_state.all_picks.append(pick)
        try:
            self.draft_state.available_players.remove(player_id)
        except ValueError:
            team.remove_player(player_id, slot)
            self.draft_state.all_picks.pop()
            raise ValidationError(f"Player {player_id} not in available pool")

        logger.info(
            "Pick %d (Rd %d): Team %d (%s) selects %s (%s) -> %s",
            pick.pick_number,
            pick.round,
            team_id,
            team.team_name,
            player_info["name"],
            player_info["position"],
            slot,
        )

        self.draft_state.advance_to_next_pick()
        self.draft_state.check_if_complete()

        return pick

    @property
    def is_complete(self) -> bool:
        """Whether the draft is finished."""
        return self.draft_state.is_complete

    def get_current_team(self) -> TeamRoster:
        """Get the team currently on the clock."""
        return self.draft_state.get_current_team()

    def get_available_players(self, position: Optional[str] = None) -> List[Dict]:
        """Get list of available player info dicts.

        Args:
            position: If provided, filter to this position only.

        Returns:
            List of player info dicts, ordered by their position in
            the available_players list (which preserves pipeline order).
        """
        players = []
        for pid in self.draft_state.available_players:
            info = self.draft_state.get_player_info(pid)
            if position is None or info.get("position") == position:
                players.append(info)
        return players

    def get_team_roster(self, team_id: int) -> Dict[str, List[Dict]]:
        """Get formatted roster for a team.

        Returns:
            Dict mapping slot name to list of player info dicts.
        """
        team = self.draft_state.get_team(team_id)
        formatted = {}
        for slot, player_ids in team.roster.items():
            formatted[slot] = [
                self.draft_state.get_player_info(pid) for pid in player_ids
            ]
        return formatted

    def get_draft_summary(self) -> Dict:
        """Generate summary of draft results.

        Returns dict with "error" key if draft is not yet complete.
        """
        if not self.draft_state.is_complete:
            return {"error": "Draft not complete"}

        scoring = self.draft_state.league_config.scoring_format

        summary = {
            "draft_id": self.draft_state.draft_id,
            "completed_at": self.draft_state.completed_at,
            "total_picks": len(self.draft_state.all_picks),
            "teams": [],
        }

        for team in self.draft_state.teams:
            team_summary = {
                "team_id": team.team_id,
                "team_name": team.team_name,
                "is_human": team.is_human,
                "roster": self.get_team_roster(team.team_id),
                "projected_points": self._calculate_team_points(team, scoring),
            }
            summary["teams"].append(team_summary)

        return summary

    def _calculate_team_points(
        self, team: TeamRoster, scoring_format: str
    ) -> float:
        """Calculate total projected points for starting lineup (excludes bench)."""
        total_points = 0.0

        for slot, player_ids in team.roster.items():
            if slot == "BENCH":
                continue
            for player_id in player_ids:
                player = self.draft_state.get_player_info(player_id)
                points = player.get("projections", {}).get(scoring_format, 0)
                total_points += points

        return round(total_points, 1)
