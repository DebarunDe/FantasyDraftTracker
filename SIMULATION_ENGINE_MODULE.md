# Simulation Engine Module Design

## Overview

The Simulation Engine is the AI brain of the draft simulator. It provides intelligent pick recommendations to human users and makes optimal picks for computer opponents using Monte Carlo simulations and dynamic Value Over Replacement (VOR) calculations.

## Module Purpose

**Primary Goal**: Generate optimal draft picks based on probabilistic simulation of future draft outcomes.

**Key Responsibilities**:
1. Calculate dynamic VOR based on current draft state
2. Run Monte Carlo simulations to evaluate pick scenarios
3. Recommend optimal picks to human users with explanations
4. Make intelligent picks for computer teams
5. Account for positional scarcity and roster construction

**Design Philosophy**: Stateless, pure functions that receive draft state as input and return recommendations.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Simulation Engine                          │
│                      (Stateless)                             │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           VOR Calculator                               │ │
│  │  Input: Draft State, Available Players                │ │
│  │  Output: VOR for each available player                │ │
│  │  - Dynamic baseline adjustment                         │ │
│  │  - Positional scarcity multiplier                      │ │
│  │  - Roster needs weighting                              │ │
│  └───────────────────┬────────────────────────────────────┘ │
│                      │                                        │
│                      ▼                                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │       Monte Carlo Simulator                            │ │
│  │  Input: Draft State, Available Players, Pick Options  │ │
│  │  Output: Simulated outcomes for each pick             │ │
│  │  - Simulate remaining draft rounds                     │ │
│  │  - Model opponent behavior                             │ │
│  │  - Calculate expected team value                       │ │
│  └───────────────────┬────────────────────────────────────┘ │
│                      │                                        │
│         ┌────────────┴────────────┐                          │
│         ▼                         ▼                          │
│  ┌──────────────┐       ┌──────────────────┐               │
│  │     Pick     │       │    Computer      │               │
│  │ Recommender  │       │    Drafter       │               │
│  │              │       │                  │               │
│  │ - Top 5 picks│       │ - Auto-pick for │               │
│  │ - Reasoning  │       │   AI teams      │               │
│  │ - Trade-offs │       │ - Strategy logic│               │
│  └──────────────┘       └──────────────────┘               │
└──────────────────────────────────────────────────────────────┘
```

## Module Structure

```
src/simulation_engine/
├── __init__.py
├── vor_calculator.py      # Dynamic VOR calculations
├── monte_carlo.py         # Draft simulations
├── pick_recommender.py    # User-facing recommendations
├── computer_drafter.py    # AI opponent logic
├── draft_simulator.py     # Core simulation logic
├── utils.py               # Helper functions
├── config.py              # Simulation parameters
└── models.py              # Data classes
```

## Component Details

### 1. VOR Calculator (`vor_calculator.py`)

**Purpose**: Calculate dynamic Value Over Replacement adjusted for draft state

```python
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class VORResult:
    """Result of VOR calculation for a player"""
    player_id: str
    base_vor: float
    dynamic_vor: float
    scarcity_multiplier: float
    position_rank: int
    explanation: str


class VORCalculator:
    """Calculates dynamic VOR based on current draft state"""
    
    def __init__(self, scoring_format: str):
        self.scoring_format = scoring_format
        
    def calculate_dynamic_vor(
        self,
        available_players: List[Dict],
        drafted_positions: Dict[str, int],  # Position -> count drafted
        roster_slots: Dict[str, int],       # Position -> total slots
        team_roster: Dict[str, List]        # Current team's roster
    ) -> Dict[str, VORResult]:
        """
        Calculate VOR for all available players adjusted for:
        - Positional scarcity (fewer players left at position)
        - Roster needs (unfilled positions more valuable)
        - Remaining draft picks
        """
        
    def _calculate_scarcity_multiplier(
        self,
        position: str,
        available_count: int,
        drafted_count: int,
        remaining_teams: int
    ) -> float:
        """
        Adjust VOR based on how scarce a position is becoming.
        
        Formula: scarcity = 1 + (drafted_pct * scarcity_factor)
        - As more players at position are drafted, scarcity increases
        - RB/WR get higher scarcity weights than QB/TE
        """
        
    def _calculate_roster_need_multiplier(
        self,
        position: str,
        team_roster: Dict[str, List],
        roster_slots: Dict[str, int]
    ) -> float:
        """
        Adjust VOR based on team's current roster needs.
        
        Formula: need = slots_remaining / total_slots
        - Empty positions get higher multiplier
        - Diminishing returns for stacking same position
        """
