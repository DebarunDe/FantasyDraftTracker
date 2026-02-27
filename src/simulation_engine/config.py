# Monte Carlo parameters
# 200 simulations per candidate balances statistical quality and the <2s target
# latency for a full evaluate_candidates() call with CANDIDATE_POOL_SIZE=15
# candidates at early-round depth (5 rounds × 12 teams = 60 picks per sim).
# Increasing to 500-1000 improves convergence but risks exceeding 2 seconds on
# slower machines.
MC_NUM_SIMULATIONS = 200
MC_SIMULATION_DEPTH = 5  # Rounds to simulate ahead
MC_PARALLEL_WORKERS = 4  # CPU cores for parallel simulation

# VOR calculation parameters
# Scarcity weights tuned for realistic early-round balance:
# - RB: Steepest initial dropoff → 1.5 (reduced from 1.8 for balance)
# - WR: Increased to match RB → 1.5 (increased from 1.4 for better early-round value)
# - TE: Significant scarcity after top tier → 1.6
# - QB: Steep decline after top 10 → 1.3
# - K/DST: Minimal dropoff (late-round targets) → 0.3
POSITION_SCARCITY_WEIGHTS = {
    "QB": 1.3,
    "RB": 1.5,
    "WR": 1.5,
    "TE": 1.6,
    "K": 0.3,
    "DST": 0.3,
}

# Roster need multiplier weights (calibrated to empirical draft outcomes)
ROSTER_NEED_WEIGHT = 0.6  # Boost for unfilled starting slots
ROSTER_FILLED_PENALTY = 0.4  # Penalty when all starting slots are filled (bench-only)
ROSTER_EXCESS_PENALTY = 0.15  # Further penalty per extra player beyond starters

# Need normalization: max starting slots any position can have (RB/WR with FLEX = 3).
# Need boost scales as empty * ROSTER_NEED_WEIGHT / NEED_NORMALIZATION, so positions
# that need more players (RB/WR → 3 slots) get proportionally more need boost than
# single-slot positions (QB/TE → 1-2 slots). This pushes QBs into round 3+ in ADP.
NEED_NORMALIZATION = 3.0

# Position-specific hard caps on total players (starting + bench).
# Applied AFTER progressive excess penalties to absolutely prevent hoarding.
# RB/WR have 3 starting slots (2+FLEX) so cap at 7 (4 excess).
# QB/TE have 1-2 starting slots so cap tighter at 3 total.
# K/DST: 1 starting slot; cap at 2 to allow one streamer backup max.
POSITION_HARD_CAPS = {
    "QB": 3,   # 1 starter + 2 max bench depth
    "RB": 7,   # 3 starting + 4 bench max
    "WR": 7,   # 3 starting + 4 bench max
    "TE": 3,   # 2 starting (1 TE + FLEX share) + 1 bench
    "K": 2,    # 1 starter + 1 backup max
    "DST": 2,  # 1 starter + 1 backup max
}

# Position uncertainty (based on Harvard study R² values)
# Higher uncertainty = less predictable projections
# Used for risk-adjusted VOR in late rounds (favor high-upside players)
POSITION_UNCERTAINTY = {
    "QB": 0.20,   # R²=0.80 → most predictable
    "TE": 0.21,   # R²=0.79 → very predictable
    "WR": 0.56,   # R²=0.44 → moderate uncertainty
    "RB": 0.97,   # R²=0.03 → highly unpredictable!
    "K": 0.70,    # Moderate uncertainty (estimate)
    "DST": 0.70,  # Moderate uncertainty (estimate)
}

# Round thresholds for uncertainty-based adjustments
EARLY_ROUND_THRESHOLD = 3   # Rounds 1-3: penalize uncertainty
LATE_ROUND_THRESHOLD = 10   # Rounds 10+: reward upside

# Tier detection parameters
TIER_GAP_THRESHOLD = 0.15  # 15% VOR drop between adjacent players = tier boundary

# Tier urgency boost: rewards drafting players who are uniquely scarce within their tier.
# Applied as: urgency = 1 + (gap_to_next_tier / tier_size × TIER_URGENCY_WEIGHT)
# Example: Chase alone in WR Tier 1 (28% gap): urgency = 1 + 0.28/1 × 1.5 = 1.42
# Example: Allen + Jackson in QB Tier 1 of 2 (17% gap): urgency = 1 + 0.17/2 × 1.5 = 1.13
# Example: Saquon in RB Tier 1 of 23 (24% gap): urgency = 1 + 0.24/23 × 1.5 = 1.016
TIER_URGENCY_WEIGHT = 1.5

# ── Computer drafter parameters ───────────────────────────────────────────────
# ADP-blended composite scoring for realistic AI opponents.
# Human recommendations use pure VOR; computer opponents blend VOR + ADP signal.
# The ADP signal is player['overall_rank'] (FantasyPros ECR) — already in the
# player JSON from the data pipeline. No new data source is needed.

COMPUTER_STRATEGY            = "balanced"  # Default for all computer teams
COMPUTER_PERSONALITY_VARIANCE = 0.05       # Reserved for future use

# Default ADP blend weight (0.0 = pure VOR, 1.0 = pure ADP)
COMPUTER_ADP_WEIGHT = 0.4    # 60% VOR + 40% ADP → realistic human-like drafting

# Per-strategy ADP blend weights.
# ComputerDrafter.__init__ looks up strategy name here when no explicit
# adp_weight is provided.
ADP_BLEND_STRATEGIES = {
    "vor_only":   0.0,   # Pure dynamic VOR (optimal but RB-heavy)
    "balanced":   0.4,   # 60% VOR + 40% ADP (default — realistic)
    "consensus":  0.7,   # 30% VOR + 70% ADP (consensus follower)
    "contrarian": 0.0,   # Pure VOR + ±15% uniform noise (exploits ADP inefficiencies)
}

# Performance tuning
CANDIDATE_POOL_SIZE = 15  # Top N players to run MC simulations on

# Computer teams in MC simulation sample uniformly from the top K ADP-ranked
# available players instead of always picking #1.  This creates stochasticity
# so that each simulation run produces a different outcome — the core
# requirement for Monte Carlo averaging to be meaningful.
# K=3: realistic variance without excessive noise.
MC_COMPUTER_PICK_TOP_K = 3

# Adaptive simulation depths
SIMULATION_DEPTH_BY_ROUND = {
    "early": 5,   # Rounds 1-3
    "mid": 3,     # Rounds 4-9
    "late": 2,    # Rounds 10+
}
