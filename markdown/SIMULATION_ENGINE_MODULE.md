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
                          ┌─────────────────────┐
                          │  Player JSON Data    │
                          │  overall_rank (ECR)  │◄── ADP Signal
                          └──────────┬──────────┘
                                     │
┌────────────────────────────────────│────────────────────────┐
│                   Simulation Engine│                         │
│                      (Stateless)   │                         │
│                                    │                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │       VOR Calculator (pure — no ADP influence)         │ │
│  │  Input: Draft State, Available Players                │ │
│  │  Output: VOR for each available player                │ │
│  │  - Dynamic baseline adjustment                         │ │
│  │  - Positional scarcity multiplier                      │ │
│  │  - Roster needs weighting + tier urgency               │ │
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
│  ┌──────────────┐       ┌──────────────────────┐           │
│  │     Pick     │       │    Computer Drafter  │◄──ADP rank│
│  │ Recommender  │       │                      │           │
│  │ (pure VOR)   │       │ adp_weight per       │           │
│  │              │       │ strategy:            │           │
│  │ - Top 5 picks│       │ vor_only   0.0       │           │
│  │ - Reasoning  │       │ balanced   0.4       │           │
│  │ - Trade-offs │       │ consensus  0.7       │           │
│  └──────────────┘       │ contrarian 0.0+noise │           │
│                         └──────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
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

---

### 1a. ADP-VOR Signal Integration (for Computer Drafter)

**Why ADP blending is needed**: Pure VOR is the mathematically optimal signal, but it
systematically differs from how real drafters behave. Analysis of the top-36 players in
a 2025 12-team Half PPR draft revealed a structural position bias:

| Position | Avg ADP Rank | Avg VOR Rank | Gap (VOR − ADP) |
|----------|-------------|-------------|-----------------|
| WR       | 15.2        | 44.0        | **+28.8** (under-valued by VOR) |
| RB       | 18.5        | 7.0         | **−11.5** (over-valued by VOR) |
| QB       | 29.5        | 16.8        | **−12.8** (over-valued by VOR) |
| TE       | 22.3        | 37.0        | **+14.7** (under-valued by VOR) |

Pure VOR ranks RBs ~12 spots too high and WRs ~29 spots too low relative to real draft
consensus. For human recommendations this is intentional — it surfaces inefficiencies to
exploit. For computer opponents, pure VOR would make them unrealistically RB-heavy and
produce uncompetitive simulations.

**The fix: rank fusion blending**

Rather than blending raw score values (which have different units and ranges), blending
is done in rank space so both signals contribute equally on a 0–1 scale:

```python
total_players = len(available_players)

# Rank by dynamic_vor descending (1 = highest VOR)
vor_score = 1 - (vor_rank - 1) / total_players

# ADP rank from overall_rank field (FantasyPros ECR, lower = better)
adp_rank = player["overall_rank"]
adp_score = 1 - (adp_rank - 1) / total_players

# Weighted blend — adp_weight controls realism vs optimality
composite = (1 - adp_weight) * vor_score + adp_weight * adp_score
```

**Key design decisions**:

1. **VOR Calculator is not modified** — it remains pure and is used unchanged for human
   recommendations (`PickRecommender`). ADP blending is applied only inside
   `ComputerDrafter._compute_blended_scores()`.

2. **`overall_rank` is the ADP signal** — the FantasyPros ECR column already written into
   every player record by the data pipeline. No new data source is needed.

3. **Rank fusion avoids scale mismatch** — VOR values range from −100 to +200; `overall_rank`
   is an integer 1–N. Normalizing both to 0–1 before blending prevents one signal from
   dominating by magnitude.

4. **`contrarian` uses noise instead of ADP weight** — ±15% random perturbation on pure
   VOR simulates a drafter intentionally zigging when consensus zags.

**ADP signal data flow**:
```
data pipeline                  computer drafter
─────────────                  ────────────────
FantasyPros rankings CSV  →    available_players list
  Overall_Rank column     →    player['overall_rank']
  → players_2025.json     →    _compute_blended_scores()
                                composite score → pick
```

