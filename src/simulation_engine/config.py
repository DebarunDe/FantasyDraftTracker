# Monte Carlo parameters
MC_NUM_SIMULATIONS = 1000
MC_SIMULATION_DEPTH = 5  # Rounds to simulate ahead
MC_PARALLEL_WORKERS = 4  # CPU cores for parallel simulation

# VOR calculation parameters
POSITION_SCARCITY_WEIGHTS = {
    "QB": 1.2,
    "RB": 1.5,
    "WR": 1.5,
    "TE": 1.5,
    "K": 0.5,
    "DST": 0.5,
}

ROSTER_NEED_WEIGHT = 0.5  # Boost for unfilled starting slots
ROSTER_FILLED_PENALTY = 0.3  # Penalty when all starting slots are filled (bench-only)
ROSTER_EXCESS_PENALTY = 0.1  # Further penalty per extra player beyond starters

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
    "mid": 3,     # Rounds 4-9
    "late": 2,    # Rounds 10+
}
