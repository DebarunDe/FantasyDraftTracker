# Draft Manager Module Design

## Overview

The Draft Manager is the central orchestrator and single source of truth for draft state. It manages draft initialization, enforces rules, validates picks, maintains state, and coordinates between the simulation engine and user interface.

## Module Purpose

**Primary Goal**: Maintain draft integrity and orchestrate the draft flow from start to finish.

**Key Responsibilities**:
1. Initialize new draft instances with user configuration
2. Maintain current draft state (in-memory + persistent)
3. Enforce all draft rules and roster limits
4. Validate pick legality before execution
5. Update state after each pick (atomic operations)
6. Coordinate between simulation engine and UI
7. Handle draft completion and summary generation

**Design Philosophy**: Centralized state management with clear boundaries and atomic operations.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Draft Manager                            │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Draft Controller                           │ │
│  │         (Main Orchestration Logic)                      │ │
│  │  - Initialize drafts                                    │ │
│  │  - Coordinate pick flow                                 │ │
│  │  - Manage draft lifecycle                               │ │
│  └────────┬────────────────────────────────┬───────────────┘ │
│           │                                │                  │
│           ▼                                ▼                  │
│  ┌──────────────────┐           ┌──────────────────────────┐ │
│  │   Draft State    │           │    Draft Rules           │ │
│  │                  │           │                          │ │
│  │ - Current picks  │           │ - Validate picks         │ │
│  │ - Team rosters   │           │ - Check roster limits    │ │
│  │ - Available pool │           │ - Enforce draft order    │ │
│  │ - Draft config   │◄──────────┤ - Position eligibility   │ │
│  └────────┬─────────┘           └──────────────────────────┘ │
│           │                                                    │
│           ▼                                                    │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │           State Persistence                              │ │
│  │  - Save to JSON after each pick                          │ │
│  │  - Load from JSON on resume                              │ │
│  │  - Validate state integrity                              │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │         Roster Validator                                 │ │
│  │  - Check position limits                                 │ │
│  │  - Validate FLEX eligibility                             │ │
│  │  - Ensure bench space                                    │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

## Module Structure

```
src/draft_manager/
├── __init__.py
├── draft_controller.py    # Main orchestration
├── draft_state.py         # State data model
├── draft_rules.py         # Rule enforcement
├── roster_validator.py    # Roster validation logic
├── state_persistence.py   # Save/load state
├── draft_initializer.py   # New draft creation
└── models.py              # Data classes
```

## Component Details

### 1. Draft State (`draft_state.py`)

**Purpose**: Data model for complete draft state

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import uuid

@dataclass
class TeamRoster:
    """Represents a single team's roster"""
    team_id: int
    team_name: str
    is_human: bool
    roster: Dict[str, List[str]] = field(default_factory=dict)
    # roster = {"QB": ["player_id_1"], "RB": ["player_id_2", "player_id_3"], ...}
    picks: List[str] = field(default_factory=list)
    # picks = ["player_id_1", "player_id_2", ...] (ordered)
    
    def get_roster_count(self, position: str) -> int:
        """Get number of players at position"""
        return len(self.roster.get(position, []))
    
    def add_player(self, player_id: str, position: str):
        """Add player to roster"""
        if position not in self.roster:
            self.roster[position] = []
        self.roster[position].append(player_id)
        self.picks.append(player_id)
    
    def get_total_picks(self) -> int:
        """Total number of picks made"""
        return len(self.picks)


@dataclass
class Pick:
    """Represents a single draft pick"""
    pick_number: int
    round: int
    team_id: int
    player_id: str
    timestamp: str
    
    @classmethod
    def create(cls, pick_number: int, round: int, team_id: int, player_id: str):
        return cls(
            pick_number=pick_number,
            round=round,
            team_id=team_id,
            player_id=player_id,
            timestamp=datetime.now().isoformat()
        )


