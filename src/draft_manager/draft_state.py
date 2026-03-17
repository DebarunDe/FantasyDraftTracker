"""Draft state data models - single source of truth for all draft information."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


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
    pick_clock_seconds: Optional[int] = None  # None = no timer

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
    draft_order: List[List[int]]  # [round_idx][pick_in_round] -> team_id
    teams: List[TeamRoster]
    all_picks: List[Pick]
    available_players: List[str]
    player_data: Dict[str, Dict]
    pick_trades: List[Dict] = field(default_factory=list)  # trade history
    is_complete: bool = False
    completed_at: Optional[str] = None

    @staticmethod
    def _generate_snake_order(league_size: int, total_rounds: int) -> List[List[int]]:
        """Pre-compute the full snake draft order as a 2D list.

        draft_order[round_idx][pick_in_round] = team_id.
        Odd rounds (1, 3, 5, …) go 0→N-1; even rounds go N-1→0.
        """
        order = []
        for rnd in range(1, total_rounds + 1):
            if rnd % 2 == 1:  # odd round: ascending
                order.append(list(range(league_size)))
            else:  # even round: descending
                order.append(list(range(league_size - 1, -1, -1)))
        return order

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
                f"human_team_id ({human_team_id}) must be in range [0, {league_config.league_size})"
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

        draft_order = cls._generate_snake_order(
            league_config.league_size, league_config.total_rounds()
        )
        available_players = list(player_data.keys())

        return cls(
            draft_id=draft_id,
            league_config=league_config,
            draft_start_time=datetime.now().isoformat(),
            current_pick=1,
            current_round=1,
            current_team_id=draft_order[0][0],
            draft_order=draft_order,
            teams=teams,
            all_picks=[],
            available_players=available_players,
            player_data=player_data,
            pick_trades=[],
        )

    def apply_pick_trade(self, from_team_id: int, round_num: int, to_team_id: int) -> None:
        """Transfer a pick from one team to another.

        Finds the first slot in round_num's draft order currently owned by
        from_team_id and reassigns it to to_team_id.

        Raises:
            ValueError: If round_num is out of range or from_team_id has no
                        pick remaining in that round.
        """
        league_size = self.league_config.league_size
        if not 0 <= from_team_id < league_size:
            raise ValueError(f"from_team_id {from_team_id} is out of range [0, {league_size - 1}]")
        if not 0 <= to_team_id < league_size:
            raise ValueError(f"to_team_id {to_team_id} is out of range [0, {league_size - 1}]")
        total_rounds = self.league_config.total_rounds()
        if not 1 <= round_num <= total_rounds:
            raise ValueError(f"round_num {round_num} is out of range [1, {total_rounds}]")

        round_slots = self.draft_order[round_num - 1]
        for i, team_id in enumerate(round_slots):
            if team_id == from_team_id:
                round_slots[i] = to_team_id
                self.pick_trades.append(
                    {
                        "from_team_id": from_team_id,
                        "round": round_num,
                        "to_team_id": to_team_id,
                    }
                )
                return

        raise ValueError(f"Team {from_team_id} does not have a pick in Round {round_num}")

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
        """Move to next pick using the pre-computed draft_order."""
        if self.is_complete:
            return

        self.current_pick += 1

        self.current_round = ((self.current_pick - 1) // self.league_config.league_size) + 1

        round_idx = self.current_round - 1
        picks_in_round = (self.current_pick - 1) % self.league_config.league_size

        # Guard: don't index beyond the draft (check_if_complete handles the
        # is_complete flag; we just need to avoid an IndexError here).
        if round_idx < len(self.draft_order):
            self.current_team_id = self.draft_order[round_idx][picks_in_round]

    def check_if_complete(self) -> bool:
        """Check if draft is complete."""
        total_picks = self.league_config.league_size * self.league_config.total_rounds()
        self.is_complete = self.current_pick > total_picks

        if self.is_complete and not self.completed_at:
            self.completed_at = datetime.now().isoformat()

        return self.is_complete
