# Fantasy Football Draft Simulator - System Architecture

## Overview

A modular monolith CLI application for simulating fantasy football drafts with AI-powered pick recommendations and computer opponents. The system uses Monte Carlo simulations and Value Over Replacement (VOR) calculations to provide intelligent draft assistance.

## Design Principles

1. **Modular Monolith**: Clear separation of concerns with well-defined module boundaries
2. **Single User MVP**: Optimized for local execution, single concurrent draft
3. **Dual Mode Support**: Simulation mode (vs AI) and Manual Draft Tracker mode
4. **Static Data During Draft**: Player projections locked at draft start (per season/year)
5. **Stateful Draft Manager**: Centralized state management with file persistence
6. **Stateless Simulation Engine**: Pure functions for recommendations

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Interface                         │
│                    (User Interaction)                        │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      Draft Manager                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Draft State (In-Memory + File Persistence)           │  │
│  │  - Current picks, rosters, available players         │  │
│  │  - League configuration, draft order                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Draft Controller                                      │  │
│  │  - Orchestrates draft flow                           │  │
│  │  - Validates picks, updates state                    │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────┬────────────────────────────┬──────────────────┘
             │                            │
             ▼                            ▼
┌─────────────────────────┐  ┌──────────────────────────────┐
│   Simulation Engine     │  │    Data Pipeline             │
│                         │  │                              │
│ - Monte Carlo Simulator │  │ - CSV Ingestion              │
│ - VOR Calculator        │  │ - Data Cleaning              │
│ - Pick Recommender      │  │ - Baseline VOR Calculation   │
│ - Computer Drafter      │  │ - Data Transformation        │
└─────────────────────────┘  └──────────────────────────────┘
             │                            │
             │                            ▼
             │               ┌──────────────────────────────┐
             │               │   File Storage (data/)       │
             └──────────────►│  - Raw CSVs                  │
                             │  - Processed player data     │
                             │  - Saved draft states        │
                             └──────────────────────────────┘
```

## Data Flow

### 1. Pre-Draft: Data Preparation (Seasonal/On-Demand)
```
FantasyPros Rankings CSV → Data Pipeline → Clean & Transform → Processed JSON
                              ↓
                         ADP → Value Score
                              ↓
                         Calculate Baseline VOR
                              ↓
                         Save to data/processed/
```

### 2. Draft Initialization
```
User Input (CLI) → Draft Manager Creates New Draft State
                       ↓
                  Load Player Data (snapshot)
                       ↓
                  Initialize Draft Order & Rosters
                       ↓
                  Save Initial State
```

### 3. Pick Cycle (Repeated)
```
Draft Manager: Get Current Team
       ↓
       ├─── Is AI Team? ──Yes──► Simulation Engine
       │                              ↓
       │                         Computer Drafter
       │                              ↓
       │                         Return Pick
       │                              ↓
       └─── Is Human? ──Yes──► Simulation Engine
                                      ↓
                                 Pick Recommender
                                      ↓
                                 Show Recommendation
                                      ↓
                                 User Selects Pick
                                      ↓
                              ┌───────────────┐
                              │ Draft Manager │
                              │ - Validate    │
                              │ - Update State│
                              │ - Recalc VOR  │
                              │ - Save State  │
                              └───────────────┘
