"""Test how VOR adapts as draft progresses in different league sizes."""

import json

from src.simulation_engine.vor_calculator import DynamicVORCalculator

# Load player data
with open("data/processed/players_2025.json", "r") as f:
    data = json.load(f)
    all_players = data["players"]

roster_slots = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "K": 1,
    "DST": 1,
    "BENCH": 6,
}

print("=" * 120)
print("VOR ADAPTATION AS DRAFT PROGRESSES")
print("=" * 120)

# Test 12-team league at different draft stages
league_size = 12
calc = DynamicVORCalculator("half_ppr", league_size=league_size)

scenarios = [
    {
        "name": "Round 1, Pick 1 (Start)",
        "drafted_positions": {},
        "roster": {pos: [] for pos in roster_slots},
        "round": 1,
    },
    {
        "name": "Round 3, Pick 25 (After 24 picks: 16 RB, 6 WR, 2 QB)",
        "drafted_positions": {"RB": 16, "WR": 6, "QB": 2},
        "roster": {
            "QB": [],
            "RB": ["rb1"],
            "WR": ["wr1"],
            "TE": [],
            "FLEX": [],
            "K": [],
            "DST": [],
            "BENCH": [],
        },
        "round": 3,
    },
    {
        "name": "Round 6, Pick 61 (After 60 picks: 28 RB, 22 WR, 6 QB, 4 TE)",
        "drafted_positions": {"RB": 28, "WR": 22, "QB": 6, "TE": 4},
        "roster": {
            "QB": [],
            "RB": ["rb1", "rb2"],
            "WR": ["wr1", "wr2"],
            "TE": [],
            "FLEX": ["rb3"],
            "K": [],
            "DST": [],
            "BENCH": [],
        },
        "round": 6,
    },
    {
        "name": "Round 10, Pick 109 (After 108 picks: 40 RB, 36 WR, 14 QB, 12 TE, 6 K)",
        "drafted_positions": {"RB": 40, "WR": 36, "QB": 14, "TE": 12, "K": 6},
        "roster": {
            "QB": ["qb1"],
            "RB": ["rb1", "rb2"],
            "WR": ["wr1", "wr2"],
            "TE": ["te1"],
            "FLEX": ["wr3"],
            "K": [],
            "DST": [],
            "BENCH": ["rb3", "wr4"],
        },
        "round": 10,
    },
]

for scenario in scenarios:
    print(f"\n{scenario['name']}")
    print("-" * 120)

    vor_results = calc.calculate_dynamic_vor(
        available_players=all_players,
        drafted_positions=scenario["drafted_positions"],
        roster_slots=roster_slots,
        team_roster=scenario["roster"],
        current_round=scenario["round"],
    )

    sorted_players = sorted(vor_results.values(), key=lambda x: x.dynamic_vor, reverse=True)

    # Show top 5 players
    print(
        f"\n{'Rank':<6} {'Name':<25} {'Pos':<5} {'Base VOR':<10} {'Scarcity':<10} {'Need':<10} {'Dynamic VOR':<12}"
    )
    print("-" * 120)

    for i, player in enumerate(sorted_players[:5], 1):
        player_data = next((p for p in all_players if p["player_id"] == player.player_id), None)
        if player_data is None:
            continue
        print(
            f"{i:<6} {player_data['name']:<25} {player.position:<5} "
            f"{player.base_vor:<10.2f} {player.scarcity_multiplier:<10.2f} "
            f"{player.need_multiplier:<10.2f} {player.dynamic_vor:<12.2f}"
        )

    # Position distribution in top 12
    pos_counts = {"RB": 0, "WR": 0, "QB": 0, "TE": 0, "K": 0, "DST": 0}
    for player in sorted_players[:12]:
        pos_counts[player.position] = pos_counts.get(player.position, 0) + 1

    print(
        f"\nTop 12: RB={pos_counts['RB']}  WR={pos_counts['WR']}  QB={pos_counts['QB']}  "
        f"TE={pos_counts['TE']}  K={pos_counts['K']}  DST={pos_counts['DST']}"
    )

    # Find key players
    key_names = ["Josh Allen", "Ja'Marr Chase", "Travis Kelce"]
    print("\nKey Player Rankings:")
    for name in key_names:
        for i, player in enumerate(sorted_players[:60], 1):
            player_data = next((p for p in all_players if p["player_id"] == player.player_id), None)
            if player_data and player_data["name"] == name:
                print(f"  {name:<25} #{i:<4} VOR: {player.dynamic_vor:.1f}")
                break

# Test scarcity multiplier progression
print("\n" + "=" * 120)
print("SCARCITY MULTIPLIER PROGRESSION (12-team, Half PPR)")
print("=" * 120)

drafted_rbs = [0, 10, 20, 30, 40]
print(
    f"\n{'RBs Drafted':<15} {'Top RB Base':<15} {'Scarcity':<15} {'Dynamic VOR':<15} {'Effect':<20}"
)
print("-" * 120)

for drafted in drafted_rbs:
    vor_results = calc.calculate_dynamic_vor(
        available_players=all_players,
        drafted_positions={"RB": drafted},
        roster_slots=roster_slots,
        team_roster={pos: [] for pos in roster_slots},
        current_round=1,
    )

    # Find top remaining RB
    rbs = [v for v in vor_results.values() if v.position == "RB"]
    if rbs:
        top_rb = max(rbs, key=lambda x: x.dynamic_vor)
        effect = (
            f"{'+' if drafted > 0 else ''}{((top_rb.dynamic_vor - 754.64) / 754.64 * 100):.1f}%"
        )
        print(
            f"{drafted:<15} {top_rb.base_vor:<15.2f} {top_rb.scarcity_multiplier:<15.2f} "
            f"{top_rb.dynamic_vor:<15.2f} {effect:<20}"
        )
