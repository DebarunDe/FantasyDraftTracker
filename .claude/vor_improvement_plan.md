# VOR Calculation Improvement Plan

## Executive Summary

Based on analysis of the two provided sources, this plan proposes evidence-based improvements to both static and dynamic VOR calculations to align with academic research and industry best practices.

---

## Research Sources Summary

### Source 1: Fantasy Football Analytics Textbook (Petersen)
- **Link**: https://isaactpetersen.github.io/Fantasy-Football-Analytics-Textbook/
- **Key Findings**:
  - VOR Formula: `Player Projected Points − Replacement-Level Player Projected Points = VOR`
  - Replacement Level: "Pick-based threshold" — player at position rank equal to number drafted by pick 100
  - Baseline averaging: Average of players at rank N-1, N, and N+1 for robustness
  - Default baselines (10-team): QB=17, RB=35, WR=35, TE=13
  - Positional dropoff patterns:
    - **RBs**: Steepest initial dropoff (highest early value)
    - **TEs**: Significant scarcity after top tier
    - **QBs**: Steep decline after top 10
    - **K/DST**: Minimal dropoff (late-round targets)
  - Draft strategy: Early rounds prioritize highest VOR regardless of position; late rounds consider uncertainty/upside

### Source 2: Harvard Sports Analytics - "How Well Do Fantasy Stats Reflect Real Value?"
- **Link**: https://harvardsportsanalysis.org/2012/03/how-well-do-fantasy-stats-reflect-real-value/
- **Key Findings**:
  - Replacement level = "level of player that one could pick up from free agency or the waiver wire"
  - Fantasy value correlations with real performance (R² values):
    - **Overall**: 0.47 (0.53 PPR)
    - **QBs**: 0.80 (most predictable)
    - **TEs**: 0.79 (very predictable)
    - **WRs**: 0.44 (moderate uncertainty)
    - **RBs**: 0.03 (highly unpredictable!)
  - Implication: RB projections have massive variance; QB/TE projections are most reliable

---

## Current Implementation Analysis

### Static VOR (`src/data_pipeline/vor_calculation.py`)
**Current Approach**:
- Fixed baseline counts: QB=12, RB=36, WR=36, TE=12, K=12, DST=12
- Formula: `VOR = player_fpts - replacement_fpts`
- Replacement player = Nth ranked player where N is baseline count
- Hardcoded for 12-team leagues only