```

## Module Responsibilities

### CLI Interface (`src/ui/`)
**Purpose**: User interaction layer

**Responsibilities**:
- Display draft configuration menu
- Show current draft board (picks made)
- Display available players with rankings
- Show AI recommendations
- Accept user input (pick selection)
- Display team rosters

**Does NOT**:
- Maintain state
- Validate picks
- Calculate recommendations

### Draft Manager (`src/draft_manager/`)
**Purpose**: Single source of truth for draft state and rules enforcement

**Responsibilities**:
- Create and initialize draft instances
- Maintain current draft state (in-memory)
- Persist draft state to disk (JSON)
- Validate all picks (legal player, position limits)
- Update available player pool after picks
- Enforce roster construction rules
- Manage draft order (snake draft logic)
- Trigger VOR recalculation after picks
- Orchestrate pick flow (human vs AI)

**Key Classes**:
- `DraftState`: Data class holding all draft information
- `DraftController`: Main orchestration logic
- `DraftRules`: Rule validation (roster limits, pick legality)
- `RosterValidator`: Position-specific validation

### Simulation Engine (`src/simulation_engine/`)
**Purpose**: AI intelligence for pick recommendations and computer drafting

**Responsibilities**:
- Calculate dynamic VOR based on current draft state
- Run Monte Carlo simulations for pick scenarios
- Generate pick recommendations for human users
- Make picks for computer teams
- Evaluate expected team value across simulations

**Stateless**: All functions receive draft state as input

**Key Classes**:
- `VORCalculator`: Dynamic value calculations
- `MonteCarloSimulator`: Draft outcome simulations
- `PickRecommender`: User-facing recommendations
- `ComputerDrafter`: AI opponent logic

### Data Pipeline (`src/data_pipeline/`)
**Purpose**: Transform raw FantasyPros data into usable format

**Responsibilities**:
- Ingest FantasyPros CSV files
- Clean and normalize player data
- Calculate baseline VOR values
- Handle multiple scoring formats (Standard, 0.5 PPR, Full PPR)
- Output structured JSON for simulation engine
- Maintain data versioning (by date)

**Runs**: As scheduled script, not during drafts

## Data Models

### League Configuration
```python
{
    "league_id": "uuid",
    "league_size": 12,  # Number of teams
    "scoring_format": "half_ppr",  # standard, half_ppr, full_ppr
    "draft_mode": "simulation",  # "simulation" or "manual_tracker"
    "data_year": 2024,  # Which season's projections to use
    "roster_slots": {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "FLEX": 1,  # RB/WR/TE
        "DST": 1,
        "K": 1,
        "BENCH": 6
    },
    "draft_type": "snake"
}
```

### Player Data
```python
{
    "player_id": "uuid",
    "name": "Justin Jefferson",
    "position": "WR",
    "team": "MIN",
    "bye_week": 13,
    "adp": 2.8,  # Average Draft Position
    "adp_std_dev": 1.2,  # Draft variance
    "expert_consensus_rank": 3,
    "value_score": 197.2,  # Derived from ADP (200 - ADP)
    "baseline_vor": 72.2   # Value over replacement
}
```

### Draft State
```python
{
    "draft_id": "uuid",
    "league_config": {...},
    "draft_start_time": "2024-08-15T19:00:00",
    "current_pick": 15,
    "current_round": 2,
    "current_team_index": 2,
    "draft_order": [0, 1, 2, ..., 11],  # Team indices
    "teams": [
        {
            "team_id": 0,
            "team_name": "User Team",
            "is_human": true,
            "roster": {
                "QB": [],
                "RB": ["player_id_1"],
                "WR": ["player_id_2"],
                ...
            },
            "picks": ["player_id_1", "player_id_2"]
        },
        ...
    ],
    "all_picks": [
        {
            "pick_number": 1,
            "round": 1,
            "team_id": 0,
            "player_id": "player_id_1",
            "timestamp": "2024-08-15T19:01:23"
        },
        ...
    ],
    "available_players": ["player_id_50", "player_id_51", ...],
    "player_data_snapshot": {...}  # Complete player data at draft start
}
```

## File Storage Structure

```
data/
├── raw/
│   ├── 2024/
│   │   └── fantasypros_rankings_2024.csv
│   ├── 2025/
│   │   └── fantasypros_rankings_2025.csv
│   └── ...
│
├── processed/
│   ├── players_2024.json
│   ├── players_2025.json
│   ├── players_latest.json  # Symlink to most recent season
│   └── metadata_2024.json   # Processing info per season
│
└── drafts/
    ├── draft_uuid_1.json  # Saved draft states
    ├── draft_uuid_2.json
    └── active_draft.json  # Current draft (symlink)
```

## State Management Strategy

### In-Memory State
- **Primary**: `DraftState` object held by `DraftController`
- **Lifetime**: Duration of draft session
- **Access**: Only through `DraftController` methods
- **Updates**: Atomic operations (validate → update → persist)

### Persistent State
- **Format**: JSON files in `data/drafts/`
- **Frequency**: After every pick
- **Purpose**: Resume interrupted drafts, analysis
- **Loading**: On draft initialization or resume

### State Transitions
```
Initialize Draft
    → Load Player Data
    → Create Draft State
    → Save Initial State
    