---

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

**Purpose**: Make intelligent picks for AI opponents using ADP-blended composite scoring

**Design principle**: Human recommendations use pure VOR (strategically optimal). Computer
opponents use ADP-blended scoring so they behave like real fantasy drafters, making
simulations more realistic and competitive.

```python
import numpy as np
from typing import Dict, List, Optional

from src.simulation_engine.config import (
    ADP_BLEND_STRATEGIES,
    COMPUTER_ADP_WEIGHT,
    COMPUTER_PERSONALITY_VARIANCE,
)


class ComputerDrafter:
    """Makes ADP-blended draft picks for AI teams.

    Uses rank fusion to combine dynamic VOR and ADP (overall_rank) signals.
    The adp_weight controls the blend: 0.0 = pure VOR, 1.0 = pure ADP.
    """

    def __init__(
        self,
        vor_calculator: "DynamicVORCalculator",
        strategy: str = "balanced",
        adp_weight: Optional[float] = None,
    ):
        self.vor_calculator = vor_calculator
        self.strategy = strategy
        # Explicit adp_weight overrides the strategy default
        if adp_weight is not None:
            self.adp_weight = adp_weight
        else:
            self.adp_weight = ADP_BLEND_STRATEGIES.get(strategy, COMPUTER_ADP_WEIGHT)
        # contrarian uses noise in addition to pure VOR
        self.noise_factor = 0.15 if strategy == "contrarian" else 0.0

    def make_pick(
        self,
        draft_state: Dict,
        available_players: List[Dict],
        team_id: int,
    ) -> str:
        """Make a pick for a computer team using the configured strategy.

        Returns: player_id of the chosen pick.
        """
        vor_results = self.vor_calculator.calculate_from_draft_state(
            draft_state, team_id
        )
        scores = self._compute_blended_scores(available_players, vor_results)
        best_pick = max(scores, key=scores.get)
        return best_pick

    def _compute_blended_scores(
        self,
        available_players: List[Dict],
        vor_results: Dict,
    ) -> Dict[str, float]:
        """Compute composite score for each available player.

        Uses rank fusion: both VOR and ADP are normalized to 0-1 before blending
        so neither signal dominates by magnitude.

        Formula:
            vor_score = 1 - (vor_rank - 1) / total_players
            adp_score = 1 - (adp_rank - 1) / total_players
            composite = (1 - adp_weight) * vor_score + adp_weight * adp_score
        """
        total = len(available_players)
        if total == 0:
            return {}

        # Build VOR rank: sort by dynamic_vor descending → rank 1 = best
        vor_rank_map = self._rank_by_vor(vor_results)

        scores = {}
        for player in available_players:
            pid = player["player_id"]
            vor_rank = vor_rank_map.get(pid, total)
            vor_score = 1 - (vor_rank - 1) / total

            # ADP signal: overall_rank (FantasyPros ECR, lower = better)
            # Fall back to total (worst rank) if field is missing
            adp_rank = player.get("overall_rank") or total
            adp_score = 1 - (adp_rank - 1) / total

            composite = (
                (1 - self.adp_weight) * vor_score
                + self.adp_weight * adp_score
            )

            # contrarian: add noise to pure VOR to exploit ADP inefficiencies
            if self.noise_factor > 0:
                noise = np.random.uniform(-self.noise_factor, self.noise_factor)
                composite = max(0.0, composite + noise)

            scores[pid] = composite

        return scores

    @staticmethod
    def _rank_by_vor(vor_results: Dict) -> Dict[str, int]:
        """Return a dict mapping player_id to 1-based VOR rank (1 = highest VOR)."""
        sorted_ids = sorted(
            vor_results.keys(),
            key=lambda pid: vor_results[pid].dynamic_vor,
            reverse=True,
        )
        return {pid: rank for rank, pid in enumerate(sorted_ids, start=1)}
```

**Strategy Details**:

| Strategy     | `adp_weight` | Noise  | Description |
|-------------|--------------|--------|-------------|
| `vor_only`  | 0.0          | 0.0    | Pure dynamic VOR. RB-heavy early rounds (VOR reflects steeper RB talent dropoff). Mathematically optimal. |
| `balanced`  | 0.4          | 0.0    | 60% VOR + 40% ADP. Default for most computer opponents. Produces realistic position distributions. |
| `consensus` | 0.7          | 0.0    | 30% VOR + 70% ADP. Closely follows the expert consensus board. Simulates a risk-averse human drafter. |
| `contrarian`| 0.0          | 0.15   | Pure VOR + ±15% random noise. Intentionally exploits ADP inefficiencies. High variance — sometimes brilliant, sometimes poor. |

**Why `balanced` is the default**: At `adp_weight=0.4`, the position bias analysis shows
the composite score moves WRs up ~17 spots and RBs down ~7 spots relative to pure VOR,
bringing distributions much closer to real draft consensus while retaining VOR's scarcity
and roster-need intelligence.

**Example: Round 1 pick selection with `balanced` strategy**

```python
# State: draft just started, 12-team half PPR, team 1's first pick

# Pure VOR top 3 (RB-heavy): Saquon Barkley, Derrick Henry, Bijan Robinson
# ADP top 3 (ECR):           Saquon Barkley, CeeDee Lamb, Justin Jefferson

# With adp_weight=0.4 (12 teams, 654 available players):
#   Saquon:    VOR rank 1  (score 1.000) + ADP rank 7  (score 0.991) → composite 0.996
#   CeeDee:    VOR rank 33 (score 0.951) + ADP rank 3  (score 0.997) → composite 0.970
#   Jefferson: VOR rank 22 (score 0.967) + ADP rank 4  (score 0.995) → composite 0.978
#   Henry:     VOR rank 2  (score 0.998) + ADP rank 20 (score 0.971) → composite 0.987

# Result: Saquon still #1 (dominant on both signals). WRs now appear in the top 5
# (vs. pure VOR where they would be ranked ~20-40). Draft looks realistic.
```

### 5. Configuration (`config.py`)

