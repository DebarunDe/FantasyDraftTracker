# Fantasy Draft Tracker

A fantasy football draft assistant with a statistical analysis pipeline, dynamic value-over-replacement (VOR) calculations, Monte Carlo simulation, and both a web-based and CLI interface. It supports simulation drafts (where the tool auto-drafts computer teams) and manual tracking drafts (where you log picks from a real-life draft).

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Overview](#architecture-overview)
3. [Data Pipeline](#data-pipeline)
   - [Ingestion](#ingestion)
   - [Cleaning](#cleaning)
   - [Transformation](#transformation)
   - [Baseline VOR Calculation](#baseline-vor-calculation)
   - [Pipeline Output](#pipeline-output)
4. [Dynamic VOR System](#dynamic-vor-system)
   - [The Core Formula](#the-core-formula)
   - [Scarcity Multiplier](#scarcity-multiplier)
   - [Need Multiplier](#need-multiplier)
   - [Uncertainty Adjustment](#uncertainty-adjustment)
   - [Tier Urgency](#tier-urgency)
   - [K/DST Special Handling](#kdst-special-handling)
   - [Hard Caps and Position Hoarding Prevention](#hard-caps-and-position-hoarding-prevention)
   - [QB Streaming Discount](#qb-streaming-discount)
5. [Monte Carlo Simulation](#monte-carlo-simulation)
   - [Algorithm](#algorithm)
   - [Computer Team Behavior](#computer-team-behavior)
   - [Performance Optimizations](#performance-optimizations)
6. [Draft Manager](#draft-manager)
   - [Draft State](#draft-state)
   - [Draft Rules and Validation](#draft-rules-and-validation)
   - [Roster Slot Assignment](#roster-slot-assignment)
   - [Snake Draft Order](#snake-draft-order)
   - [Traded Picks](#traded-picks)
   - [State Persistence](#state-persistence)
7. [Pick Recommender](#pick-recommender)
8. [Computer Drafter](#computer-drafter)
9. [Web Application](#web-application)
   - [Backend (FastAPI)](#backend-fastapi)
   - [Session Management](#session-management)
   - [WebSocket Events](#websocket-events)
   - [Frontend (React)](#frontend-react)
10. [CLI Interface](#cli-interface)
11. [Running the Application](#running-the-application)
    - [Dependencies](#dependencies)
    - [Run the Web App](#run-the-web-app)
    - [Run the CLI](#run-the-cli)
    - [Run the Data Pipeline](#run-the-data-pipeline)
12. [Adding a New Year of Data](#adding-a-new-year-of-data)
13. [Running Tests](#running-tests)
14. [Sources](#sources)

---

## Project Overview

Fantasy Draft Tracker is built around a core insight: drafting well in fantasy football requires understanding not just player projections, but how value changes as the draft progresses. A running back's worth at pick 5 is completely different from their worth at pick 55, because the pool of available replacements has shrunk.

The tool models this using a two-layer VOR system:

- **Baseline VOR** is computed once from raw projections before the draft begins. It answers: how much better is this player than the worst starter at his position that a team would be forced to use?
- **Dynamic VOR** is recomputed on every pick. It adjusts the baseline using current draft state: how many of this position are already drafted, how many empty starting slots does your team have, where is this player in his positional tier, and how uncertain is his projection?

On top of that, a Monte Carlo engine simulates hundreds of possible futures for each candidate pick to estimate which player produces the highest expected team score by draft end.

---

## Architecture Overview

```
Raw FantasyPros CSVs (5 files per year)
        |
        v
[Data Pipeline]
  ingestion.py -> cleaning.py -> transformation.py -> vor_calculation.py
        |
        v
data/processed/players_{year}.json
        |
        v
[Draft Session]
  DraftInitializer loads JSON into DraftState
        |
        v
  Per-pick loop:
    DynamicVORCalculator  -->  VOR multipliers for every available player
    MonteCarloSimulator   -->  Simulate 200 futures per top-15 candidate
    PickRecommender       -->  Rank + explain top picks
    DraftController       -->  Execute and validate pick
    StatePersistence      -->  Save to data/drafts/{draft_id}.json
        |
        v
  WebSocket broadcast to React frontend  OR  Rich CLI display
```

Key source directories:

| Path | Contents |
|---|---|
| `src/data_pipeline/` | CSV ingestion, cleaning, transformation, VOR |
| `src/draft_manager/` | Draft state, rules, controller, persistence |
| `src/simulation_engine/` | Dynamic VOR, Monte Carlo, recommender, computer drafter |
| `src/web/` | FastAPI app, routers, WebSocket, session manager |
| `src/ui/` | CLI app, setup wizard, Rich display |
| `frontend/src/` | React + TypeScript frontend |
| `tests/` | pytest test suite |
| `data/raw/{year}/` | FantasyPros CSV exports |
| `data/processed/` | Pipeline output JSON |
| `data/drafts/` | Saved draft states |

---

## Data Pipeline

The pipeline is a linear five-stage process that converts raw FantasyPros CSV exports into a single unified JSON file used by the rest of the application. Run it with:

```bash
venv/bin/python -m src.data_pipeline.run_update [year] [data_dir]
```

### Ingestion

`src/data_pipeline/ingestion.py`

The pipeline reads five separate CSV files that FantasyPros exports for each position group:

| File | Contents |
|---|---|
| `rankings.csv` | Overall ECR rank, position rank, tier, bye week |
| `qb.csv` | QB passing and rushing projections |
| `flex.csv` | RB, WR, and TE projections combined |
| `k.csv` | Kicker projections (field goals, extra points) |
| `dst.csv` | Defense/Special Teams projections |

Several data quirks require position-aware parsing:

- **Duplicate column names in QB/FLEX files.** The `ATT`, `YDS`, and `TDS` columns appear twice (once for passing stats and once for rushing). pandas suffixes these with `_x` and `_y` automatically, and the ingestion layer maps them to explicit `pass_att`, `rush_att`, etc.
- **Comma-formatted numbers.** Projected points appear as strings like `"3,904.1"`. These are stripped and converted to floats.
- **Blank placeholder rows.** Some exports include blank rows between the header and data. These are dropped.
- **Position rank embedded in the position column.** The FLEX file represents a player's position rank within his position as a suffix on the position string (e.g., `"WR1"`, `"RB23"`). The ingestion layer splits these apart.
- **DST naming.** The `Player` column in `dst.csv` contains full team names (`"Philadelphia Eagles"`), not abbreviations. The `Team` column is blank. The pipeline uses the full team name as-is and normalizes it during cleaning.

### Cleaning

`src/data_pipeline/cleaning.py`

After ingestion, each DataFrame is cleaned independently before merging:

**Position extraction.** Strips the numeric suffix from FLEX position strings (`"WR3"` becomes position `"WR"`, rank `3`).

**Team standardization.** Maps 32 variations of team names (full names, abbreviations, alternate spellings) to a canonical two- or three-letter code. DST full team names like `"Philadelphia Eagles"` map to `"PHI"`.

**Player name normalization.** Strips surrounding quotes, normalizes unicode apostrophes and dashes, and standardizes spacing. Name suffixes (`Jr.`, `Sr.`, `III`, `II`, `IV`, `V`) are preserved exactly because they are needed to distinguish players like Marvin Harrison (retired WR) from Marvin Harrison Jr. (active WR).

**Two-pass suffix handling for merging.** When merging projections against rankings, exact name matches are attempted first. Any unmatched rows are then retried with suffixes stripped from both sides. This prevents false negatives (e.g., one file has `"James Cook"`, another has `"James Cook III"`) while avoiding false positives (e.g., merging a player with his namesake parent).

### Transformation

`src/data_pipeline/transformation.py`

The five cleaned DataFrames are merged into a single unified table:

1. **Merge projections.** QB, FLEX, K, and DST are combined on player name and position.
2. **Scoring variants.** FantasyPros exports Full PPR projected points by default. Standard and Half-PPR variants are derived:
   - `FPTS_Standard = FPTS_FullPPR - Receptions`
   - `FPTS_HalfPPR = FPTS_FullPPR - (Receptions * 0.5)`
3. **Rankings merge.** The overall rankings CSV (ECR rank, tier, bye week) is merged onto the projections using the two-pass strategy described above. Players that appear in projections but not rankings receive `Overall_Rank = 999` and `Tier = 99`.
4. **Player ID generation.** A stable identifier is generated for each player in the format `{normalized_name}_{position}_{team}` (e.g., `jamarr_chase_wr_cin`). Collisions from players sharing names are resolved with a numeric suffix.

Two players (`Scott Matlock`, `Ben VanSumeren`) have unrecognized positions in the FLEX CSV and are filtered out during this stage.

### Baseline VOR Calculation

`src/data_pipeline/vor_calculation.py`

Value Over Replacement (VOR) measures how much a player's projected points exceed the projected points of the worst starter at his position that a team would be forced to start. The baseline VOR is computed once from raw projections before any picks are made.

**Replacement level calculation:**

The replacement player index is determined by estimating how many starters at each position exist across the league. A per-team weight is multiplied by league size:

| Position | Per-team weight | Replacement index (12-team) |
|---|---|---|
| QB | 1.5 | 18 |
| RB | 2.33 | 28 |
| WR | 3.4 | 41 |
| TE | 1.2 | 14 |
| K | 0.75 | 9 |
| DST | 0.75 | 9 |

RB and WR weights are higher than their raw starting slot counts because FLEX eligibility effectively increases demand.

**Baseline averaging.** To make the replacement level more robust against projection noise, the pipeline averages the projected points of the player at the replacement index with the players ranked one above and one below him (Petersen methodology). This prevents a single outlier projection from distorting the entire position's VOR scale.

**Three scoring variants.** Baseline VOR is computed separately for Standard, Half-PPR, and Full-PPR scoring, using the corresponding projected points column for each.

`VOR = player_projected_points - replacement_level_projected_points`

Players at or below replacement level receive negative VOR values, which is correct: they represent negative surplus value relative to a freely available waiver pickup.

Note: `float('nan')` is truthy in Python. The pipeline explicitly uses `math.isnan()` checks when working with FPTS to prevent NaN values from propagating into VOR calculations.

### Pipeline Output

The pipeline writes `data/processed/players_{year}.json` and updates a `players_latest.json` symlink. The structure is:

```json
{
  "metadata": {
    "version": "1.0",
    "generated_at": "2025-08-01T12:00:00",
    "season": 2025,
    "total_players": 654
  },
  "players": [
    {
      "player_id": "jamarr_chase_wr_cin",
      "name": "Ja'Marr Chase",
      "position": "WR",
      "team": "CIN",
      "bye_week": 9,
      "overall_rank": 2,
      "projections": {
        "standard": 150.5,
        "half_ppr": 165.2,
        "full_ppr": 179.9
      },
      "baseline_vor": {
        "standard": 68.5,
        "half_ppr": 83.2,
        "full_ppr": 98.0
      },
      "stats": { ... }
    }
  ]
}
```

---

## Dynamic VOR System

`src/simulation_engine/vor_calculator.py`

The dynamic VOR system is the core analytical engine of the draft assistant. It recalculates every player's value from scratch on every pick, accounting for the current state of the draft: which players are gone, how rosters look, and where a player sits relative to his positional peers.

### The Core Formula

```
dynamic_vor = base_vor x scarcity x need x uncertainty_adj x tier_urgency
```

Each multiplier is independent and captures a different dimension of draft value. The formula is applied to every available player on every pick, producing a ranked list that updates continuously as the draft progresses.

### Scarcity Multiplier

Scarcity models the depletion of positional depth as the draft proceeds.

```
drafted_pct = drafted_at_position / (starting_slots x league_size)
```

For skill positions (QB, RB, WR, TE):

```
scarcity = 1.0 + (drafted_pct x weight)
```

As more players at a position are taken, the remaining available players become relatively more scarce, increasing their value. The weights reflect how quickly positional depth degrades:

| Position | Scarcity weight |
|---|---|
| QB | 0.8 |
| RB | 1.5 |
| WR | 1.5 |
| TE | 1.6 |

TE has the highest weight because elite tight ends (top 3-5) are dramatically better than the streaming tier, so the talent drop-off is steep and fast. QB has the lowest weight because there are 30+ viable starting quarterbacks each season.

For K and DST, scarcity is inverted because these positions are interchangeable week-to-week. As more kickers and defenses are taken off the board, the remaining ones are not more valuable; they are the same:

```
scarcity (K/DST) = max(1.0 - (drafted_pct x 0.3), 0.1)
```

### Need Multiplier

Need captures how urgently a specific team needs a player at a given position, based on their current roster construction.

```
empty_slots = total_starting_slots - filled_starting_slots
```

If the team has unfilled starting slots at the position:

```
need = 1.0 + (empty_slots x 0.6 / max_starting_slots)
```

The normalization by `max_starting_slots` ensures positions with more starting slots (RB with 2+FLEX, WR with 2+FLEX) receive proportionally larger boosts than single-starter positions (QB, TE, K, DST).

If all starting slots are filled (player would go to bench):

```
need = 1.0 - 0.4 - (excess_count x excess_penalty)
```

The bench penalty (0.4) applies to all positions when starting slots are full. The excess penalty stacks for each player beyond the starting lineup:

- Excess players 1-2: penalty of 0.15 per player (reasonable bench depth)
- Excess players 3+: penalty of 0.40 per player (getting excessive)

For K and DST: 0.50 per excess player (strong deterrent against bench-hoarding kickers and defenses).

The need multiplier floor is 0.0 for K/DST and 0.01 for skill positions.

### Uncertainty Adjustment

Position uncertainty reflects how unpredictable a player's actual performance is relative to his projection. This is expressed as the R-squared value of projected vs. actual points for each position group, derived from multi-year empirical data.

| Position | R-squared (predictability) |
|---|---|
| QB | 0.20 (most predictable) |
| TE | 0.21 |
| WR | 0.56 |
| RB | 0.97 (highly unpredictable) |

The uncertainty adjustment varies by draft phase:

| Draft phase | Rounds | Uncertainty effect |
|---|---|---|
| Early | 1-3 | Penalty (x 0.5): avoid high-variance busts |
| Mid | 4-9 | Neutral (x 1.0) |
| Late | 10+ | Boost (x 1.5): favor upside |

In early rounds, high predictability (QB, TE) is rewarded because you are spending premium picks. In late rounds, uncertainty is rewarded because you are looking for upside plays who might outperform their projections.

### Tier Urgency

Tier urgency rewards players who are uniquely elite within their position's tier structure. If a player is the last member of an elite tier before a significant talent cliff, his value increases because missing him means settling for a materially worse player.

Tiers are detected using a two-pass algorithm on each position's VOR-sorted list:

1. **First pass (boundary detection).** A tier boundary exists between two adjacent players when the VOR gap between them exceeds 15% of the higher player's VOR. Each player is assigned a tier number.
2. **Second pass (propagation).** For each tier, compute the tier size (number of members) and the VOR gap to the next tier below. Propagate both values to all members of the tier.

The tier urgency multiplier:

```
tier_urgency = 1.0 + (gap_to_next_tier / tier_size x TIER_URGENCY_WEIGHT)
```

`TIER_URGENCY_WEIGHT = 1.0`

Example: If Ja'Marr Chase is alone in WR Tier 1 and the gap to Tier 2 is 28% of his VOR, and Tier 1 has 1 member, his tier urgency is `1.0 + (0.28 / 1 x 1.0) = 1.28`. A Tier 2 WR with 4 tier-mates and a 12% gap to Tier 3 would have `1.0 + (0.12 / 4 x 1.0) = 1.03`.

### K/DST Special Handling

Kickers and defenses receive additional draft-completion penalties to ensure they are not drafted until the final 20-35% of the draft, regardless of league size. This uses draft completion percentage rather than a fixed round threshold, so it works correctly across 8-team, 10-team, 12-team, and 14-team leagues.

```
draft_pct = picks_made / (total_roster_slots x league_size)
```

| Draft completion | K/DST dynamic_vor override |
|---|---|
| Less than 65% | -50.0 (effectively unpickable) |
| 65% to 80% | -5.0 (strongly discouraged) |
| 80% or more | Calculated VOR with 50% penalty applied |

Additionally, any K or DST player assigned to the bench (starting slot already filled) receives a streaming penalty of `-100.0 VOR`. Teams should never draft backup kickers or defenses; they should stream them on waivers weekly.

### Hard Caps and Position Hoarding Prevention

Hard caps prevent a team from drafting far more players at one position than they can meaningfully use. When a team's count at a position reaches or exceeds the cap, all remaining players at that position receive `dynamic_vor = -100.0`, making them effectively undraftable.

The cap is calculated as: `starting_slots + flex_eligibility + bench_allowance`

Default caps in a 12-team league with standard roster construction:

| Position | Starting slots | Bench allowance | Hard cap |
|---|---|---|---|
| QB | 1 | 1 | 2 |
| RB | 2 + 1 FLEX | 2 | 5 |
| WR | 2 + 1 FLEX | 2 | 5 |
| TE | 1 + 1 FLEX | 0 | 2 |
| K | 1 | 1 | 2 |
| DST | 1 | 1 | 2 |

The hard cap is applied after the full dynamic VOR formula is computed, to avoid a sign-flip bug that can occur when multiplying a negative base VOR by a negative need multiplier (which would incorrectly produce a positive final value).

### QB Streaming Discount

A flat 35% discount is applied to all QB dynamic VOR values:

```
dynamic_vor (QB) = calculated_dynamic_vor x 0.65
```

This reflects the BEER+ research finding that elite quarterbacks provide only approximately 1 additional point per game above a streaming-level QB. The discount does not mean QBs have no value; it calibrates their value correctly against the deep supply of viable starters and encourages teams not to spend early picks on a position where late-round alternatives are nearly as productive.

---

## Monte Carlo Simulation

`src/simulation_engine/monte_carlo.py`

The Monte Carlo simulator addresses a limitation of single-pick VOR analysis: the best player for this pick might not produce the best team by the end of the draft, because it depends on what other players are still available when you pick again. The simulator estimates expected team quality by simulating hundreds of complete draft continuations.

### Algorithm

For each pick recommendation request, the simulator evaluates the top 15 candidates by dynamic VOR:

```
For each candidate C in top-15 VOR candidates:
    total_score = 0
    For each simulation in 1..200:
        Assign C to the human team's current roster
        Simulate 5 rounds ahead:
            For each pick in those rounds:
                If computer team:
                    Pick from top-3 ADP available players, chosen randomly
                If human team:
                    Pick highest-VOR available player that fits roster
        Score the human team's optimal starting lineup using projected points
        total_score += lineup_score
    expected_score[C] = total_score / 200

Recommend candidates sorted by expected_score descending
mc_delta = expected_score[best] - expected_score[second_best]
```

The simulation depth is adaptive:
- Rounds 1-5: simulate 5 rounds ahead
- Rounds 6-10: simulate 3 rounds ahead
- Rounds 11+: simulate 2 rounds ahead

The simulator returns a `mc_delta` field for each candidate showing how many expected points it contributes above the next-best alternative. This is surfaced in the recommendation reasoning.

### Computer Team Behavior

Computer teams in the simulation pick by ADP (Overall Rank from FantasyPros). To introduce realistic variance rather than perfectly deterministic behavior, each computer team samples uniformly from the top 3 ADP-ranked available players rather than always taking rank 1. This creates branching in the simulation trees that better captures realistic draft outcomes.

The human team picks greedily by dynamic VOR in the simulation, taking the best available player that fits their roster. This is intentionally simple inside the simulation because it runs 200 times per candidate and must be fast.

### Performance Optimizations

The simulator runs 200 simulations for each of up to 15 candidates, meaning up to 3,000 simulations per recommendation request. Several optimizations keep this under 2 seconds:

- **Pre-sorted lists.** VOR-sorted and ADP-sorted player lists are built once per recommendation call and reused across all simulations.
- **Flat projections lookup.** A flat dictionary `{player_id: projected_points}` is built once per call. This avoids three levels of nested dictionary access in the `_score_team` function, which is called in the innermost loop.
- **Monotonic cursor.** The human team's pick selection advances a cursor through the pre-sorted VOR list rather than searching from the beginning on each pick. This reduces human-team pick selection from O(n) per pick to O(1) amortized.
- **Stateless design.** All simulation state is passed as parameters rather than stored on the object, enabling clean isolation between simulation runs and avoiding shared mutable state bugs.

---

## Draft Manager

`src/draft_manager/`

### Draft State

`src/draft_manager/draft_state.py`

`DraftState` is the single source of truth for an in-progress draft. All draft components read from and write to this object.

Key fields:

| Field | Type | Description |
|---|---|---|
| `draft_id` | `str` | UUID identifying this draft |
| `league_config` | `LeagueConfig` | League size, scoring format, roster slots |
| `draft_order` | `List[List[int]]` | 2D array: `draft_order[round][pick_in_round] = team_id` |
| `teams` | `List[TeamRoster]` | Each team's roster and pick history |
| `current_pick` | `int` | Absolute pick number, 1-indexed |
| `current_round` | `int` | Current round, 1-indexed |
| `current_team_id` | `int` | Team currently on the clock |
| `available_players` | `List[str]` | Player IDs not yet drafted |
| `all_picks` | `List[Pick]` | Full chronological pick history |
| `player_data` | `Dict[str, Dict]` | All player info loaded from pipeline JSON |

### Draft Rules and Validation

`src/draft_manager/draft_rules.py`

Every pick is validated through a chain of checks before being executed:

1. Is it this team's turn? (This check is skipped in `manual_tracker` mode, where the user enters picks for all teams.)
2. Does the player exist in the player database?
3. Is the player still available (not already drafted)?
4. Does the team have available roster slots for this position?

Validation order matters: player existence is checked before availability, because a non-existent player will also not appear in the available players list, and the two conditions produce different error messages.

### Roster Slot Assignment

`src/draft_manager/roster_validator.py`

When a pick passes validation, the roster validator determines which slot the player occupies on the team's roster:

1. Does the team have an open slot of the player's exact position? Fill it there.
2. Is the player FLEX-eligible (RB, WR, or TE) and is there an open FLEX slot? Fill the FLEX slot.
3. Otherwise, assign the player to the BENCH.

This priority ensures starting lineups are filled optimally before bench slots are used.

### Snake Draft Order

The draft order is pre-computed as a 2D list at draft initialization:

- `draft_order[round_index][pick_in_round] = team_id`
- Odd rounds (1, 3, 5, ...): teams 0 through N-1 in ascending order
- Even rounds (2, 4, 6, ...): teams N-1 through 0 in descending order

Pre-computing this eliminates runtime calculation and simplifies the `advance_to_next_pick()` logic to a simple 2D array lookup. A subtle ordering bug was fixed during development: `current_round` must be updated before calculating the team index for the new pick, otherwise the first pick of each even round uses the wrong direction.

### Traded Picks

`src/draft_manager/draft_state.py`

The draft supports pick trading between teams. Trades are specified before the draft begins and stored in `pick_trades: List[Dict]`, where each entry records `{from_team_id, round, to_team_id}`.

The 2D draft order array makes applying trades straightforward: the entry `draft_order[round][pick_index]` is simply changed from the original team's ID to the new team's ID. The `apply_pick_trade()` method on `DraftState` validates that both team IDs exist and that the round number is in bounds before applying.

Trades are entered in the setup wizard using a four-part syntax: `<team_A_number> <round_A> <team_B_number> <round_B>`, which swaps the two picks bidirectionally.

Saved drafts from before the traded picks feature used a 1D `List[int]` for draft order. These are auto-migrated to the 2D format on load without data loss.

### State Persistence

`src/draft_manager/state_persistence.py`

Drafts are serialized to JSON and saved at `data/drafts/{draft_id}.json`. The draft state is saved automatically after every pick. The persistence layer handles:

- `save_draft(draft_state)`: serialize all dataclasses to JSON
- `load_draft(draft_id)`: deserialize from JSON, rebuild all dataclasses
- `list_saved_drafts()`: return metadata (team names, pick number, date) for all saved drafts
- `delete_draft(draft_id)`: remove the save file

---

## Pick Recommender

`src/simulation_engine/pick_recommender.py`

The pick recommender assembles outputs from the dynamic VOR calculator and Monte Carlo simulator into a ranked list of recommendations for the human drafter.

Flow:

1. Compute dynamic VOR for all available players via `DynamicVORCalculator`.
2. Sort by dynamic VOR descending.
3. If a Monte Carlo simulator is available, evaluate the top 15 by VOR through the simulator and re-rank by expected team score.
4. Generate reasoning text for each recommendation explaining:
   - Scarcity and need rationale
   - Tier status (last player in elite tier, etc.)
   - Monte Carlo advantage in expected points above the next candidate
   - Reach or Steal indicator vs. ADP (thresholds: 8 picks for label, 15 picks for "strong" designation)
5. Return the top N recommendations as `Recommendation` dataclass instances with fields including `dynamic_vor`, `mc_expected_score`, `mc_delta`, and `reasoning`.

---

## Computer Drafter

`src/simulation_engine/computer_drafter.py`

The computer drafter makes picks for AI-controlled teams during simulation drafts. It uses a composite scoring system that blends dynamic VOR with ADP to produce realistic human-like draft behavior.

```
composite_score = (1 - adp_weight) x normalized_vor + adp_weight x normalized_adp
```

Available strategies:

| Strategy | ADP weight | Behavior |
|---|---|---|
| `vor_only` | 0.0 | Pure VOR, mathematically optimal, RB-heavy in early rounds |
| `balanced` | 0.4 | 60% VOR, 40% ADP; realistic human-like drafting |
| `consensus` | 0.7 | 30% VOR, 70% ADP; closely follows expert consensus rankings |
| `contrarian` | 0.0 + noise | Pure VOR with ±15% random noise; unpredictable |

Players with hard-cap violations (`dynamic_vor = -100.0`) are excluded from the computer drafter's candidate pool. All other position limit validation is shared with the human pick validation path.

---

## Web Application

### Backend (FastAPI)

`src/web/`

The FastAPI backend serves the React frontend and exposes a REST API plus a WebSocket endpoint.

**REST API routes:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/drafts` | Create a new draft |
| `GET` | `/api/drafts` | List all saved drafts |
| `GET` | `/api/drafts/{draft_id}` | Get full draft state |
| `DELETE` | `/api/drafts/{draft_id}` | Delete a saved draft |
| `POST` | `/api/drafts/{draft_id}/picks` | Execute a pick |
| `POST` | `/api/drafts/{draft_id}/advance` | Trigger computer pick chain |
| `GET` | `/api/drafts/{draft_id}/players` | List available players (filterable) |
| `GET` | `/api/drafts/{draft_id}/recommendations` | Get pick recommendations |

The `/api/drafts/{draft_id}/players` endpoint supports query parameters for `position`, `search` (fuzzy name match), and pagination.

In production, the frontend is built with `npm run build` and served statically by the FastAPI app under the root `/` path. In development, Vite runs on port 5173 and the FastAPI CORS middleware allows cross-origin requests from that origin.

### Session Management

`src/web/session_manager.py`

The session manager maintains an in-memory registry of active `DraftSession` objects. Each session bundles all components needed to operate a draft:

```python
@dataclass
class DraftSession:
    draft_state: DraftState
    controller: DraftController
    vor_calculator: DynamicVORCalculator
    computer_drafter: ComputerDrafter
    mc_simulator: MonteCarloSimulator
    recommender: PickRecommender
    persistence: StatePersistence
    lock: asyncio.Lock
```

The `asyncio.Lock` on each session prevents concurrent pick mutations. If two HTTP requests arrive simultaneously for the same draft (e.g., a human pick and a timer-triggered auto-pick), one waits while the other completes.

If the server restarts, sessions are rebuilt from disk on the next request via `load_or_create(draft_id)`.

Computer picks auto-advance via an asyncio task with an 800ms delay between picks, simulating thinking time. This task is spawned after any pick that leaves a computer team on the clock.

### WebSocket Events

`src/web/websocket/`

The WebSocket endpoint at `/ws/{draft_id}` streams real-time draft events to all connected clients. The connection is server-push only; clients do not send messages over the WebSocket.

Events:

| Event type | When emitted |
|---|---|
| `pick_made` | After any pick (human or computer) is executed |
| `computer_pick` | As each computer pick in a chain completes |
| `draft_complete` | When the last pick of the last round is made |

The connection manager maintains a set of connected WebSocket clients per draft ID and broadcasts to all of them on each event.

### Frontend (React)

`frontend/src/`

The frontend is a React 19 + TypeScript 5.9 application built with Vite.

**Routes:**

| Path | Component | Description |
|---|---|---|
| `/` | `LandingPage` | Home screen with saved draft list |
| `/new` | `SetupWizard` | Multi-step draft configuration |
| `/draft/:draftId` | `DraftBoard` | Active draft interface |

**Draft board layout:**

The draft board is the main interface during a simulation or manual tracking session. It consists of:

- `DraftHeader`: current round, pick number, team on the clock, and countdown timer
- `DraftGrid`: chronological pick history displayed as a grid (rounds x teams)
- `SidePanel`: tabbed panel containing:
  - `AvailablePlayers`: searchable, filterable list of remaining players
  - `RecommendationsPanel`: top pick suggestions with VOR and MC scores
  - `RosterPanel`: current human team's roster by position slot
- `PickClock`: visual countdown timer; triggers auto-pick on expiration (simulation mode)

A responsive `MobileDraftBoard` layout reflows these components for narrow screens.

The frontend connects to the WebSocket on draft load and updates the board state on each incoming event without requiring a full page reload.

**Setup wizard steps:**

1. Draft mode (simulation vs. manual tracker)
2. League configuration (team count, scoring format, roster slots)
3. Team names
4. Pick trades (optional)
5. Confirmation with draft order preview

---

## CLI Interface

`src/ui/cli.py`

Entry point: `python -m src.ui.cli`

The CLI provides a full terminal interface using the Rich library for formatted output.

**Available commands during a draft:**

| Command | Description |
|---|---|
| `a` / `available` | Show available players (filterable by position) |
| `r` / `roster` | Show your current team's roster |
| `s` / `search` | Search for a specific player by name |
| `rec` | Show pick recommendations |
| `b` / `board` | Show full draft board (all picks to date) |
| `compare` | Compare two teams' rosters side by side |
| `export` | Export draft to CSV |
| `save` | Manually save draft state |
| `sim` | Simulate the rest of the draft (simulation mode only) |
| `h` / `help` | Show command list |
| `q` / `quit` | Quit the application |

**Draft modes:**

In `simulation` mode, the CLI auto-drafts computer teams and prompts the human drafter for their picks. Recommendations are generated before each human pick.

In `manual_tracker` mode, the user enters all picks for all teams. This is designed for tracking a live draft happening on another platform (e.g., a league's official draft tool). Recommendations are shown only when it is the human team's turn. The `sim` command is disabled in this mode.

The CLI supports resuming saved drafts and deleting saved drafts from the startup menu. Drafts are auto-saved after every pick.

---

## Running the Application

### Dependencies

**Python (3.13):**
```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
```

**Node (20+):**
```bash
cd frontend && npm install
```

### Run the Web App

**Development (two terminals):**

Terminal 1 — Backend:
```bash
venv/bin/python -m uvicorn src.web.app:app --reload
```

Terminal 2 — Frontend with hot reload:
```bash
cd frontend && npm run dev
```

Open `http://localhost:5173` in your browser.

**Production (single process):**
```bash
cd frontend && npm run build
cd ..
venv/bin/python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

### Run the CLI

```bash
venv/bin/python -m src.ui.cli
```

### Run the Data Pipeline

```bash
venv/bin/python -m src.data_pipeline.run_update [year] [data_dir]
```

Example:
```bash
venv/bin/python -m src.data_pipeline.run_update 2025 data/raw/2025
```

---

## Adding a New Year of Data

The pipeline is designed to work with FantasyPros CSV exports. To add a new season:

1. **Download the five CSV files from FantasyPros.** You need:
   - Overall ECR rankings
   - QB projections
   - FLEX (RB/WR/TE) projections
   - K projections
   - DST projections

   Export these as CSV files from the FantasyPros rankings and projections pages for the relevant season.

2. **Create the raw data directory for the new year:**
   ```bash
   mkdir -p data/raw/{year}
   ```

3. **Place the CSV files in the new directory.** The expected filenames are configured in `src/data_pipeline/config.py` under the `CSV_FILENAMES` mapping. By default:
   ```
   data/raw/{year}/rankings.csv
   data/raw/{year}/qb.csv
   data/raw/{year}/flex.csv
   data/raw/{year}/k.csv
   data/raw/{year}/dst.csv
   ```

4. **Run the pipeline:**
   ```bash
   venv/bin/python -m src.data_pipeline.run_update {year}
   ```

5. **Verify the output.** The pipeline will print summary statistics (player count, VOR range per position) and write `data/processed/players_{year}.json`. The `players_latest.json` symlink will be updated to point to the new file.

6. **Check for new team abbreviation or player name edge cases.** The cleaning layer's team standardization map (`src/data_pipeline/cleaning.py`) may need to be updated if any NFL teams have relocated or rebranded since the last export. Similarly, the suffix handling in the name normalization step may need adjustment if new players with common name suffixes are added.

**Note on the VOR baseline weights.** The replacement level weights (`QB: 1.5`, `RB: 2.33`, etc. in `src/data_pipeline/config.py`) were calibrated for standard 12-team leagues and should remain stable across seasons. If your league uses an unusual roster construction (e.g., 3 starting WRs, 2 FLEX slots), revisit these weights to ensure the replacement level reflects your league's actual roster demand.

---

## Running Tests

**Backend:**
```bash
venv/bin/python -m pytest tests/ -v
```

**Backend with coverage:**
```bash
venv/bin/python -m pytest tests/ --cov=src --cov-report=term-missing
```

**Skip slow Monte Carlo wall-clock tests (recommended for development):**
```bash
venv/bin/python -m pytest tests/ -m "not slow"
```

**Frontend:**
```bash
cd frontend && npm run test
```

**Frontend with coverage:**
```bash
cd frontend && npm run test -- --coverage
```

The test suite covers all pipeline stages (ingestion, cleaning, transformation, VOR), draft manager logic (pick validation, slot assignment, snake order, traded picks), the simulation engine (dynamic VOR formula components, Monte Carlo), and CLI workflows.

---

## Sources

The statistical methodology in this project draws from published research on fantasy football valuation:

**Value Over Replacement (VOR) methodology:**
- Petersen, B. "Value Over Replacement in Fantasy Football." The core VOR framework, including the baseline averaging technique (averaging ±1 rank around the replacement player to reduce noise sensitivity) and the per-position replacement level weights.

**QB streaming discount and positional scarcity:**
- BEER+ (Breaking Even Every Round) research on quarterback value in single-QB formats. The research finding that elite QBs provide approximately 1 additional point per game above a waiver-level QB justifies the 35% streaming discount applied to QB dynamic VOR.

**Position uncertainty and R-squared values:**
- Harvard Sports Analysis Collective studies on projection accuracy by position. The R-squared values used in the uncertainty adjustment (QB: 0.20, TE: 0.21, WR: 0.56, RB: 0.97) are derived from multi-year analyses of how well preseason projections predict actual season-ending points for each position group. The high RB uncertainty (0.97) reflects injury fragility, role changes, and the difficulty of predicting workload distribution. The low QB uncertainty (0.20) reflects the stability of starting quarterback opportunities.

**Tier-based drafting and scarcity weights:**
- Boris Chen's ADP tier analysis. The tier detection algorithm's 15% VOR gap threshold for tier boundaries, and the concept of rewarding players who are the last member of an elite tier before a significant talent cliff, are influenced by this work.

**Dynamic roster construction and FLEX value:**
- The RB weight adjustment upward from raw starting slots (from 2 to 2.33 per team) to account for FLEX eligibility follows the methodology in Petersen's VOR framework, which notes that RBs and WRs compete for FLEX slots and thus have higher aggregate roster demand than their dedicated starting slots alone suggest.