```

**Dynamic VOR Formula**:

```python
dynamic_VOR = base_VOR * scarcity_multiplier * need_multiplier

where:
    scarcity_multiplier = 1 + (drafted_pct * position_scarcity_weight)
    drafted_pct = players_drafted_at_position / total_startable_players
    
    position_scarcity_weight = {
        "RB": 2.0,   # RBs are scarce, value increases fast
        "WR": 1.8,   # WRs moderately scarce
        "TE": 1.5,   # TE position thin after top tier
        "QB": 1.2,   # QBs relatively deep
        "DST": 1.0,  # Streaming positions, less scarcity
        "K": 1.0
    }
    
    need_multiplier = 1 + (empty_slots / total_slots) * 0.5
```

**Example Calculation**:

```python
# Scenario: Round 3, Pick 5 (12-team league)
# 28 picks have been made (including 15 RBs, 10 WRs, 3 QBs)
# Your team: RB, WR (need another RB, WR, flex options)

Player: Derrick Henry (RB)
- Base VOR: 85.2 (calculated in data pipeline)
- Drafted RBs: 15 / 36 = 42% of startable RBs taken
- Scarcity multiplier: 1 + (0.42 * 2.0) = 1.84
- Roster need (1 RB slot filled, 2-3 needed): 
  Need multiplier = 1 + (1.5 / 2.5) * 0.5 = 1.3
- Dynamic VOR = 85.2 * 1.84 * 1.3 = 203.9

Player: Garrett Wilson (WR)
- Base VOR: 75.5
- Drafted WRs: 10 / 36 = 28%
- Scarcity multiplier: 1 + (0.28 * 1.8) = 1.50
- Roster need (1 WR slot filled, 2-3 needed):
  Need multiplier = 1 + (1.5 / 2.5) * 0.5 = 1.3
- Dynamic VOR = 75.5 * 1.50 * 1.3 = 147.2

Result: Henry recommended due to higher dynamic VOR
```

### 2. Monte Carlo Simulator (`monte_carlo.py`)

**Purpose**: Simulate future draft scenarios to evaluate pick options

```python
from typing import List, Dict, Tuple
import numpy as np
from dataclasses import dataclass

@dataclass
class SimulationResult:
    """Result of Monte Carlo simulation for a pick"""
    player_id: str
    player_name: str
    expected_team_value: float
    value_variance: float
    best_outcome: float
    worst_outcome: float
    simulation_count: int


class MonteCarloSimulator:
    """Simulates draft outcomes to evaluate picks"""
    
    def __init__(
        self,
        num_simulations: int = 1000,
        simulation_depth: int = 5  # Rounds to simulate
    ):
        self.num_simulations = num_simulations
        self.simulation_depth = simulation_depth
        
    def evaluate_picks(
        self,
        candidate_picks: List[str],  # Player IDs to evaluate
        draft_state: Dict,
        available_players: List[Dict]
    ) -> List[SimulationResult]:
        """
        For each candidate pick, simulate future draft rounds
        and calculate expected team value.
        
        Returns ranked list of picks by expected value.
        """
        
    def _run_single_simulation(
        self,
        initial_pick: str,
        draft_state: Dict,
        available_players: List[Dict]
    ) -> float:
        """
        Run one simulation:
        1. Make the initial pick for current team
        2. Simulate opponent picks for remaining rounds
        3. Simulate our picks in future rounds
        4. Calculate final team value
        
        Returns: Total projected fantasy points for team
        """
        
    def _simulate_opponent_pick(
        self,
        available: List[Dict],
        team_roster: Dict[str, List],
        opponent_strategy: str = "best_available"
    ) -> str:
        """
        Model how an opponent would pick.
        
        Strategies:
        - best_available: Highest VOR remaining
        - positional_need: Fill empty positions first
        - stochastic: Add randomness (normal distribution around VOR)
        """