Make Pick (loop)
    → Validate Pick
    → Update In-Memory State
        - Remove from available players
        - Add to team roster
        - Add to pick history
        - Recalculate VOR
    → Persist to Disk
    → Check if Draft Complete
    
End Draft
    → Final State Save
    → Generate Summary
```

## Error Handling

### Data Pipeline Errors
- CSV parsing failures → Log error, use previous day's data
- Missing columns → Raise exception with clear message
- Invalid data types → Skip row, log warning

### Draft Manager Errors
- Invalid pick (player taken) → Reject, prompt retry
- Invalid pick (position full) → Reject, show roster limits
- File save failure → Log error, continue in-memory
- State corruption → Validate on load, reject if invalid

### Simulation Engine Errors
- Monte Carlo timeout → Return partial results
- VOR calculation error → Fall back to baseline VOR
- Missing player data → Log warning, exclude from recommendations

## Performance Considerations

### Monte Carlo Simulations
- **Target**: <2 seconds per recommendation
- **Strategy**: 
  - Limit simulation depth (e.g., next 3-5 rounds)
  - Limit number of iterations (e.g., 1000 simulations)
  - Use numpy for vectorized operations
  - Consider caching common scenarios

### VOR Recalculation
- **Target**: <100ms per pick
- **Strategy**:
  - Calculate only for remaining players
  - Use efficient filtering (set operations)
  - Cache position-specific calculations

### Data Loading
- **Target**: <1 second draft initialization
- **Strategy**:
  - Pre-processed JSON (not CSV parsing)
  - Load once at draft start
  - Keep in memory for draft duration

## Testing Strategy

### Unit Tests
- Data pipeline: CSV parsing, cleaning logic
- VOR Calculator: Calculation correctness
- Draft Rules: All validation scenarios
- State transitions: Pick updates, roster management

### Integration Tests
- Complete draft simulation (all AI teams)
- Human + AI draft scenario
- Draft pause and resume
- Invalid pick handling

### Performance Tests
- Monte Carlo simulation timing
- Large league (14-team) draft
- Data pipeline processing time

## Future Extensibility

### Microservices Migration Path
If scale becomes necessary:

1. **First Split**: Extract Simulation Engine
   - High CPU usage isolation
   - Independent scaling
   - API: REST or gRPC

2. **Second Split**: Extract Data Pipeline
   - Scheduled service
   - Independent updates
   - Message queue for updates

3. **Third Split**: Draft Manager with Database
   - PostgreSQL for state
   - Redis for caching
   - WebSocket for real-time

### Feature Extensions
- Web UI (Flask/React)
- Multi-user concurrent drafts
- Auction draft support
- Trade evaluation
- Keeper league logic
- Custom scoring systems
- Historical draft analysis

## Technology Stack

### Core
- **Language**: Python 3.10+
- **CLI Framework**: Rich (for beautiful terminal UI)
- **Data Processing**: Pandas, NumPy
- **Simulation**: NumPy (vectorized operations)
- **Testing**: pytest

### Storage
- **Player Data**: JSON files
- **Draft State**: JSON files
- **Configuration**: YAML or JSON

### Development
- **Dependency Management**: Poetry or pip + requirements.txt
- **Code Quality**: Black (formatting), flake8 (linting), mypy (type checking)
- **Version Control**: Git

## Development Workflow

### Initial Setup
```bash
# Clone repository
git clone <repo-url>
cd fantasy-draft-simulator

# Install dependencies
pip install -r requirements.txt

# Run data pipeline
python -m src.data_pipeline.run_daily_update

# Start draft
python -m src.ui.cli
```

### Daily Data Update
```bash
# Manual execution
python -m src.data_pipeline.run_daily_update