```python
# config.py

# Monte Carlo parameters
MC_NUM_SIMULATIONS = 1000
MC_SIMULATION_DEPTH = 5  # Rounds to simulate ahead
MC_PARALLEL_WORKERS = 4  # CPU cores for parallel simulation

# ── VOR calculation parameters ────────────────────────────────────────────────
# Used by DynamicVORCalculator (human recommendations — no ADP influence).
# Formula: dynamic_vor = base_vor * scarcity * need * uncertainty_adj * tier_urgency
#
# Scarcity weights calibrated via Petersen methodology + empirical simulation testing:
# - RB/WR both 1.5 (balanced early-round value)
# - TE 1.6 (scarce after top tier)
# - QB 1.3 (deep position, "wait on QB" strategy viable)
# - K/DST 0.3 (inverse scarcity — value DROPS as more are drafted; streaming positions)
POSITION_SCARCITY_WEIGHTS = {
    "QB":  1.3,
    "RB":  1.5,
    "WR":  1.5,
    "TE":  1.6,
    "K":   0.3,
    "DST": 0.3,
}

ROSTER_NEED_WEIGHT    = 0.6   # Boost for unfilled starting slots
ROSTER_FILLED_PENALTY = 0.4   # Penalty when all starting slots are filled
ROSTER_EXCESS_PENALTY = 0.15  # Per-extra-player penalty beyond starters

# Need normalization: max starting slots any position can have (RB/WR with FLEX = 3).
# QB need = 1 + (1 * 0.6 / 3.0) = 1.2; RB need = 1 + (3 * 0.6 / 3.0) = 1.6
NEED_NORMALIZATION = 3.0

# Position-specific hard caps (total players, starting + bench).
# Applied after progressive excess penalties to absolutely prevent hoarding.
POSITION_HARD_CAPS = {
    "QB": 3,   # 1 starter + 2 bench max
    "RB": 7,   # 3 starting slots (RB1, RB2, FLEX) + 4 bench max
    "WR": 7,   # 3 starting slots (WR1, WR2, FLEX) + 4 bench max
    "TE": 3,   # 2 starting slots (TE1, FLEX-share) + 1 bench max
}

# Tier urgency boost: rewards picking players who are uniquely scarce in their tier.
# Formula: urgency = 1 + (tier_gap / tier_size) * TIER_URGENCY_WEIGHT
# Example: Chase alone in WR Tier 1 (28% gap) → urgency = 1 + 0.28/1 * 1.5 = 1.42
# Example: Allen + Jackson in QB Tier 1 of 2 (17% gap) → urgency = 1.13
# Example: Saquon in RB Tier 1 of 23 (24% gap) → urgency = 1.016
TIER_GAP_THRESHOLD  = 0.15   # % VOR drop between adjacent players = tier boundary
TIER_URGENCY_WEIGHT = 1.5

# Position uncertainty (Harvard study R² values — higher = less predictable)
POSITION_UNCERTAINTY = {
    "QB":  0.20,   # R²=0.80 → most predictable
    "TE":  0.21,   # R²=0.79 → very predictable
    "WR":  0.56,   # R²=0.44 → moderate uncertainty
    "RB":  0.97,   # R²=0.03 → highly unpredictable
    "K":   0.70,
    "DST": 0.70,
}

EARLY_ROUND_THRESHOLD = 3    # Rounds 1-3: penalize uncertainty (favor safe picks)
LATE_ROUND_THRESHOLD  = 10   # Round 10+: reward uncertainty (favor upside)

# ── Computer drafter parameters ───────────────────────────────────────────────
# ADP-blended composite scoring for realistic AI opponents.
# Human recommendations use pure VOR; computer opponents blend VOR + ADP signal.
# The ADP signal is player['overall_rank'] (FantasyPros ECR) — already in the
# player JSON from the data pipeline. No new data source is needed.

COMPUTER_STRATEGY            = "balanced"  # Default for all computer teams
COMPUTER_PERSONALITY_VARIANCE = 0.05       # +/- 5% noise for vor_only/contrarian

# Default ADP blend weight (0.0 = pure VOR, 1.0 = pure ADP)
COMPUTER_ADP_WEIGHT = 0.4    # 60% VOR + 40% ADP → realistic human-like drafting

# Per-strategy ADP blend weights.
# ComputerDrafter.__init__ looks up strategy name here when no explicit
# adp_weight is provided.
ADP_BLEND_STRATEGIES = {
    "vor_only":   0.0,   # Pure dynamic VOR (optimal but RB-heavy)
    "balanced":   0.4,   # 60% VOR + 40% ADP (default — realistic)
    "consensus":  0.7,   # 30% VOR + 70% ADP (consensus follower)
    "contrarian": 0.0,   # Pure VOR + noise=0.15 (exploits ADP inefficiencies)
}

# ── Performance tuning ────────────────────────────────────────────────────────
CANDIDATE_POOL_SIZE = 15  # Top N players to run Monte Carlo simulations on

# Adaptive simulation depths
SIMULATION_DEPTH_BY_ROUND = {
    "early": 5,   # Rounds 1-3
    "mid":   3,   # Rounds 4-9
    "late":  2,   # Rounds 10+
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

### ADP Blend Tests

```python
# test_computer_drafter.py

def test_blended_score_uses_overall_rank():
    """ADP score must derive from player['overall_rank'], not from VOR."""
    vor_calc = DynamicVORCalculator(scoring_format="half_ppr", league_size=12)
    computer = ComputerDrafter(vor_calculator=vor_calc, strategy="balanced")

    # Player A: weak VOR but top ADP rank
    player_a = _make_player("a", "WR", vor_half_ppr=5.0, overall_rank=1)
    # Player B: strong VOR but poor ADP rank
    player_b = _make_player("b", "RB", vor_half_ppr=80.0, overall_rank=200)

    available = [player_a, player_b]
    vor_results = {
        "a": VORResult("a", 5.0, 5.0, 1.0, 1.0, "WR", 1),
        "b": VORResult("b", 80.0, 80.0, 1.0, 1.0, "RB", 1),
    }
    scores = computer._compute_blended_scores(available, vor_results)

    # With adp_weight=0.4 the ADP boost for player_a shrinks the raw gap
    vor_only_gap = 80.0 - 5.0       # 75 pts if scoring raw VOR
    blended_gap = abs(scores["b"] - scores["a"])
    assert blended_gap < 0.5        # Rank-fused gap is in 0-1 space, much smaller