```

**Simulation Algorithm**:

```
For each candidate pick:
    For i = 1 to num_simulations:
        1. Create draft state copy
        2. Make candidate pick for current team
        3. For each remaining round until simulation_depth:
            a. Simulate all opponent picks (VOR-based with noise)
            b. Simulate our team's pick (best available VOR)
        4. Calculate team's total projected points
        5. Store team value
    
    Calculate statistics:
        - Expected value (mean)
        - Variance (std dev)
        - Best case (95th percentile)
        - Worst case (5th percentile)

Return picks ranked by expected value
```

**Opponent Modeling**:

```python
def _simulate_opponent_pick(self, available, team_roster):
    """
    Model realistic opponent behavior with stochastic element
    """
    # Calculate VOR for each available player
    vor_scores = self._calculate_vor_for_all(available, team_roster)
    
    # Add uncertainty: opponents don't always take best player
    # Sample from normal distribution around VOR
    noisy_scores = {}
    for player_id, vor in vor_scores.items():
        # Standard deviation = 15% of VOR value
        noise = np.random.normal(0, vor * 0.15)
        noisy_scores[player_id] = vor + noise
    
    # Pick player with highest noisy score
    best_player = max(noisy_scores, key=noisy_scores.get)
    return best_player
```

**Performance Optimization**:

```python
# Use NumPy for vectorized operations
def _calculate_team_values_vectorized(self, rosters, player_projections):
    """Calculate all team values in one vectorized operation"""
    # Convert to numpy array
    team_ids = np.array([r['player_ids'] for r in rosters])
    projections = np.array([player_projections[pid] for pid in team_ids])
    
    # Sum across players for each team (vectorized)
    team_values = np.sum(projections, axis=1)
    return team_values

# Parallel simulation for speed
from concurrent.futures import ProcessPoolExecutor

def evaluate_picks_parallel(self, candidate_picks, draft_state, available):
    """Run simulations in parallel across CPU cores"""
    with ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(
                self._simulate_pick, 
                pick, 
                draft_state, 
                available
            )
            for pick in candidate_picks
        ]
        results = [f.result() for f in futures]
    return results
```

**Simulation Depth Strategy**:

```python
def _adaptive_simulation_depth(self, current_round, total_rounds):
    """
    Adjust simulation depth based on draft stage.
    
    Early rounds: Simulate deeper (more future value matters)
    Late rounds: Simulate shallower (immediate needs matter more)
    """
    if current_round <= 3:
        return 5  # Simulate 5 rounds ahead
    elif current_round <= 8:
        return 3  # Simulate 3 rounds ahead
    else:
        return 2  # Simulate 2 rounds ahead (best available)
```

### 3. Pick Recommender (`pick_recommender.py`)

**Purpose**: Generate user-friendly pick recommendations with reasoning

```python
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class PickRecommendation:
    """A single pick recommendation with explanation"""
    rank: int
    player_id: str
    player_name: str
    position: str
    team: str
    projected_points: float
    dynamic_vor: float
    expected_value: float  # From Monte Carlo
    reasoning: str
    trade_offs: str


