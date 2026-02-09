"""Roster validation and slot assignment logic."""

from typing import Dict, List, Tuple

from src.draft_manager.draft_state import LeagueConfig, TeamRoster


class RosterValidator:
    """Validates roster construction and slot assignments."""

    FLEX_ELIGIBLE_POSITIONS = {"RB", "WR", "TE"}

    def __init__(self, league_config: LeagueConfig):
        self.league_config = league_config

    def determine_roster_slot(self, team: TeamRoster, player_position: str) -> str:
        """
        Determine which roster slot a player should fill.

        Priority: specific position -> FLEX (if eligible) -> BENCH.
        """
        current_count = team.get_roster_count(player_position)
        position_limit = self.league_config.get_position_limit(player_position)

        if current_count < position_limit:
            return player_position

        if player_position in self.FLEX_ELIGIBLE_POSITIONS:
            flex_count = team.get_roster_count("FLEX")
            flex_limit = self.league_config.get_position_limit("FLEX")
            if flex_count < flex_limit:
                return "FLEX"

        return "BENCH"

    def validate_final_roster(self, team: TeamRoster) -> Tuple[bool, List[str]]:
        """
        Validate that a completed roster meets all requirements.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        for position, required_count in self.league_config.roster_slots.items():
            actual_count = team.get_roster_count(position)

            if actual_count < required_count:
                errors.append(
                    f"Missing {required_count - actual_count} {position} "
                    f"(have {actual_count}, need {required_count})"
                )
            elif actual_count > required_count:
                errors.append(
                    f"Too many {position} players "
                    f"(have {actual_count}, max {required_count})"
                )

        return (len(errors) == 0, errors)

    def get_roster_summary(self, team: TeamRoster) -> Dict[str, Dict]:
        """Generate summary of team's roster status."""
        summary = {}

        for position, required in self.league_config.roster_slots.items():
            filled = team.get_roster_count(position)
            summary[position] = {
                "filled": filled,
                "required": required,
                "remaining": max(0, required - filled),
            }

        return summary