@dataclass
class LeagueConfig:
    """League configuration settings"""
    league_id: str
    league_size: int
    scoring_format: str  # "standard", "half_ppr", "full_ppr"
    draft_type: str = "snake"
    draft_mode: str = "simulation"  # "simulation" or "manual_tracker"
    data_year: int = 2024  # Which season's projections to use
    roster_slots: Dict[str, int] = field(default_factory=dict)
    # roster_slots = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "DST": 1, "K": 1, "BENCH": 6}
    
    def total_rounds(self) -> int:
        """Calculate total number of draft rounds"""
        return sum(self.roster_slots.values())
    
    def get_position_limit(self, position: str) -> int:
        """Get roster limit for position"""
        return self.roster_slots.get(position, 0)


@dataclass
class DraftState:
    """Complete draft state - single source of truth"""
    draft_id: str
    league_config: LeagueConfig
    draft_start_time: str
    current_pick: int
    current_round: int
    current_team_id: int
    draft_order: List[int]  # Team IDs in draft order
    teams: List[TeamRoster]
    all_picks: List[Pick]
    available_players: List[str]  # List of player IDs
    player_data: Dict[str, Dict]  # player_id -> player info
    is_complete: bool = False
    completed_at: Optional[str] = None
    
    @classmethod
    def create_new(
        cls,
        league_config: LeagueConfig,
        team_names: List[str],
        human_team_id: int,
        player_data: Dict[str, Dict]
    ) -> "DraftState":
        """Factory method to create new draft"""
        draft_id = str(uuid.uuid4())
        
        # Create teams
        teams = [
            TeamRoster(
                team_id=i,
                team_name=name,
                is_human=(i == human_team_id),
                roster={pos: [] for pos in league_config.roster_slots.keys()}
            )
            for i, name in enumerate(team_names)
        ]
        
        # Set up draft order (0, 1, 2, ..., N-1)
        draft_order = list(range(league_config.league_size))
        
        # All players start as available
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
            player_data=player_data
        )
    
    def get_current_team(self) -> TeamRoster:
        """Get the team currently on the clock"""
        return self.teams[self.current_team_id]
    
    def get_team(self, team_id: int) -> TeamRoster:
        """Get specific team by ID"""
        return self.teams[team_id]
    
    def is_player_available(self, player_id: str) -> bool:
        """Check if player is still available"""
        return player_id in self.available_players
    
    def get_player_info(self, player_id: str) -> Dict:
        """Get player information"""
        return self.player_data.get(player_id, {})
    
    def advance_to_next_pick(self):
        """Move to next pick (handles snake draft logic)"""
        self.current_pick += 1
        
        # Calculate next team based on snake draft
        if self.league_config.draft_type == "snake":
            picks_in_round = (self.current_pick - 1) % self.league_config.league_size
            
            if self.current_round % 2 == 1:  # Odd rounds: 0 -> N-1
                team_index = picks_in_round
            else:  # Even rounds: N-1 -> 0
                team_index = self.league_config.league_size - 1 - picks_in_round
            
            self.current_team_id = self.draft_order[team_index]
        else:  # Linear draft (for future support)
            team_index = (self.current_pick - 1) % self.league_config.league_size
            self.current_team_id = self.draft_order[team_index]
        
        # Update round if we've completed a full circuit
        self.current_round = ((self.current_pick - 1) // self.league_config.league_size) + 1
    
    def check_if_complete(self) -> bool:
        """Check if draft is complete"""
        total_picks = self.league_config.league_size * self.league_config.total_rounds()
        self.is_complete = (self.current_pick > total_picks)
        
        if self.is_complete and not self.completed_at:
            self.completed_at = datetime.now().isoformat()
        
        return self.is_complete
```

### 2. Draft Rules (`draft_rules.py`)

**Purpose**: Enforce draft rules and validate picks

```python
from typing import Optional, Tuple
from src.draft_manager.draft_state import DraftState

class ValidationError(Exception):
    """Raised when a pick violates draft rules"""
    pass


class DraftRules:
    """Enforces all draft rules and validation logic"""
    
    def __init__(self, draft_state: DraftState):
        self.draft_state = draft_state
    
    def validate_pick(self, team_id: int, player_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if a pick is legal.
        
        Returns:
            (is_valid, error_message)
            - (True, None) if valid
            - (False, "error message") if invalid
        """
        # Check 1: Is it this team's turn? (Skip in manual tracker mode)
        if self.draft_state.league_config.draft_mode == "simulation":
            if team_id != self.draft_state.current_team_id:
                return False, f"Not team {team_id}'s turn (current: {self.draft_state.current_team_id})"
        # In manual_tracker mode, allow picks from any team (user enters all picks)
        
        # Check 2: Is player available?
        if not self.draft_state.is_player_available(player_id):
            player = self.draft_state.get_player_info(player_id)
            return False, f"{player.get('name', player_id)} has already been drafted"
        
        # Check 3: Does player exist in data?
        player_info = self.draft_state.get_player_info(player_id)
        if not player_info:
            return False, f"Player {player_id} not found in player database"
        
        # Check 4: Position limits (can team draft this position?)
        team = self.draft_state.get_team(team_id)
        position = player_info['position']
        
        position_valid, pos_error = self._validate_position_limit(team, position)
        if not position_valid:
            return False, pos_error
        
        # All checks passed
        return True, None
    
    def _validate_position_limit(
        self,
        team: 'TeamRoster',
        position: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if team can draft another player at this position.
        
        Rules:
        - Must have space at specific position OR bench
        - FLEX can accept RB/WR/TE but only if specific slots full
        """
        roster_slots = self.draft_state.league_config.roster_slots
        
        # Get current count at position
        current_count = team.get_roster_count(position)
        position_limit = roster_slots.get(position, 0)
        
        # Check specific position limit
        if current_count < position_limit:
            return True, None  # Space at specific position
        
        # Check FLEX eligibility
        if position in ["RB", "WR", "TE"]:
            flex_count = team.get_roster_count("FLEX")
            flex_limit = roster_slots.get("FLEX", 0)
            
            if flex_count < flex_limit:
                return True, None  # Can go to FLEX
        
        # Check bench space
        bench_count = team.get_roster_count("BENCH")
        bench_limit = roster_slots.get("BENCH", 0)
        
        if bench_count < bench_limit:
            return True, None  # Can go to bench
        
        # No space anywhere
        return False, (
            f"Cannot draft another {position}. "
            f"Position full ({current_count}/{position_limit}), "
            f"no FLEX space, and bench full ({bench_count}/{bench_limit})"
        )
    
    def enforce_draft_order(self, team_id: int) -> bool:
        """Ensure picks happen in correct order"""
        return team_id == self.draft_state.current_team_id
    
    def is_draft_complete(self) -> bool:
        """Check if all rounds are complete"""
        total_picks = (
            self.draft_state.league_config.league_size * 
            self.draft_state.league_config.total_rounds()
        )
        return len(self.draft_state.all_picks) >= total_picks
```

### 3. Roster Validator (`roster_validator.py`)

**Purpose**: Handle complex roster validation and FLEX slot logic

```python
from typing import Dict, List, Optional
from src.draft_manager.draft_state import TeamRoster, LeagueConfig

class RosterValidator:
    """Validates roster construction and slot assignments"""
    
    FLEX_ELIGIBLE_POSITIONS = {"RB", "WR", "TE"}
    
    def __init__(self, league_config: LeagueConfig):
        self.league_config = league_config
    
    def determine_roster_slot(
        self,
        team: TeamRoster,
        player_position: str
    ) -> str:
        """
        Determine which roster slot a player should fill.
        
        Priority:
        1. Specific position slot (if available)
        2. FLEX slot (if eligible and available)
        3. BENCH slot (if available)
        
        Returns: Slot name ("QB", "RB", "FLEX", "BENCH", etc.)
        """
        # Check specific position slot
        current_count = team.get_roster_count(player_position)
        position_limit = self.league_config.get_position_limit(player_position)
        
        if current_count < position_limit:
            return player_position
        
        # Check FLEX slot (for RB/WR/TE)
        if player_position in self.FLEX_ELIGIBLE_POSITIONS:
            flex_count = team.get_roster_count("FLEX")
            flex_limit = self.league_config.get_position_limit("FLEX")
            
            if flex_count < flex_limit:
                return "FLEX"
        
        # Default to bench
        return "BENCH"
    
    def validate_final_roster(self, team: TeamRoster) -> Tuple[bool, List[str]]:
        """
        Validate that a completed roster meets all requirements.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        # Check each position requirement
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
        """
        Generate summary of team's roster status.
        
        Returns:
            {
                "QB": {"filled": 1, "required": 1, "remaining": 0},
                "RB": {"filled": 2, "required": 2, "remaining": 0},
                ...
            }
        """
        summary = {}
        
        for position, required in self.league_config.roster_slots.items():
            filled = team.get_roster_count(position)
            summary[position] = {
                "filled": filled,
                "required": required,
                "remaining": max(0, required - filled)
            }
        
        return summary
```

### 4. State Persistence (`state_persistence.py`)

**Purpose**: Save and load draft state to/from JSON files

```python
import json
from pathlib import Path
from typing import Optional
from src.draft_manager.draft_state import DraftState, LeagueConfig, TeamRoster, Pick
from src.draft_manager.config import DRAFTS_DIR

class StatePersistence:
    """Handles saving and loading draft state"""
    
    def __init__(self, storage_dir: Path = DRAFTS_DIR):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_draft(self, draft_state: DraftState) -> Path:
        """
        Save draft state to JSON file.
        
        Returns: Path to saved file
        """
        filename = f"draft_{draft_state.draft_id}.json"
        filepath = self.storage_dir / filename
        
        # Convert to dictionary
        state_dict = self._draft_state_to_dict(draft_state)
        
        # Write to file
        with open(filepath, 'w') as f:
            json.dump(state_dict, f, indent=2)
        
        # Update active draft symlink
        self._update_active_link(filepath)
        
        return filepath
    
    def load_draft(self, draft_id: str) -> Optional[DraftState]:
        """
        Load draft state from JSON file.
        
        Returns: DraftState or None if not found
        """
        filename = f"draft_{draft_id}.json"
        filepath = self.storage_dir / filename
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r') as f:
            state_dict = json.load(f)
        
        # Reconstruct DraftState from dictionary
        return self._dict_to_draft_state(state_dict)
    
    def load_active_draft(self) -> Optional[DraftState]:
        """Load the currently active draft"""
        active_link = self.storage_dir / "active_draft.json"
        
        if not active_link.exists():
            return None
        
        # Read symlink to get actual file
        if active_link.is_symlink():
            actual_file = active_link.resolve()
            with open(actual_file, 'r') as f:
                state_dict = json.load(f)
            return self._dict_to_draft_state(state_dict)
        
        return None
    
    def list_saved_drafts(self) -> List[Dict]:
        """
        List all saved drafts with metadata.
        
        Returns: List of {draft_id, start_time, is_complete}
        """
        drafts = []
        
        for filepath in self.storage_dir.glob("draft_*.json"):
            if filepath.name == "active_draft.json":
                continue
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            drafts.append({
                "draft_id": data["draft_id"],
                "start_time": data["draft_start_time"],
                "is_complete": data.get("is_complete", False),
                "current_round": data.get("current_round", 1)
            })
        
        return sorted(drafts, key=lambda x: x["start_time"], reverse=True)
    
    def _draft_state_to_dict(self, state: DraftState) -> Dict:
        """Convert DraftState to JSON-serializable dict"""
        return {
            "draft_id": state.draft_id,
            "league_config": {
                "league_id": state.league_config.league_id,
                "league_size": state.league_config.league_size,
                "scoring_format": state.league_config.scoring_format,
                "draft_type": state.league_config.draft_type,
                "roster_slots": state.league_config.roster_slots
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
                    "picks": team.picks
                }
                for team in state.teams
            ],
            "all_picks": [
                {
                    "pick_number": pick.pick_number,
                    "round": pick.round,
                    "team_id": pick.team_id,
                    "player_id": pick.player_id,
                    "timestamp": pick.timestamp
                }
                for pick in state.all_picks
            ],
            "available_players": state.available_players,
            "player_data": state.player_data,
            "is_complete": state.is_complete,
            "completed_at": state.completed_at
        }
    
    def _dict_to_draft_state(self, data: Dict) -> DraftState:
        """Reconstruct DraftState from dict"""
        # Reconstruct league config
        league_config = LeagueConfig(**data["league_config"])
        
        # Reconstruct teams
        teams = [
            TeamRoster(
                team_id=team_data["team_id"],
                team_name=team_data["team_name"],
                is_human=team_data["is_human"],
                roster=team_data["roster"],
                picks=team_data["picks"]
            )
            for team_data in data["teams"]
        ]
        
        # Reconstruct picks
        all_picks = [
            Pick(**pick_data)
            for pick_data in data["all_picks"]
        ]
        
        # Reconstruct full state
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
            completed_at=data.get("completed_at")
        )
    
    def _update_active_link(self, filepath: Path):
        """Update symlink to active draft"""
        active_link = self.storage_dir / "active_draft.json"
        
        # Remove old symlink if exists
        if active_link.exists() or active_link.is_symlink():
            active_link.unlink()
        
        # Create new symlink (relative path)
        active_link.symlink_to(filepath.name)
```

### 5. Draft Controller (`draft_controller.py`)

**Purpose**: Main orchestration logic for draft flow

```python
from typing import Optional, List, Dict
import logging
from src.draft_manager.draft_state import DraftState, LeagueConfig, Pick
from src.draft_manager.draft_rules import DraftRules, ValidationError
from src.draft_manager.roster_validator import RosterValidator
from src.draft_manager.state_persistence import StatePersistence
from src.simulation_engine.pick_recommender import PickRecommender
from src.simulation_engine.computer_drafter import ComputerDrafter

logger = logging.getLogger(__name__)


class DraftController:
    """Main controller for draft orchestration"""
    
    def __init__(
        self,
        draft_state: DraftState,
        pick_recommender: PickRecommender,
        computer_drafter: ComputerDrafter
    ):
        self.draft_state = draft_state
        self.rules = DraftRules(draft_state)
        self.validator = RosterValidator(draft_state.league_config)
        self.persistence = StatePersistence()
        self.recommender = pick_recommender
        self.computer = computer_drafter
    
    def make_pick(self, team_id: int, player_id: str) -> bool:
        """
        Execute a draft pick.
        
        Works in both modes:
        - Simulation mode: Validates it's the correct team's turn
        - Manual tracker mode: Allows any team to pick (for manual entry)
        
        Process:
        1. Validate pick
        2. Update state (atomic)
        3. Persist state
        4. Recalculate VOR (happens in simulation engine)
        
        Returns: True if successful, raises ValidationError if not
        """
        # Validate pick
        is_valid, error_msg = self.rules.validate_pick(team_id, player_id)
        if not is_valid:
            logger.warning(f"Invalid pick attempted: {error_msg}")
            raise ValidationError(error_msg)
        
        # Get player info
        player_info = self.draft_state.get_player_info(player_id)
        
        # Determine roster slot
        team = self.draft_state.get_team(team_id)
        slot = self.validator.determine_roster_slot(team, player_info['position'])
        
        # Update state (atomic operation)
        self._update_draft_state(team_id, player_id, slot)
        
        # Persist to disk
        self.persistence.save_draft(self.draft_state)
        
        logger.info(
            f"Pick {self.draft_state.current_pick}: "
            f"Team {team_id} selects {player_info['name']} ({player_info['position']})"
        )
        
        return True
    
    def _update_draft_state(self, team_id: int, player_id: str, slot: str):
        """Atomic state update"""
        # Create pick record
        pick = Pick.create(
            pick_number=self.draft_state.current_pick,
            round=self.draft_state.current_round,
            team_id=team_id,
            player_id=player_id
        )
        
        # Update team roster
        team = self.draft_state.get_team(team_id)
        team.add_player(player_id, slot)
        
        # Update global state
        self.draft_state.all_picks.append(pick)
        self.draft_state.available_players.remove(player_id)
        
        # Advance to next pick
        self.draft_state.advance_to_next_pick()
        
        # Check if draft is complete
        self.draft_state.check_if_complete()
    
    def get_recommendation(self, num_recommendations: int = 5) -> List:
        """Get pick recommendations for current team"""
        current_team = self.draft_state.get_current_team()
        
        if not current_team.is_human:
            raise ValueError("Cannot get recommendations for computer team")
        
        # Get available players as list of dicts
        available = [
            self.draft_state.get_player_info(pid)
            for pid in self.draft_state.available_players
        ]
        
        # Get recommendations from simulation engine
        recommendations = self.recommender.recommend_picks(
            draft_state=self._serialize_for_simulation(),
            available_players=available,
            num_recommendations=num_recommendations
        )
        
        return recommendations
    
    def get_computer_pick(self) -> str:
        """Get computer-generated pick for current team"""
        current_team = self.draft_state.get_current_team()
        
        if current_team.is_human:
            raise ValueError("Cannot get computer pick for human team")
        
        # Get available players
        available = [
            self.draft_state.get_player_info(pid)
            for pid in self.draft_state.available_players
        ]
        
        # Get computer pick
        pick = self.computer.make_pick(
            draft_state=self._serialize_for_simulation(),
            available_players=available,
            team_id=current_team.team_id
        )
        
        return pick
    
    def _serialize_for_simulation(self) -> Dict:
        """Convert DraftState to dict for simulation engine"""
        return {
            "draft_id": self.draft_state.draft_id,
            "league_config": {
                "league_size": self.draft_state.league_config.league_size,
                "scoring_format": self.draft_state.league_config.scoring_format,
                "roster_slots": self.draft_state.league_config.roster_slots
            },
            "current_round": self.draft_state.current_round,
            "current_pick": self.draft_state.current_pick,
            "current_team": self.draft_state.current_team_id,
            "teams": [
                {
                    "team_id": team.team_id,
                    "roster": team.roster,
                    "picks": team.picks
                }
                for team in self.draft_state.teams
            ],
            "all_picks": [
                {"player_id": pick.player_id, "team_id": pick.team_id}
                for pick in self.draft_state.all_picks
            ]
        }
    
    def get_draft_summary(self) -> Dict:
        """Generate summary of draft results"""
        if not self.draft_state.is_complete:
            return {"error": "Draft not complete"}
        
        summary = {
            "draft_id": self.draft_state.draft_id,
            "completed_at": self.draft_state.completed_at,
            "teams": []
        }
        
        for team in self.draft_state.teams:
            team_summary = {
                "team_id": team.team_id,
                "team_name": team.team_name,
                "roster": self._format_roster(team),
                "projected_points": self._calculate_team_points(team)
            }
            summary["teams"].append(team_summary)
        
        return summary
    
    def _format_roster(self, team: 'TeamRoster') -> Dict:
        """Format team roster for display"""
        formatted = {}
        
        for position, player_ids in team.roster.items():
            formatted[position] = [
                self.draft_state.get_player_info(pid)
                for pid in player_ids
            ]
        
        return formatted
    
    def _calculate_team_points(self, team: 'TeamRoster') -> float:
        """Calculate total projected points for team"""
        scoring = self.draft_state.league_config.scoring_format
        total_points = 0.0
        
        for position, player_ids in team.roster.items():
            if position == "BENCH":
                continue  # Don't count bench
            
            for player_id in player_ids:
                player = self.draft_state.get_player_info(player_id)
                points = player.get("projections", {}).get(scoring, 0)
                total_points += points
        
        return round(total_points, 1)
```

### 6. Draft Initializer (`draft_initializer.py`)

**Purpose**: Create new draft instances

```python
from typing import List, Dict
from pathlib import Path
import json
from src.draft_manager.draft_state import DraftState, LeagueConfig
from src.data_pipeline.loader import DataLoader
from src.draft_manager.config import PROCESSED_DATA_DIR

class DraftInitializer:
    """Handles creation of new draft instances"""
    
    def __init__(self):
        self.data_loader = DataLoader(PROCESSED_DATA_DIR)
    
    def create_draft(
        self,
        league_size: int,
        scoring_format: str,
        roster_slots: Dict[str, int],
        team_names: List[str],
        human_team_id: int = 0
    ) -> DraftState:
        """
        Create a new draft instance.
        
        Args:
            league_size: Number of teams (e.g., 12)
            scoring_format: "standard", "half_ppr", or "full_ppr"
            roster_slots: Position limits {"QB": 1, "RB": 2, ...}
            team_names: List of team names
            human_team_id: Index of human team (default: 0)
        
        Returns:
            DraftState ready to begin drafting
        """
        # Validate inputs
        self._validate_inputs(league_size, team_names, human_team_id, roster_slots)
        
        # Load player data
        player_data = self._load_player_data()
        
        # Create league config
        league_config = LeagueConfig(
            league_id=f"league_{league_size}team",
            league_size=league_size,
            scoring_format=scoring_format,
            draft_type="snake",
            roster_slots=roster_slots
        )
        
        # Create draft state
        draft_state = DraftState.create_new(
            league_config=league_config,
            team_names=team_names,
            human_team_id=human_team_id,
            player_data=player_data
        )
        
        return draft_state
    
    def _validate_inputs(
        self,
        league_size: int,
        team_names: List[str],
        human_team_id: int,
        roster_slots: Dict[str, int]
    ):
        """Validate draft configuration inputs"""
        if league_size < 2 or league_size > 20:
            raise ValueError("League size must be between 2 and 20")
        
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
        
        required_positions = {"QB", "RB", "WR", "TE", "FLEX", "BENCH"}
        if not required_positions.issubset(roster_slots.keys()):
            raise ValueError(
                f"Roster slots must include: {required_positions}"
            )
    
    def _load_player_data(self) -> Dict[str, Dict]:
        """Load latest player projections from data pipeline"""
        # Load from processed data
        latest_file = PROCESSED_DATA_DIR / "players_latest.json"
        
        if not latest_file.exists():
            raise FileNotFoundError(
                "No player data found. Run data pipeline first:\n"
                "python -m src.data_pipeline.run_daily_update"
            )
        
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        # Convert list to dict keyed by player_id
        player_data = {
            player['player_id']: player
            for player in data['players']
        }
        
        return player_data
    
    @staticmethod
    def get_default_roster_slots() -> Dict[str, int]:
        """Get standard roster configuration"""
        return {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 1,  # RB/WR/TE
            "DST": 1,
            "K": 1,
            "BENCH": 6
        }
```

## Usage Examples

### 1. Creating a New Draft

```python
from src.draft_manager.draft_initializer import DraftInitializer
from src.draft_manager.draft_controller import DraftController
from src.simulation_engine import PickRecommender, ComputerDrafter

# Initialize draft
initializer = DraftInitializer()

team_names = [
    "User Team",  # Human team (index 0)
    "Computer 1",
    "Computer 2",
    # ... up to 12 teams
]

draft_state = initializer.create_draft(
    league_size=12,
    scoring_format="half_ppr",
    roster_slots=initializer.get_default_roster_slots(),
    team_names=team_names,
    human_team_id=0
)

# Create controller
controller = DraftController(
    draft_state=draft_state,
    pick_recommender=PickRecommender(...),
    computer_drafter=ComputerDrafter(...)
)
```

### 2. Making Picks

```python
# Human pick
try:
    controller.make_pick(team_id=0, player_id="cmccaffrey_rb_sf")
    print("Pick successful!")
except ValidationError as e:
    print(f"Invalid pick: {e}")

# Computer pick
if not draft_state.get_current_team().is_human:
    player_id = controller.get_computer_pick()
    controller.make_pick(draft_state.current_team_id, player_id)
```

### 3. Getting Recommendations

```python
if draft_state.get_current_team().is_human:
    recommendations = controller.get_recommendation(num_recommendations=5)
    
    for rec in recommendations:
        print(f"{rec.rank}. {rec.player_name} ({rec.position})")
        print(f"   {rec.reasoning}")
```

### 4. Saving and Loading

```python
from src.draft_manager.state_persistence import StatePersistence

persistence = StatePersistence()

# Save current draft
persistence.save_draft(draft_state)

# Load saved draft
loaded_state = persistence.load_draft(draft_id="abc-123")

# Resume active draft
active_state = persistence.load_active_draft()
```

## Testing Strategy

### Unit Tests

```python
def test_snake_draft_order():
    """Test snake draft order calculation"""
    state = create_test_draft_state(league_size=4)
    
    # Round 1: 0, 1, 2, 3
    assert state.current_team_id == 0
    state.advance_to_next_pick()
    assert state.current_team_id == 1
    state.advance_to_next_pick()
    assert state.current_team_id == 2
    state.advance_to_next_pick()
    assert state.current_team_id == 3
    
    # Round 2: 3, 2, 1, 0 (snake back)
    state.advance_to_next_pick()
    assert state.current_team_id == 3
    assert state.current_round == 2


def test_position_validation():
    """Test roster position limits"""
    rules = DraftRules(draft_state)
    team = draft_state.get_team(0)
    
    # Fill RB slots
    team.roster["RB"] = ["rb1", "rb2"]
    
    # Should allow RB to FLEX
    is_valid, _ = rules._validate_position_limit(team, "RB")
    assert is_valid
    
    # Fill FLEX and BENCH
    team.roster["FLEX"] = ["rb3"]
    team.roster["BENCH"] = ["rb4", "rb5", "rb6", "rb7", "rb8", "rb9"]
    
    # Should not allow another RB
    is_valid, error = rules._validate_position_limit(team, "RB")
    assert not is_valid
    assert "full" in error.lower()
```

### Integration Tests

```python
def test_complete_draft_flow():
    """Test full draft from start to finish"""
    # Create draft
    initializer = DraftInitializer()
    state = initializer.create_draft(...)
    controller = DraftController(state, ...)
    
    # Draft all rounds
    while not state.is_complete:
        current_team = state.get_current_team()
        
        if current_team.is_human:
            # Simulate human picking best available
            recs = controller.get_recommendation(1)
            player_id = recs[0].player_id
        else:
            player_id = controller.get_computer_pick()
        
        controller.make_pick(state.current_team_id, player_id)
    
    # Verify completion
    assert state.is_complete
    assert len(state.all_picks) == state.league_config.league_size * 15
    
    # Verify all rosters complete
    for team in state.teams:
        assert len(team.picks) == 15
```

## Future Enhancements

1. **Undo/Redo Picks**: Allow reverting mistaken picks
2. **Draft Timer**: Add pick time limits
3. **Trade During Draft**: Allow pre-draft trades
4. **Keeper/Dynasty Support**: Handle keeper selections
5. **Auction Draft**: Support auction format
6. **Multi-User**: Support concurrent users in same draft
7. **Draft Analytics**: Track pick value, reaches, steals

---

## Document Version
- **Version**: 1.0
- **Last Updated**: 2024-08-15
- **Status**: Approved for MVP Development