class PickRecommender:
    """Generates human-readable pick recommendations"""
    
    def __init__(
        self,
        vor_calculator: VORCalculator,
        mc_simulator: MonteCarloSimulator
    ):
        self.vor_calculator = vor_calculator
        self.mc_simulator = mc_simulator
        
    def recommend_picks(
        self,
        draft_state: Dict,
        available_players: List[Dict],
        num_recommendations: int = 5
    ) -> List[PickRecommendation]:
        """
        Generate top N pick recommendations with explanations.
        
        Process:
        1. Calculate dynamic VOR for all available players
        2. Select top 10-15 candidates by VOR
        3. Run Monte Carlo simulations on candidates
        4. Rank by expected value from simulations
        5. Generate explanations for top N
        """
        
    def _generate_reasoning(
        self,
        player: Dict,
        vor_result: VORResult,
        sim_result: SimulationResult,
        draft_state: Dict
    ) -> str:
        """
        Generate human-readable explanation for why this pick is good.
        
        Includes:
        - Position scarcity ("RBs flying off the board")
        - Roster fit ("Fills your RB2 slot")
        - Value comparison ("40 points ahead of next RB")
        - Risk assessment ("Consistent floor, high ceiling")
        """
        
    def _generate_trade_offs(
        self,
        recommended_player: Dict,
        alternative_players: List[Dict],
        draft_state: Dict
    ) -> str:
        """
        Explain what you're giving up by taking this player.
        
        Example: "Passing on Garrett Wilson (WR) who has higher 
                  upside but fills a less urgent position need."
        """
```

**Reasoning Generation Examples**:

```python
def _generate_reasoning(self, player, vor_result, sim_result, draft_state):
    """Generate contextual explanation"""
    reasons = []
    
    # Scarcity factor
    if vor_result.scarcity_multiplier > 1.5:
        reasons.append(
            f"{player['position']}s being drafted heavily "
            f"({vor_result.position_rank} of top players remaining)"
        )
    
    # Roster fit
    team_roster = draft_state['teams'][draft_state['current_team']]['roster']
    position_filled = len(team_roster.get(player['position'], []))
    position_needed = draft_state['league_config']['roster_slots'][player['position']]
    
    if position_filled < position_needed:
        reasons.append(
            f"Fills your {player['position']}{position_filled + 1} slot"
        )
    
    # Value comparison
    next_player = self._find_next_at_position(player['position'], available_players)
    if next_player:
        point_diff = player['projected_points'] - next_player['projected_points']
        if point_diff > 20:
            reasons.append(
                f"{point_diff:.1f} points ahead of next {player['position']} "
                f"({next_player['name']})"
            )
    
    # Simulation confidence
    if sim_result.value_variance < 50:
        reasons.append("Consistent value across simulations (low risk)")
    
    return ". ".join(reasons) + "."


def _generate_trade_offs(self, recommended, alternatives, draft_state):
    """Explain opportunity cost"""
    trade_offs = []
    
    for alt in alternatives[:2]:  # Top 2 alternatives
        if alt['position'] != recommended['position']:
            point_diff = alt['projected_points'] - recommended['projected_points']
            
            if point_diff > 10:
                trade_offs.append(
                    f"Passing on {alt['name']} ({alt['position']}) who projects "
                    f"{point_diff:.1f} more points but fills less urgent need"
                )
            else:
                trade_offs.append(
                    f"Choosing positional value over {alt['name']} ({alt['position']})"
                )
    
    return " ".join(trade_offs) if trade_offs else "Clear best available player."
```

**Recommendation Output Format**:

```python
[
    PickRecommendation(
        rank=1,
        player_id="bsanders_rb_det",
        player_name="Barry Sanders",
        position="RB",
        team="DET",
        projected_points=285.5,
        dynamic_vor=203.9,
        expected_value=1847.3,  # Total team points across simulations
        reasoning="RBs being drafted heavily (5th best RB remaining). "
                  "Fills your RB2 slot. 35.2 points ahead of next RB "
                  "(Najee Harris). Consistent value across simulations.",
        trade_offs="Passing on Garrett Wilson (WR) who projects 15.3 more "
                   "points but fills less urgent need."
    ),
    PickRecommendation(rank=2, ...),
    # ...
]
```

### 4. Computer Drafter (`computer_drafter.py`)

**Purpose**: Make intelligent picks for AI opponents

```python
from typing import Dict, List, Optional

