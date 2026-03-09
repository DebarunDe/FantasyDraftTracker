# Monte Carlo parameters
# 200 simulations per candidate balances statistical quality and the <2s target
# latency for a full evaluate_candidates() call with CANDIDATE_POOL_SIZE=15
# candidates at early-round depth (5 rounds × 12 teams = 60 picks per sim).
# Increasing to 500-1000 improves convergence but risks exceeding 2 seconds on
# slower machines.
MC_NUM_SIMULATIONS = 200
MC_SIMULATION_DEPTH = 5  # Rounds to simulate ahead

# VOR calculation parameters
# Scarcity weights tuned for realistic early-round balance:
# - RB: Steepest talent cliff, no streaming option → 1.5
# - WR: Deep position but steep elite tier dropoff → 1.5
# - TE: Significant scarcity after top 3-5 tier → 1.6
# - QB: Reduced from 1.3 → 0.8: QB is the LEAST scarce skill position in 1-QB leagues
#       (30+ viable starters for 12 slots); BEER+ streaming methodology confirms lower weight
# - K/DST: Minimal dropoff (streaming-only positions) → 0.3
POSITION_SCARCITY_WEIGHTS = {
    "QB": 0.8,   # Reduced from 1.3: least positionally scarce skill position in 1-QB leagues
    "RB": 1.5,
    "WR": 1.5,
    "TE": 1.6,
    "K": 0.3,
    "DST": 0.3,
}

# QB streaming discount for single-QB leagues (BEER+ methodology).
# QBs are the most "streamable" position — viable waiver QBs score ~250-270 FPTS,
# making the elite-QB premium only ~1 PPG over a mid-tier streamer.
# Applied as a multiplier to QB dynamic VOR in DynamicVORCalculator.
# Effect: Allen moves from rank ~15 to ~19-22; Hurts from ~20 to ~30-35.
QB_STREAMING_DISCOUNT = 0.65

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
    "QB": 3,  # 1 starter + 2 max bench depth
    "RB": 7,  # 3 starting + 4 bench max
    "WR": 7,  # 3 starting + 4 bench max
    "TE": 3,  # 2 starting (1 TE + FLEX share) + 1 bench
    "K": 2,  # 1 starter + 1 backup max
    "DST": 2,  # 1 starter + 1 backup max
}

# Position uncertainty (based on Harvard study R² values)
# Higher uncertainty = less predictable projections
# Used for risk-adjusted VOR in late rounds (favor high-upside players)
POSITION_UNCERTAINTY = {
    "QB": 0.20,  # R²=0.80 → most predictable
    "TE": 0.21,  # R²=0.79 → very predictable
    "WR": 0.56,  # R²=0.44 → moderate uncertainty
    "RB": 0.97,  # R²=0.03 → highly unpredictable!
    "K": 0.70,  # Moderate uncertainty (estimate)
    "DST": 0.70,  # Moderate uncertainty (estimate)
}

# Round thresholds for uncertainty-based adjustments
EARLY_ROUND_THRESHOLD = 3  # Rounds 1-3: penalize uncertainty
LATE_ROUND_THRESHOLD = 10  # Rounds 10+: reward upside

# Tier detection parameters
TIER_GAP_THRESHOLD = 0.15  # 15% VOR drop between adjacent players = tier boundary

# Tier urgency boost: rewards drafting players who are uniquely scarce within their tier.
# Applied as: urgency = 1 + (gap_to_next_tier / tier_size × TIER_URGENCY_WEIGHT)
# Reduced from 1.5 → 1.0 to prevent over-inflation of solo-tier players (especially
# elite TEs like Kittle who sit alone in TE Tier 1 and were being pushed to round 1).
# At 1.0: Kittle urgency = 1 + 0.22/1 × 1.0 = 1.22 (rank ~20, correct for round 2)
# At 1.5: Kittle urgency = 1 + 0.22/1 × 1.5 = 1.33 (rank ~11, too early for round 1)
# Chase still ranks #1-2 since her high base VOR dominates regardless of urgency weight.
# Example: Chase alone in WR Tier 1 (26% gap): urgency = 1 + 0.26/1 × 1.0 = 1.26
# Example: Allen + Jackson in QB Tier 1 of 2 (17% gap): urgency = 1 + 0.17/2 × 1.0 = 1.09
# Example: Saquon in RB Tier 1 of 23 (24% gap): urgency = 1 + 0.24/23 × 1.0 = 1.01
TIER_URGENCY_WEIGHT = 1.0

# ── Computer drafter parameters ───────────────────────────────────────────────
# ADP-blended composite scoring for realistic AI opponents.
# Human recommendations use pure VOR; computer opponents blend VOR + ADP signal.
# The ADP signal is player['overall_rank'] (FantasyPros ECR) — already in the
# player JSON from the data pipeline. No new data source is needed.

COMPUTER_STRATEGY = "balanced"  # Default for all computer teams

# Default ADP blend weight (0.0 = pure VOR, 1.0 = pure ADP)
COMPUTER_ADP_WEIGHT = 0.4  # 60% VOR + 40% ADP → realistic human-like drafting

# Per-strategy ADP blend weights.
# ComputerDrafter.__init__ looks up strategy name here when no explicit
# adp_weight is provided.
ADP_BLEND_STRATEGIES = {
    "vor_only": 0.0,  # Pure dynamic VOR (optimal but RB-heavy)
    "balanced": 0.4,  # 60% VOR + 40% ADP (default — realistic)
    "consensus": 0.7,  # 30% VOR + 70% ADP (consensus follower)
    "contrarian": 0.0,  # Pure VOR + ±15% uniform noise (exploits ADP inefficiencies)
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
    "early": 5,  # Rounds 1-3
    "mid": 3,  # Rounds 4-9
    "late": 2,  # Rounds 10+
}