# Or set up cron job (Unix/Mac)
0 8 * * * cd /path/to/project && python -m src.data_pipeline.run_daily_update
```

### Running Tests
```bash
pytest tests/
pytest tests/test_simulation_engine.py -v  # Specific module
pytest --cov=src  # With coverage report
```

## Security Considerations

### For MVP (Single User)
- No authentication needed
- Local file system only
- No network exposure

### For Future Multi-User
- API authentication (JWT)
- Rate limiting on simulations
- Input validation and sanitization
- Secure draft state storage

## Monitoring and Observability

### MVP Logging
- Log level: INFO for normal operations, DEBUG for development
- Log file: `logs/draft_simulator.log`
- Key events to log:
  - Draft initialization
  - Each pick made
  - VOR recalculations
  - Monte Carlo completion times
  - Errors and exceptions

### Future Enhancements
- Prometheus metrics
- Distributed tracing
- Performance profiling
- Error tracking (Sentry)

---

## Development Milestones

This section provides clear, incremental benchmarks to build the system iteratively with testable checkpoints.

### Philosophy
- **Build horizontally through the stack** (full feature, end-to-end)
- **Test at each milestone** before moving forward
- **Start simple, add complexity** (e.g., VOR before Monte Carlo)
- **Always have a working system** (even if limited)

### Milestone Overview

| # | Milestone | Goal | Time |
|---|-----------|------|------|
| 0 | Project Setup | Development environment | 30min |
| 1 | CSV Ingestion | Read FantasyPros CSVs | 2-3h |
| 2 | Data Cleaning | Clean and transform data | 3-4h |
| 3 | VOR & Output | Calculate VOR, output JSON | 3-4h |
| 4 | Draft State | Create draft instances | 2-3h |
| 5 | Pick Execution | Make picks, update state | 4-5h |
| 6 | State Persistence | Save/load drafts | 2-3h |
| 7 | Dynamic VOR | Adjust for scarcity | 3-4h |
| 8 | CLI Interface | Basic draft UI | 4-5h |
| 9 | Computer Drafter | VOR-based AI | 3-4h |
| 10 | Manual Tracker | Manual draft entry | 2-3h |
| 11 | Recommender | User recommendations | 3-4h |
| 12 | **MVP Complete** | End-to-end test | 2h |
| 13 | Monte Carlo | Probabilistic simulation | 6-8h |
| 14 | Performance | Optimization | 4-6h |
| 15 | Polish | UX improvements | 4-6h |

**Total Time to MVP (M0-M12): ~40-50 hours**

### Milestone Details

#### MILESTONE 0: Project Setup
**Goal**: Get development environment ready

**Tasks**:
- Create project structure (directories)
- Set up virtual environment
- Install core dependencies (pandas, numpy, rich)
- Create basic logging configuration
- Initialize git repository

**Validation**:
```bash
python -c "import pandas, numpy, rich; print('Dependencies OK')"
```

---

#### MILESTONE 1: Data Pipeline - Basic CSV Ingestion
**Goal**: Read FantasyPros rankings CSV

**Success Criteria**:
- Can read FantasyPros CSV without errors
- Returns pandas DataFrame with expected columns
- Handles missing files gracefully

**Validation**:
```python
from src.data_pipeline.ingestion import CSVIngester

ingester = CSVIngester("data/raw/2026")
df = ingester.read_rankings("fantasypros_rankings_2026.csv")
assert len(df) > 100
assert "PLAYER NAME" in df.columns or "PLAYER NAME" in [c.strip('"') for c in df.columns]
assert "AVG." in df.columns or "AVG." in [c.strip('"') for c in df.columns]
print(f"✓ CSV ingestion works - loaded {len(df)} players")
```

---

#### MILESTONE 2: Data Pipeline - Cleaning & Transformation
**Goal**: Clean data and calculate value scores from ADP

**Success Criteria**:
- Player names normalized consistently
- Base positions extracted from position ranks (WR1 → WR)
- ADP converted to float
- Value scores calculated

**Validation**:
```python
cleaner = DataCleaner()
clean_df = cleaner.clean(df)

# Check position extraction
assert clean_df['position'].isin(['QB', 'RB', 'WR', 'TE', 'K', 'DST']).all()
assert 'WR' in clean_df['position'].values  # Has WRs
assert 'RB' in clean_df['position'].values  # Has RBs