class ComputerDrafter:
    """Makes draft picks for AI teams"""
    
    def __init__(
        self,
        vor_calculator: VORCalculator,
        mc_simulator: Optional[MonteCarloSimulator] = None,
        strategy: str = "optimal"
    ):
        self.vor_calculator = vor_calculator
        self.mc_simulator = mc_simulator
        self.strategy = strategy
        
    def make_pick(
        self,
        draft_state: Dict,
        available_players: List[Dict],
        team_id: int
    ) -> str:
        """
        Make a pick for a computer team.
        
        Strategies:
        - optimal: Use Monte Carlo simulations (slow but best)
        - fast: Use VOR only (faster)
        - balanced: VOR + lightweight simulation
        """
        
    def _optimal_pick(
        self,
        draft_state: Dict,
        available: List[Dict],
        team_id: int
    ) -> str:
        """Use full Monte Carlo simulation (500 iterations)"""
        
    def _fast_pick(
        self,
        draft_state: Dict,
        available: List[Dict],
        team_id: int
    ) -> str:
        """Use dynamic VOR only, with positional balancing"""
        
    def _add_draft_personality(self) -> float:
        """
        Add slight randomness so computer teams don't all draft identically.
        
        Returns: Noise factor to apply to VOR (0.9 - 1.1)
        """
```

**Computer Strategy Implementation**:

```python
def _fast_pick(self, draft_state, available, team_id):
    """
    Fast pick strategy using dynamic VOR with smart balancing.
    
    Algorithm:
    1. Calculate dynamic VOR for all available players
    2. Apply team-specific positional needs multiplier
    3. Add small random factor for variety
    4. Pick highest adjusted VOR
    """
    team_roster = draft_state['teams'][team_id]['roster']
    
    # Calculate VOR for all available
    vor_results = self.vor_calculator.calculate_dynamic_vor(
        available,
        self._get_drafted_counts(draft_state),
        draft_state['league_config']['roster_slots'],
        team_roster
    )
    
    # Apply positional balance
    adjusted_scores = {}
    for player_id, vor in vor_results.items():
        player = next(p for p in available if p['player_id'] == player_id)
        position = player['position']
        
        # Boost positions we need more
        need_multiplier = self._calculate_positional_urgency(
            position, team_roster, draft_state
        )
        
        # Add personality (small random factor)
        personality_factor = np.random.uniform(0.95, 1.05)
        
        adjusted_scores[player_id] = (
            vor.dynamic_vor * need_multiplier * personality_factor
        )
    
    # Pick highest adjusted score
    best_pick = max(adjusted_scores, key=adjusted_scores.get)
    return best_pick


def _calculate_positional_urgency(self, position, roster, draft_state):
    """
    How urgently does this team need this position?
    
    Returns multiplier: 0.8 (already stacked) to 1.5 (desperate need)
    """
    current_round = draft_state['current_round']
    total_rounds = draft_state['league_config']['total_rounds']
    
    slots_needed = draft_state['league_config']['roster_slots'][position]
    slots_filled = len(roster.get(position, []))
    
    if slots_filled >= slots_needed:
        # Position filled, less urgent
        return 0.8
    elif slots_filled == 0:
        # No players at position
        if current_round > total_rounds / 2:
            # Late in draft, very urgent
            return 1.5
        else:
            # Early draft, moderate urgency
            return 1.2
    else:
        # Partially filled, normal urgency
        return 1.0
```

### 5. Configuration (`config.py`)

```python
# config.py

# Monte Carlo parameters
MC_NUM_SIMULATIONS = 1000
MC_SIMULATION_DEPTH = 5  # Rounds to simulate ahead
MC_PARALLEL_WORKERS = 4  # CPU cores for parallel simulation

