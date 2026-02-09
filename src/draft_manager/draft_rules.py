"""Draft rule enforcement and pick validation."""

from typing import Optional, Tuple

from src.draft_manager.draft_state import DraftState, TeamRoster


class ValidationError(Exception):
    """Raised when a pick violates draft rules."""

    pass


class DraftRules:
    """Enforces all draft rules and validation logic."""

    def __init__(self, draft_state: DraftState):
        self.draft_state = draft_state

    def validate_pick(
        self, team_id: int, player_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a pick is legal.

        Returns:
            (is_valid, error_message) - (True, None) if valid
        """
        # Check 1: Is it this team's turn? (Skip in manual tracker mode)
        if self.draft_state.league_config.draft_mode == "simulation":
            if team_id != self.draft_state.current_team_id:
                return (
                    False,
                    f"Not team {team_id}'s turn "
                    f"(current: {self.draft_state.current_team_id})",
                )

        # Check 2: Does player exist in data?
        player_info = self.draft_state.get_player_info(player_id)
        if not player_info:
            return False, f"Player {player_id} not found in player database"

        # Check 3: Is player available?
        if not self.draft_state.is_player_available(player_id):
            return (
                False,
                f"{player_info.get('name', player_id)} has already been drafted",
            )

        # Check 4: Position limits
        team = self.draft_state.get_team(team_id)
        position = player_info.get("position")
        if not position:
            return False, f"Player {player_id} has no position defined"

        position_valid, pos_error = self._validate_position_limit(team, position)
        if not position_valid:
            return False, pos_error

        return True, None

    def _validate_position_limit(
        self, team: TeamRoster, position: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if team can draft another player at this position.

        Priority: specific position slot -> FLEX slot -> BENCH slot.
        """
        roster_slots = self.draft_state.league_config.roster_slots

        current_count = team.get_roster_count(position)
        position_limit = roster_slots.get(position, 0)

        if current_count < position_limit:
            return True, None

        # Check FLEX eligibility (RB/WR/TE can fill FLEX)
        if position in ("RB", "WR", "TE"):
            flex_count = team.get_roster_count("FLEX")
            flex_limit = roster_slots.get("FLEX", 0)
            if flex_count < flex_limit:
                return True, None

        # Check bench space
        bench_count = team.get_roster_count("BENCH")
        bench_limit = roster_slots.get("BENCH", 0)
        if bench_count < bench_limit:
            return True, None

        return False, (
            f"Cannot draft another {position}. "
            f"Position full ({current_count}/{position_limit}), "
            f"no FLEX space, and bench full ({bench_count}/{bench_limit})"
        )

    def is_draft_complete(self) -> bool:
        """Check if all rounds are complete."""
        total_picks = (
            self.draft_state.league_config.league_size
            * self.draft_state.league_config.total_rounds()
        )
        return len(self.draft_state.all_picks) >= total_picks