# Check ADP conversion
assert clean_df['adp'].dtype == float
assert clean_df['adp'].min() >= 1.0
assert clean_df['adp'].max() > 100.0

transformer = DataTransformer()
with_value = transformer.calculate_value_from_adp(clean_df)

assert "value_score" in with_value.columns
assert with_value["value_score"].max() > 150  # Top players have high value
print("✓ Data cleaning and transformation works")
```

---

#### MILESTONE 3: Data Pipeline - Baseline VOR & Output
**Goal**: Calculate VOR and output JSON

**Success Criteria**:
- Complete pipeline runs without errors
- JSON output has correct structure
- VOR values are reasonable (top players have highest VOR)

**Validation**:
```bash
python -m src.data_pipeline.run_update --year 2026
# Should produce: data/processed/players_2026.json

# Verify output
python -c "
import json
with open('data/processed/players_2026.json') as f:
    data = json.load(f)
assert 'players' in data
assert len(data['players']) > 200
assert 'baseline_vor' in data['players'][0]
assert 'value_score' in data['players'][0]
print(f'✓ Pipeline complete: {len(data[\"players\"])} players')

# Check top players have highest VOR
sorted_by_vor = sorted(data['players'], key=lambda p: p['baseline_vor'], reverse=True)
print(f'Top VOR: {sorted_by_vor[0][\"name\"]} - {sorted_by_vor[0][\"baseline_vor\"]:.1f}')
"
```

---

#### MILESTONE 4: Draft Manager - State Model & Initialization
**Goal**: Create and initialize a draft

**Success Criteria**:
- Can create new draft instance
- Draft state contains all necessary data
- Player pool properly loaded
- Draft mode properly set

**Validation**:
```python
from src.draft_manager.draft_initializer import DraftInitializer

initializer = DraftInitializer()
draft_state = initializer.create_draft(
    league_size=12,
    scoring_format="half_ppr",
    roster_slots=initializer.get_default_roster_slots(),
    team_names=["Team 1", "Team 2", ..., "Team 12"],
    human_team_id=0,
    draft_mode="simulation",
    data_year=2024
)

assert draft_state.current_pick == 1
assert draft_state.current_round == 1
assert len(draft_state.available_players) > 300
print("✓ Draft initialization works")
```

---

#### MILESTONE 5: Draft Manager - Pick Validation & Execution
**Goal**: Make picks and update state

**Success Criteria**:
- Can make valid picks
- Invalid picks properly rejected
- State updates correctly after picks
- Snake draft order works correctly

**Validation**:
```python
from src.draft_manager.draft_controller import DraftController

controller = DraftController(draft_state, None, None)

# Make first pick
player_id = draft_state.available_players[0]
controller.make_pick(team_id=0, player_id=player_id)

assert draft_state.current_pick == 2
assert draft_state.current_team_id == 1  # Next team
assert player_id not in draft_state.available_players
print("✓ Pick execution works")

# Test validation
try:
    controller.make_pick(team_id=0, player_id=player_id)
    assert False, "Should have raised ValidationError"
except ValidationError:
    print("✓ Pick validation works")
```

---

#### MILESTONE 6: Draft Manager - State Persistence
**Goal**: Save and load drafts

**Success Criteria**:
- Drafts save to JSON without errors
- Loaded state matches saved state exactly
- Can resume interrupted drafts

**Validation**:
```python
from src.draft_manager.state_persistence import StatePersistence

persistence = StatePersistence()
saved_path = persistence.save_draft(draft_state)
loaded_state = persistence.load_draft(draft_state.draft_id)

assert loaded_state.current_pick == draft_state.current_pick
print("✓ State persistence works")
```

---

#### MILESTONE 7: Simulation Engine - Dynamic VOR
**Goal**: Calculate VOR adjusted for draft state

**Success Criteria**:
- VOR values adjust based on scarcity
- Positions with more drafted players have higher multipliers
- Values are reasonable and monotonic

**Validation**:
```python
from src.simulation_engine.vor_calculator import VORCalculator

vor_calc = VORCalculator(scoring_format="half_ppr")

