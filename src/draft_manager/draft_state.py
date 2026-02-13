"""Draft state data models - single source of truth for all draft information."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import uuid


@dataclass
class TeamRoster:
    """Represents a single team's roster."""

    team_id: int
    team_name: str
    is_human: bool
    roster: Dict[str, List[str]] = field(default_factory=dict)
    picks: List[str] = field(default_factory=list)

    def get_roster_count(self, position: str) -> int:
        """Get number of players at position."""
        return len(self.roster.get(position, []))

    def add_player(self, player_id: str, slot: str):
        """Add player to roster at the given slot."""
        if slot not in self.roster:
            self.roster[slot] = []
        self.roster[slot].append(player_id)
        self.picks.append(player_id)

    def remove_player(self, player_id: str, slot: str):
        """Remove player from roster at the given slot (for rollback)."""
        if slot in self.roster:
            self.roster[slot].remove(player_id)
        self.picks.remove(player_id)

    def get_total_picks(self) -> int:
        """Total number of picks made."""
        return len(self.picks)


@dataclass
class Pick:
    """Represents a single draft pick."""

    pick_number: int
    round: int
    team_id: int
    player_id: str
    timestamp: str
    slot: Optional[str] = None  # Roster slot assigned (QB, RB, FLEX, BENCH, etc.)

    @classmethod
    def create(
        cls,
        pick_number: int,
        round: int,
        team_id: int,
        player_id: str,
        slot: Optional[str] = None,
    ):
        return cls(
            pick_number=pick_number,
            round=round,
            team_id=team_id,
            player_id=player_id,
            timestamp=datetime.now().isoformat(),
            slot=slot,
        )


@dataclass
class LeagueConfig:
    """League configuration settings."""

    league_id: str
    league_size: int
    scoring_format: str  # "standard", "half_ppr", "full_ppr"
    draft_type: str = "snake"
    draft_mode: str = "simulation"  # "simulation" or "manual_tracker"
    data_year: int = 2025
    roster_slots: Dict[str, int] = field(default_factory=dict)

    def total_rounds(self) -> int:
        """Calculate total number of draft rounds."""
        if not self.roster_slots:
            raise ValueError("roster_slots cannot be empty")
        return sum(self.roster_slots.values())

    def get_position_limit(self, position: str) -> int:
        """Get roster limit for position."""
        return self.roster_slots.get(position, 0)


@dataclass
class DraftState:
    """Complete draft state - single source of truth."""

    draft_id: str
    league_config: LeagueConfig
    draft_start_time: str
    current_pick: int
    current_round: int
    current_team_id: int
    draft_order: List[int]
    teams: List[TeamRoster]
    all_picks: List[Pick]
    available_players: List[str]
    player_data: Dict[str, Dict]
    is_complete: bool = False
    completed_at: Optional[str] = None

    @classmethod
    def create_new(
        cls,
        league_config: LeagueConfig,
        team_names: List[str],
        human_team_id: int,
        player_data: Dict[str, Dict],
    ) -> "DraftState":
        """Factory method to create a new draft."""
        if len(team_names) != league_config.league_size:
            raise ValueError(
                f"team_names length ({len(team_names)}) must match "
                f"league_size ({league_config.league_size})"
            )
        if not 0 <= human_team_id < league_config.league_size:
            raise ValueError(
                f"human_team_id ({human_team_id}) must be in range "
                f"[0, {league_config.league_size})"
            )
        draft_id = str(uuid.uuid4())

        teams = [
            TeamRoster(
                team_id=i,
                team_name=name,
                is_human=(i == human_team_id),
                roster={pos: [] for pos in league_config.roster_slots},
            )
            for i, name in enumerate(team_names)
        ]

        draft_order = list(range(league_config.league_size))
        available_players = list(player_data.keys())

        return cls(
            draft_id=draft_id,
            league_config=league_config,
            draft_start_time=datetime.now().isoformat(),
            current_pick=1,
            current_round=1,
            current_team_id=draft_order[0],
            draft_order=draft_order,
            teams=teams,
            all_picks=[],
            available_players=available_players,
            player_data=player_data,
        )

    def get_current_team(self) -> TeamRoster:
        """Get the team currently on the clock."""
        return self.teams[self.current_team_id]

    def get_team(self, team_id: int) -> TeamRoster:
        """Get specific team by ID."""
        return self.teams[team_id]

    def is_player_available(self, player_id: str) -> bool:
        """Check if player is still available."""
        return player_id in self.available_players

    def get_player_info(self, player_id: str) -> Dict:
        """Get player information."""
        return self.player_data.get(player_id, {})

    def advance_to_next_pick(self):
        """Move to next pick (handles snake draft logic)."""
        if self.is_complete:
            return

        self.current_pick += 1

        # Update round first so team calculation uses correct direction
        self.current_round = (
            (self.current_pick - 1) // self.league_config.league_size
        ) + 1

        if self.league_config.draft_type == "snake":
            picks_in_round = (self.current_pick - 1) % self.league_config.league_size

            if self.current_round % 2 == 1:  # Odd rounds: 0 -> N-1
                team_index = picks_in_round
            else:  # Even rounds: N-1 -> 0
                team_index = self.league_config.league_size - 1 - picks_in_round

            self.current_team_id = self.draft_order[team_index]
        else:  # Linear draft
            team_index = (self.current_pick - 1) % self.league_config.league_size
            self.current_team_id = self.draft_order[team_index]

    def check_if_complete(self) -> bool:
        """Check if draft is complete."""
        total_picks = self.league_config.league_size * self.league_config.total_rounds()
        self.is_complete = self.current_pick > total_picks

        if self.is_complete and not self.completed_at:
            self.completed_at = datetime.now().isoformat()

        return self.is_complete