def test_vor_only_strategy_ignores_adp():
    """adp_weight=0.0 means composite is determined solely by VOR rank."""
    vor_calc = DynamicVORCalculator(scoring_format="half_ppr", league_size=12)
    computer = ComputerDrafter(vor_calculator=vor_calc, strategy="vor_only")
    assert computer.adp_weight == 0.0
    assert computer.noise_factor == 0.0


def test_contrarian_strategy_has_noise():
    """contrarian strategy sets noise_factor=0.15 and adp_weight=0.0."""
    vor_calc = DynamicVORCalculator(scoring_format="half_ppr", league_size=12)
    computer = ComputerDrafter(vor_calculator=vor_calc, strategy="contrarian")
    assert computer.adp_weight == 0.0
    assert computer.noise_factor == 0.15


def test_consensus_strategy_adp_weight():
    """consensus strategy must use adp_weight=0.7."""
    vor_calc = DynamicVORCalculator(scoring_format="half_ppr", league_size=12)
    computer = ComputerDrafter(vor_calculator=vor_calc, strategy="consensus")
    assert computer.adp_weight == 0.7


def test_missing_overall_rank_falls_back_gracefully():
    """Players without overall_rank should be treated as last (rank = total)."""
    vor_calc = DynamicVORCalculator(scoring_format="half_ppr", league_size=12)
    computer = ComputerDrafter(vor_calculator=vor_calc, strategy="balanced")

    player_no_rank = _make_player("x", "QB", vor_half_ppr=30.0)
    player_no_rank.pop("overall_rank", None)

    available = [player_no_rank]
    vor_results = {"x": VORResult("x", 30.0, 30.0, 1.0, 1.0, "QB", 1)}
    scores = computer._compute_blended_scores(available, vor_results)

    assert isinstance(scores["x"], float)  # Must not raise


def test_all_strategies_produce_legal_picks(draft_state_fixture):
    """All four strategies must return a valid player_id from the available pool."""
    vor_calc = DynamicVORCalculator(scoring_format="half_ppr", league_size=12)
    available_ids = {p["player_id"] for p in draft_state_fixture.available_list}

    for strategy in ["vor_only", "balanced", "consensus", "contrarian"]:
        computer = ComputerDrafter(vor_calculator=vor_calc, strategy=strategy)
        pick = computer.make_pick(
            draft_state_fixture, draft_state_fixture.available_list, team_id=0
        )
        assert pick in available_ids, f"Strategy {strategy!r} returned invalid pick"
```

### Performance Tests

```python
import time

def test_recommendation_performance():
    """Ensure recommendations complete within time limit."""
    start = time.time()
    recommendations = recommender.recommend_picks(
        large_draft_state,
        many_available_players,
        num_recommendations=5
    )
    elapsed = time.time() - start
    assert elapsed < 2.0  # Must complete in under 2 seconds


def test_computer_pick_performance():
    """Computer pick (balanced strategy) must complete within 0.5 seconds."""
    vor_calc = DynamicVORCalculator(scoring_format="half_ppr", league_size=12)
    computer = ComputerDrafter(vor_calculator=vor_calc, strategy="balanced")

    start = time.time()
    pick = computer.make_pick(large_draft_state, many_available_players, team_id=0)
    elapsed = time.time() - start

    assert elapsed < 0.5
    assert pick is not None
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
- **Version**: 1.1
- **Last Updated**: 2026-02-21
- **Status**: Updated for M9 ADP-Blended Computer Drafter