# VOR calculation parameters
POSITION_SCARCITY_WEIGHTS = {
    "QB": 1.2,
    "RB": 2.0,
    "WR": 1.8,
    "TE": 1.5,
    "K": 1.0,
    "DST": 1.0
}

ROSTER_NEED_WEIGHT = 0.5  # How much to weight positional needs

# Computer drafter parameters
COMPUTER_STRATEGY = "fast"  # "optimal", "fast", "balanced"
COMPUTER_PERSONALITY_VARIANCE = 0.05  # +/- 5% randomness

# Performance tuning
CANDIDATE_POOL_SIZE = 15  # Top N players to run MC simulations on
EARLY_ROUND_THRESHOLD = 3  # Rounds to consider "early"
LATE_ROUND_THRESHOLD = 10  # Rounds to consider "late"

# Adaptive simulation depths
SIMULATION_DEPTH_BY_ROUND = {
    "early": 5,   # Rounds 1-3
    "mid": 3,     # Rounds 4-8
    "late": 2     # Rounds 9+
}
```

## Usage Examples

### 1. Getting User Recommendations

```python
from src.simulation_engine.pick_recommender import PickRecommender
from src.simulation_engine.vor_calculator import VORCalculator
from src.simulation_engine.monte_carlo import MonteCarloSimulator

# Initialize components
vor_calc = VORCalculator(scoring_format="half_ppr")
mc_sim = MonteCarloSimulator(num_simulations=1000, simulation_depth=5)
recommender = PickRecommender(vor_calc, mc_sim)

# Get recommendations
recommendations = recommender.recommend_picks(
    draft_state=current_draft_state,
    available_players=available_players,
    num_recommendations=5
)

# Display to user
for rec in recommendations:
    print(f"{rec.rank}. {rec.player_name} ({rec.position})")
    print(f"   Projected: {rec.projected_points:.1f} pts")
    print(f"   Reasoning: {rec.reasoning}")
    print(f"   Trade-offs: {rec.trade_offs}")
    print()
```

### 2. Computer Making a Pick

```python
from src.simulation_engine.computer_drafter import ComputerDrafter

# Initialize computer drafter
computer = ComputerDrafter(
    vor_calculator=vor_calc,
    strategy="fast"  # Fast strategy for snappy drafting
)

# Make pick for team
pick = computer.make_pick(
    draft_state=current_draft_state,
    available_players=available_players,
    team_id=5  # Computer team ID
)

print(f"Computer team picks: {pick['player_name']}")
```

### 3. Direct VOR Calculation

```python
from src.simulation_engine.vor_calculator import VORCalculator

vor_calc = VORCalculator(scoring_format="half_ppr")