vor_results = vor_calc.calculate_dynamic_vor(
    available_players=[...],
    drafted_positions={"QB": 2, "RB": 25, "WR": 18, "TE": 8},
    roster_slots={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
    team_roster={"QB": ["qb1"], "RB": [], "WR": ["wr1"], "TE": []}
)

# Verify RB scarcity increases VOR
print("✓ Dynamic VOR works")
```

---

#### MILESTONE 8: CLI Interface - Basic Draft Flow
**Goal**: Command-line interface for drafting

**Success Criteria**:
- Can start draft via CLI
- Can see available players
- Can make picks by player name or number
- Interface is clear and usable

**Validation**:
```bash
python -m src.ui.cli
# Should display draft board, available players, and accept picks
```

---

#### MILESTONE 9: Simple Computer Drafter
**Goal**: AI opponents that pick based on VOR

**Success Criteria**:
- Computer teams make legal picks
- Picks are reasonable (high VOR players)
- Draft completes without errors

**Validation**:
```python
from src.simulation_engine.computer_drafter import ComputerDrafter

computer = ComputerDrafter(vor_calculator=vor_calc, strategy="fast")
pick = computer.make_pick(draft_state, available_players, team_id=1)

assert pick in [p['player_id'] for p in available_players]
print(f"✓ Computer picked: {draft_state.get_player_info(pick)['name']}")
```

---

#### MILESTONE 10: Manual Draft Tracker Mode
**Goal**: Support manual entry of all picks

**Success Criteria**:
- Can enter picks for any team
- VOR recommendations update after each pick
- Works for full draft (all rounds)

**Validation**:
```bash
python -m src.ui.cli
# Choose: (2) Manual Draft Tracker
# Enter picks manually for all teams
# Verify recommendations update correctly
```

---

#### MILESTONE 11: Pick Recommender
**Goal**: User-facing pick recommendations

**Success Criteria**:
- Returns ranked list of recommendations
- Reasoning explains why each player is valuable
- Recommendations make sense given draft context

**Validation**:
```python
from src.simulation_engine.pick_recommender import PickRecommender

recommender = PickRecommender(vor_calculator=vor_calc, mc_simulator=None)
recommendations = recommender.recommend_picks(
    draft_state=draft_state,
    available_players=available_players,
    num_recommendations=5
)

assert len(recommendations) == 5
print(f"✓ Top pick: {recommendations[0].player_name}")
```

---

#### MILESTONE 12: End-to-End MVP Test
**Goal**: Complete draft simulation with all features

**Success Criteria**:
- Can complete full draft without errors
- All teams have complete rosters
- Manual tracker mode works correctly
- Saved draft can be loaded

**Validation**:
```bash
# Test simulation mode
python -m src.ui.cli
# Complete a full draft, verify results

# Test manual tracker mode  
python -m src.ui.cli
# Track a full draft manually, verify recommendations
```

**🎉 MVP COMPLETE - Ready for real use!**

---

#### MILESTONE 13: Monte Carlo Simulator (Advanced)
**Goal**: Add probabilistic simulation for better recommendations

**Success Criteria**:
- Simulations complete in <2 seconds
- Recommendations differ from pure VOR
- Computer drafters perform better

---

#### MILESTONE 14: Performance Optimization
**Goal**: Make everything fast and responsive

**Benchmarks**:
- Pick validation: <10ms
- VOR calculation: <100ms
- Simple recommendation: <500ms
- Monte Carlo recommendation: <2 seconds

---

#### MILESTONE 15: Polish & User Experience
**Goal**: Make the tool pleasant to use

**Features**:
- Draft board visualization
- Team comparison
- "Reached" and "Steal" indicators
- Export draft results

---

### Testing Strategy

**After Each Milestone**:
- Run unit tests
- Manual testing of new feature
- Regression test previous features

**Continuous Testing**:
```bash
pytest tests/ -v
pytest tests/ --cov=src --cov-report=html
```

**Integration Testing Checkpoints**:
- After M6: Can initialize and make picks
- After M9: Can complete full draft with AI
- After M10: Can track manual draft
- After M12: Full end-to-end test

---

## Document Version
- **Version**: 1.1
- **Last Updated**: 2024-08-15
- **Author**: System Architect
- **Status**: Approved for MVP Development