**Issues**:
1. ❌ Not league-size-dependent (won't work for 8-team or 10-team leagues)
2. ❌ No baseline averaging for robustness
3. ❌ Baseline counts don't match Petersen's pick-100 methodology
4. ❌ K/DST baselines too high (12 each) when sources recommend minimal value

### Dynamic VOR (`src/simulation_engine/vor_calculator.py`)
**Current Approach**:
- Multiplies static VOR by scarcity and need multipliers
- Scarcity: `1 + (drafted_pct * position_weight)`
  - Weights: QB=1.2, RB=1.5, WR=1.5, TE=1.5, K=0.5, DST=0.5
- Need: Three-tier system (empty boost / filled penalty / excess penalty)

**Issues**:
1. ⚠️ Scarcity weights not grounded in empirical data
2. ❌ No tier/dropoff detection for draft strategy
3. ❌ No uncertainty/variance consideration (RBs should have higher risk)
4. ⚠️ Need multiplier weights (0.5 boost, 0.3 penalty, 0.1 excess) are arbitrary

---

## Proposed Improvements

### Phase 1: Static VOR Enhancements

#### 1.1 League-Size-Dependent Baselines
**Rationale**: Petersen's methodology scales with league size and roster construction.

**Implementation**:
```python
def calculate_baseline_rank(position: str, league_size: int, roster_slots: Dict[str, int]) -> int:
    """
    Calculate replacement level as:
    (starters_per_team + flex_share + bench_buffer) * league_size

    Example for RB in 12-team, 2RB/1FLEX/6BENCH:
    - Starters: 2
    - FLEX share: ~0.33 (assume equal RB/WR/TE split)
    - Bench buffer: ~0.5 (half of bench typically RB/WR)
    - Total: (2 + 0.33 + 0.5) * 12 = 34 players
    """
    # Position-specific formulas
```

**Baselines Matrix** (for reference):

| Position | 8-team | 10-team | 12-team | 14-team |
|----------|--------|---------|---------|---------|
| QB       | 8-10   | 12-15   | 15-18   | 18-21   |
| RB       | 24-28  | 30-35   | 36-42   | 42-49   |
| WR       | 24-28  | 30-35   | 36-42   | 42-49   |
| TE       | 8-10   | 10-12   | 12-15   | 15-18   |
| K        | 4-6    | 6-8     | 8-10    | 10-12   |
| DST      | 4-6    | 6-8     | 8-10    | 10-12   |

#### 1.2 Baseline Averaging for Robustness
**Rationale**: Petersen recommends averaging ±1 rank to smooth out projection noise.

**Implementation**:
```python
# Instead of:
replacement_fpts = pos_df.iloc[repl_idx][fpts_col]

# Use:
repl_low = max(0, repl_idx - 1)
repl_high = min(len(pos_df) - 1, repl_idx + 1)
replacement_fpts = pos_df.iloc[repl_low:repl_high + 1][fpts_col].mean()
```

#### 1.3 Evidence-Based K/DST Devaluation
**Rationale**: Both sources indicate K/DST have minimal dropoff; current baselines overvalue them.

**Implementation**:
- Reduce K/DST baselines by ~50% (from 12 to 6-8 for 12-team)
- This will make most K/DST have negative VOR, correctly reflecting late-round value

### Phase 2: Dynamic VOR Enhancements

#### 2.1 Evidence-Based Scarcity Weights
**Rationale**: Align weights with documented dropoff curves from Petersen research.

**Current vs Proposed**:

| Position | Current | Proposed | Justification |
|----------|---------|----------|---------------|
| QB       | 1.2     | 1.3      | Steep drop after top 10 (Petersen) |
| RB       | 1.5     | 1.8      | Steepest initial dropoff (Petersen) |
| WR       | 1.5     | 1.4      | More depth, gentler decline (Petersen) |
| TE       | 1.5     | 1.6      | Scarcity after top tier (Petersen) |
| K        | 0.5     | 0.3      | Minimal dropoff (both sources) |
| DST      | 0.5     | 0.3      | Minimal dropoff (both sources) |

#### 2.2 Tier Detection and Gap Analysis
**Rationale**: Petersen emphasizes tier-based drafting; identify VOR gaps to avoid reaching.

**Implementation**:
```python
def identify_tiers(players_by_position: List, min_gap_pct: float = 0.15) -> List[int]:
    """
    Detect tier boundaries where VOR drops by >15% between adjacent players.

    Returns list of tier boundary indices.
    """
    tiers = []
    for i in range(len(players_by_position) - 1):
        vor_drop = (players[i].vor - players[i+1].vor) / players[i].vor
        if vor_drop > min_gap_pct:
            tiers.append(i)
    return tiers
```

**Use Case**: CLI can show tier boundaries in recommendations (e.g., "Last player in Tier 1")

#### 2.3 Position Uncertainty Metrics
**Rationale**: Harvard study shows RB projections are highly unreliable (R²=0.03 vs QB R²=0.80).

**Implementation**:
```python
POSITION_UNCERTAINTY = {
    "QB": 0.20,   # R²=0.80 → low uncertainty
    "TE": 0.21,   # R²=0.79 → low uncertainty
    "WR": 0.56,   # R²=0.44 → moderate uncertainty
    "RB": 0.97,   # R²=0.03 → very high uncertainty
    "K": 0.70,    # Moderate uncertainty (estimate)
    "DST": 0.70,  # Moderate uncertainty (estimate)
}

def calculate_risk_adjusted_vor(base_vor: float, position: str, draft_round: int) -> float:
    """
    Late rounds: favor high-ceiling RBs despite uncertainty
    Early rounds: favor consistent QBs/TEs
    """
    uncertainty = POSITION_UNCERTAINTY[position]

    if draft_round <= 3:  # Early: penalize uncertainty
        return base_vor * (1 - uncertainty * 0.2)
    elif draft_round >= 10:  # Late: reward upside
        return base_vor * (1 + uncertainty * 0.15)
    else:
        return base_vor  # Mid-rounds: no adjustment
```

#### 2.4 Refined Need Multiplier
**Rationale**: Current weights (0.5 boost, 0.3 penalty) are arbitrary; calibrate to empirical draft outcomes.

**Proposed Adjustments**:
- Empty slot boost: 0.5 → 0.6 (stronger incentive to fill starters)
- Filled penalty: 0.3 → 0.4 (stronger disincentive for bench depth at expensive positions)
- Excess penalty: 0.1 → 0.15 (more aggressive penalty for 3rd/4th K/DST)
- Floor: 0.1 → 0.05 (allow steeper penalties for egregious picks)

---

## Implementation Plan

### Step 1: Static VOR Improvements
**Files to modify**:
- `src/data_pipeline/config.py` — Add league-size scaling formulas
- `src/data_pipeline/vor_calculation.py` — Implement averaging, league-size baselines

**Testing**:
- Update `tests/test_vor_calculation.py` for new baseline logic
- Verify 8-team, 10-team, 12-team, 14-team produce sensible baselines
- Confirm K/DST now have mostly negative VOR

**Expected Impact**:
- More accurate baselines for non-12-team leagues
- Smoother VOR curves (less noise)
- K/DST correctly valued as late-round picks

### Step 2: Dynamic VOR Enhancements
**Files to modify**:
- `src/simulation_engine/config.py` — Update scarcity weights, add uncertainty constants
- `src/simulation_engine/vor_calculator.py` — Add tier detection, uncertainty adjustment
- `src/simulation_engine/models.py` — Add `tier` and `uncertainty` fields to `VORResult`

**Testing**:
- Update `tests/test_dynamic_vor.py` for new weights
- Add tests for tier detection
- Add tests for uncertainty adjustments by draft round

**Expected Impact**:
- RBs regain slight edge in early rounds (scarcity 1.8 vs WR 1.4)
- K/DST stay deprioritized (scarcity 0.3)
- Late-round strategy favors high-upside RBs
- CLI can show tier boundaries to users

### Step 3: CLI Integration
**Files to modify**:
- `src/ui/display.py` — Show tier markers in recommendations
- `src/ui/cli.py` — Display uncertainty/risk for players

**New Features**:
- `[rec]` command shows tier boundaries: `"1. Player A (Tier 1 - last in tier)"`
- Player search shows uncertainty: `"RB12 - High variance (sleeper potential)"`

---

## Validation Criteria

### Quantitative Checks
1. ✅ 8/10/12/14-team leagues produce proportional baselines
2. ✅ RB baseline > WR baseline (reflects roster construction)
3. ✅ K/DST have lowest baselines (~50% of current)
4. ✅ Averaging reduces VOR volatility (lower std dev)
5. ✅ RB scarcity weight > WR scarcity weight
6. ✅ K/DST scarcity weights lowest (0.3)
7. ✅ Tier detection identifies 3-5 tiers per position in top 50

### Qualitative Checks
1. ✅ Early-round recommendations prioritize RBs/WRs over QBs (matches Petersen)
2. ✅ No recommendations for K/DST before round 10 (matches both sources)
3. ✅ Late-round recommendations include high-variance RBs (matches Harvard study)
4. ✅ User testing: 12-team mock draft produces realistic outcomes

---

## Risks and Mitigations

### Risk 1: Breaking Existing Tests
**Mitigation**: Update test expectations incrementally; maintain backward compatibility flag during development.

### Risk 2: User Confusion with New Metrics
**Mitigation**: Phase CLI changes; add tooltips/help text explaining tiers and uncertainty.

### Risk 3: Calibration Error
**Mitigation**: Use 2024-2025 ADP data to validate baseline ranks; run simulations against historical drafts.

---

## Timeline Estimate

- **Phase 1** (Static VOR): ~2-3 hours
  - Code changes: 1 hour
  - Testing: 1-2 hours

- **Phase 2** (Dynamic VOR): ~3-4 hours
  - Code changes: 2 hours
  - Testing: 1-2 hours

- **Phase 3** (CLI Integration): ~1-2 hours
  - Display updates: 1 hour
  - Manual testing: 1 hour

**Total**: ~6-9 hours of development

---

## User Decisions (Approved)

1. **League size priority**: ✅ All league sizes (8/10/12/14) calibrated equally
2. **Uncertainty strategy**: ✅ Configurable but defaults to research-based values
3. **Tier display**: ✅ `[rec]` shows tier boundaries by default; `[a]` shows top players without tiers
4. **Baseline source**: ✅ Use Petersen's baselines (no stable 2024-2025 ADP data available)
5. **K/DST handling**: ✅ Rely on VOR math (no hard rules)

---

## References

- Petersen, I. T. (2024). *Fantasy Football Analytics: Statistics, Prediction, and Empiricism Using R*. https://isaactpetersen.github.io/Fantasy-Football-Analytics-Textbook/
- Petersen, I. T. (2013). "Win Your Snake Draft: Calculating 'Value Over Replacement' using R". https://fantasyfootballanalytics.net/2013/04/win-your-snake-draft-calculating-value.html
- Fantasy Football Analytics (2024). "Winning Fantasy Football with Projections, Value Over Replacement, and Value-Based Drafting". https://fantasyfootballanalytics.net/2024/08/winning-fantasy-football-with-projections-value-over-replacement-and-value-based-drafting.html
- Harvard Sports Analysis Collective (2012). "How Well Do Fantasy Stats Reflect Real Value?" https://harvardsportsanalysis.org/2012/03/how-well-do-fantasy-stats-reflect-real-value/