# Calculate VOR for all available players
vor_results = vor_calc.calculate_dynamic_vor(
    available_players=available_players,
    drafted_positions={"QB": 5, "RB": 18, "WR": 15, "TE": 3},
    roster_slots={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
    team_roster={"QB": [], "RB": ["player1"], "WR": [], "TE": []}
)

# Sort by dynamic VOR
sorted_players = sorted(
    vor_results.items(),
    key=lambda x: x[1].dynamic_vor,
    reverse=True
)

for player_id, vor_result in sorted_players[:10]:
    print(f"{vor_result.player_name}: {vor_result.dynamic_vor:.1f}")
```

## Performance Considerations

### Target Response Times

- **User Recommendation**: < 2 seconds
- **Computer Pick (fast)**: < 0.5 seconds
- **Computer Pick (optimal)**: < 3 seconds

### Optimization Strategies

1. **Candidate Filtering**:
   ```python
   # Don't simulate all 200+ available players
   # Filter to top 15 by VOR, then simulate those
   candidates = sort_by_vor(available_players)[:15]
   simulate_only(candidates)
   ```

2. **Adaptive Depth**:
   ```python
   # Reduce simulation depth in late rounds
   if current_round > 10:
       simulation_depth = 2
   else:
       simulation_depth = 5
   ```

3. **Vectorization**:
   ```python
   # Use numpy for batch operations
   team_values = np.sum(player_projections[roster_ids], axis=1)
   ```

4. **Caching**:
   ```python
   # Cache VOR calculations that don't change between picks
   @lru_cache(maxsize=1000)
   def get_baseline_vor(player_id, scoring):
       return baseline_vor_lookup[player_id][scoring]
   ```

5. **Parallel Processing**:
   ```python
   # Run simulations in parallel
   with ProcessPoolExecutor(max_workers=4) as executor:
       futures = [executor.submit(simulate, pick) for pick in candidates]
       results = [f.result() for f in futures]
   ```

### Memory Management

- Keep only necessary data in memory
- Clear simulation results after pick
- Use generators for large datasets

```python
def available_players_generator(all_players, drafted_ids):
    """Generate available players on-the-fly instead of creating large lists"""
    for player in all_players:
        if player['player_id'] not in drafted_ids:
            yield player
```

## Testing Strategy

### Unit Tests

```python
# test_vor_calculator.py
def test_scarcity_multiplier():
    vor_calc = VORCalculator("half_ppr")
    
    # High scarcity scenario (75% of RBs drafted)
    multiplier = vor_calc._calculate_scarcity_multiplier(
        position="RB",
        available_count=9,
        drafted_count=27,
        remaining_teams=12
    )
    
    assert multiplier > 1.5  # Should significantly boost value


# test_monte_carlo.py
def test_simulation_deterministic_with_seed():
    """Ensure reproducibility with random seed"""
    np.random.seed(42)
    
    mc_sim = MonteCarloSimulator(num_simulations=100)
    result1 = mc_sim.evaluate_picks([player1], draft_state, available)
    
    np.random.seed(42)
    result2 = mc_sim.evaluate_picks([player1], draft_state, available)
    
    assert result1[0].expected_value == result2[0].expected_value
```

### Integration Tests

```python
def test_full_recommendation_flow():
    """Test complete recommendation generation"""
    vor_calc = VORCalculator("half_ppr")
    mc_sim = MonteCarloSimulator(num_simulations=100)  # Faster for tests
    recommender = PickRecommender(vor_calc, mc_sim)
    
    recommendations = recommender.recommend_picks(
        mock_draft_state,
        mock_available_players,
        num_recommendations=5
    )
    
    assert len(recommendations) == 5
    assert recommendations[0].rank == 1
    assert recommendations[0].reasoning != ""
    assert recommendations[0].expected_value > recommendations[1].expected_value
```

### Performance Tests

```python
import time

def test_recommendation_performance():
    """Ensure recommendations complete within time limit"""
    start = time.time()
    
    recommendations = recommender.recommend_picks(
        large_draft_state,
        many_available_players,
        num_recommendations=5
    )
    
    elapsed = time.time() - start
    assert elapsed < 2.0  # Must complete in under 2 seconds
```

## Future Enhancements

### Advanced Features

1. **Machine Learning Integration**:
   - Train model on historical draft data
   - Learn actual opponent tendencies
   - Predict ADP deviations

2. **Multi-Objective Optimization**:
   - Balance upside vs. floor
   - Risk-adjusted recommendations
   - Maximize team ceiling or consistency

3. **Scenario Analysis**:
   - "What if" simulations
   - Show draft paths
   - Visualize decision trees

4. **Streaming Strategy**:
   - Identify streamable positions (DST, K)
   - Recommend late-round dart throws
   - Value late picks differently

### Performance Improvements

1. **GPU Acceleration**:
   - Use CuPy for GPU-accelerated simulations
   - 10-100x speedup for large simulations

2. **Approximate Methods**:
   - Use closed-form approximations for VOR
   - Reduced simulation counts with importance sampling

3. **Progressive Results**:
   - Stream recommendations as they're computed
   - Show top pick immediately, refine others

---

## Document Version
- **Version**: 1.0
- **Last Updated**: 2024-08-15
- **Status**: Approved for MVP Development
