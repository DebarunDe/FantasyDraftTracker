"""Test VOR rankings across different league sizes."""

import json
from src.simulation_engine.vor_calculator import DynamicVORCalculator

# Load player data
with open("data/processed/players_2025.json", "r") as f:
    data = json.load(f)
    all_players = data["players"]

roster_slots = {
    "QB": 1, "RB": 2, "WR": 2, "TE": 1,
    "FLEX": 1, "K": 1, "DST": 1, "BENCH": 6,
}

league_sizes = [8, 10, 12, 14]

print("=" * 120)
print("VOR RANKINGS ACROSS LEAGUE SIZES (Half PPR, Top 24 picks)")
print("=" * 120)

for league_size in league_sizes:
    calc = DynamicVORCalculator("half_ppr", league_size=league_size)

    vor_results = calc.calculate_dynamic_vor(
        available_players=all_players,
        drafted_positions={},
        roster_slots=roster_slots,
        team_roster={pos: [] for pos in roster_slots},
        current_round=1,
    )

    sorted_players = sorted(vor_results.values(), key=lambda x: x.dynamic_vor, reverse=True)

    print(f"\n{league_size}-TEAM LEAGUE:")
    print("-" * 120)

    # Count positions in top 24
    pos_counts = {"RB": 0, "WR": 0, "QB": 0, "TE": 0}
    for i, player in enumerate(sorted_players[:24], 1):
        pos_counts[player.position] = pos_counts.get(player.position, 0) + 1

    print(f"Top 24 Distribution: RB={pos_counts['RB']}  WR={pos_counts['WR']}  "
          f"QB={pos_counts['QB']}  TE={pos_counts['TE']}")

    # Show key players
    key_players = {
        "Ja'Marr Chase": "WR",
        "Josh Allen": "QB",
        "CeeDee Lamb": "WR",
        "James Conner": "RB",
    }

    print(f"\n{'Player':<25} {'Pos':<5} {'Rank':<8} {'Base VOR':<12} {'Dynamic VOR':<12}")
    print("-" * 120)

    for target_name, target_pos in key_players.items():
        found = False
        for i, player in enumerate(sorted_players[:48], 1):
            player_data = next((p for p in all_players if p["player_id"] == player.player_id), None)
            if player_data and player_data["name"] == target_name:
                print(f"{target_name:<25} {target_pos:<5} #{i:<7} {player.base_vor:<12.2f} {player.dynamic_vor:<12.2f}")
                found = True
                break
        if not found:
            print(f"{target_name:<25} {target_pos:<5} Not in top 48")

# Test how elite QB rankings change with league size
print("\n" + "=" * 120)
print("ELITE QB RANKINGS BY LEAGUE SIZE")
print("=" * 120)

elite_qbs = ["Josh Allen", "Lamar Jackson", "Jalen Hurts"]
print(f"\n{'Player':<20} ", end="")
for size in league_sizes:
    print(f"{size}-team   ", end="")
print()
print("-" * 120)

for qb_name in elite_qbs:
    print(f"{qb_name:<20} ", end="")
    for league_size in league_sizes:
        calc = DynamicVORCalculator("half_ppr", league_size=league_size)
        vor_results = calc.calculate_dynamic_vor(
            available_players=all_players,
            drafted_positions={},
            roster_slots=roster_slots,
            team_roster={pos: [] for pos in roster_slots},
            current_round=1,
        )
        sorted_players = sorted(vor_results.values(), key=lambda x: x.dynamic_vor, reverse=True)

        found = False
        for i, player in enumerate(sorted_players[:60], 1):
            player_data = next((p for p in all_players if p["player_id"] == player.player_id), None)
            if player_data and player_data["name"] == qb_name:
                print(f"#{i:<9}", end="")
                found = True
                break
        if not found:
            print(f"{'N/A':<9}", end="")
    print()

# Test positional scarcity effects
print("\n" + "=" * 120)
print("POSITIONAL SCARCITY EFFECTS")
print("=" * 120)

from src.data_pipeline.config import calculate_baseline_count

print(f"\n{'League Size':<15} {'RB Baseline':<15} {'WR Baseline':<15} {'QB Baseline':<15}")
print("-" * 120)

for league_size in league_sizes:
    rb_baseline = calculate_baseline_count("RB", league_size)
    wr_baseline = calculate_baseline_count("WR", league_size)
    qb_baseline = calculate_baseline_count("QB", league_size)
    print(f"{league_size}-team{'':<9} {rb_baseline:<15} {wr_baseline:<15} {qb_baseline:<15}")
