"""CLI configuration constants."""

# Position colors for Rich markup
POSITION_COLORS = {
    "QB": "red",
    "RB": "green",
    "WR": "cyan",
    "TE": "yellow",
    "K": "magenta",
    "DST": "blue",
}

# Display limits
AVAILABLE_PLAYERS_DEFAULT_LIMIT = 25
RECENT_PICKS_DISPLAY_COUNT = 12
VOR_RECOMMENDATIONS_COUNT = 10
SEARCH_RESULTS_LIMIT = 20

# Scoring format display names
SCORING_DISPLAY_NAMES = {
    "standard": "Standard",
    "half_ppr": "Half PPR",
    "full_ppr": "Full PPR",
}

# Valid league sizes (must be even, 2-20)
VALID_LEAGUE_SIZES = [4, 6, 8, 10, 12, 14, 16, 18, 20]

# Commands recognized by the CLI
COMMANDS = {
    "a", "available",
    "r", "roster",
    "s", "search",
    "rec", "recommend",
    "h", "help",
    "q", "quit",
    "b", "board",
    "save",
    "sim", "simulate",
}
