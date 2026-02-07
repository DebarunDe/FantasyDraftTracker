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
    "DST": 1.0,
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
    "mid": 3,     # Rounds 4-9
    "late": 2,    # Rounds 10+
}
