"""Simulate a full draft using DynamicVORCalculator recommendations."""

import json
from src.simulation_engine.vor_calculator import DynamicVORCalculator
from src.draft_manager.draft_state import DraftState, LeagueConfig
from src.draft_manager.draft_controller import DraftController
from src.draft_manager.draft_rules import ValidationError


def run_simulation(league_size=12, scoring_format="half_ppr"):
    """Simulate a full draft where every team picks the highest dynamic VOR player."""
    with open("data/processed/players_2025.json", "r") as f:
        data = json.load(f)
    player_data = {p["player_id"]: p for p in data["players"]}

    roster_slots = {
        "QB": 1, "RB": 2, "WR": 2, "TE": 1,
        "FLEX": 1, "K": 1, "DST": 1, "BENCH": 6,
    }

    config = LeagueConfig(
        league_id="sim",
        league_size=league_size,
        scoring_format=scoring_format,
        draft_type="snake",
        draft_mode="simulation",
        data_year=2025,
        roster_slots=roster_slots,
    )

    team_names = [f"Team {i}" for i in range(league_size)]
    state = DraftState.create_new(
        league_config=config,
        team_names=team_names,
        human_team_id=0,
        player_data=player_data,
    )
    controller = DraftController(state)
    calc = DynamicVORCalculator(scoring_format, league_size=league_size)

    total_rounds = sum(roster_slots.values())
    total_picks = total_rounds * league_size
    draft_log = []  # (pick_num, round, team, player_name, position, dynamic_vor)

    for pick_num in range(1, total_picks + 1):
        team_id = state.current_team_id
        current_round = state.current_round

        # Calculate dynamic VOR for this team
        vor_results = calc.calculate_from_draft_state(state, team_id)

        # Pick the highest dynamic VOR player, skipping invalid picks
        sorted_candidates = sorted(vor_results.values(), key=lambda x: x.dynamic_vor, reverse=True)
        for candidate in sorted_candidates:
            player_info = state.get_player_info(candidate.player_id)
            try:
                controller.make_pick(team_id, candidate.player_id)
                draft_log.append((
                    pick_num, current_round, team_id,
                    player_info["name"], player_info["position"],
                    candidate.dynamic_vor,
                ))
                break
            except ValidationError:
                continue

    return draft_log, state


def print_results(draft_log, state, league_size, scoring_format):
    print(f"\n{'='*120}")
    print(f"FULL DRAFT SIMULATION: {league_size}-team {scoring_format}")
    print(f"{'='*120}")

    # Show first 4 rounds
    for rnd in range(1, 5):
        picks_in_round = [p for p in draft_log if p[1] == rnd]
        print(f"\n--- Round {rnd} ---")
        for pick_num, _, team_id, name, pos, dvor in picks_in_round:
            print(f"  Pick {pick_num:>3}: Team {team_id:>2} → {name:<25} ({pos:<3}) VOR: {dvor:.1f}")

    # Key player tracking
    print(f"\n--- Key Player Draft Positions ---")
    key_players = [
        "Saquon Barkley", "Ja'Marr Chase", "Josh Allen", "Justin Jefferson",
        "CeeDee Lamb", "Lamar Jackson", "Jalen Hurts", "Travis Kelce",
        "George Kittle", "Bijan Robinson", "Derrick Henry",
    ]
    for name in key_players:
        for pick_num, rnd, team_id, pname, pos, dvor in draft_log:
            if pname == name:
                print(f"  {name:<25} Pick #{pick_num:>3} (Round {rnd}) VOR: {dvor:.1f}")
                break

    # Position distribution per round
    print(f"\n--- Position Distribution by Round ---")
    total_rounds = sum(state.league_config.roster_slots.values())
    for rnd in range(1, min(total_rounds + 1, 16)):
        picks = [p for p in draft_log if p[1] == rnd]
        pos_counts = {}
        for _, _, _, _, pos, _ in picks:
            pos_counts[pos] = pos_counts.get(pos, 0) + 1
        parts = [f"{pos}={cnt}" for pos, cnt in sorted(pos_counts.items())]
        print(f"  Round {rnd:>2}: {', '.join(parts)}")

    # K/DST draft rounds
    print(f"\n--- K/DST Draft Timing ---")
    k_rounds = [p[1] for p in draft_log if p[4] == "K"]
    dst_rounds = [p[1] for p in draft_log if p[4] == "DST"]
    if k_rounds:
        print(f"  K:   rounds {min(k_rounds)}-{max(k_rounds)} (avg {sum(k_rounds)/len(k_rounds):.1f})")
    if dst_rounds:
        print(f"  DST: rounds {min(dst_rounds)}-{max(dst_rounds)} (avg {sum(dst_rounds)/len(dst_rounds):.1f})")

    # Team roster balance
    print(f"\n--- Team Roster Summary ---")
    max_positions = {}
    for team in state.teams:
        pos_counts = {}
        for slot, pids in team.roster.items():
            for pid in pids:
                pinfo = state.get_player_info(pid)
                if pinfo:
                    p = pinfo["position"]
                    pos_counts[p] = pos_counts.get(p, 0) + 1
        for pos, cnt in pos_counts.items():
            if pos not in max_positions or cnt > max_positions[pos]:
                max_positions[pos] = cnt

    print(f"  Max players at any position across all teams:")
    for pos in ["QB", "RB", "WR", "TE", "K", "DST"]:
        print(f"    {pos}: {max_positions.get(pos, 0)}")

    # Balance score
    print(f"\n  Team balance scores (lower = more balanced):")
    for team in state.teams:
        pos_counts = {}
        for slot, pids in team.roster.items():
            for pid in pids:
                pinfo = state.get_player_info(pid)
                if pinfo:
                    p = pinfo["position"]
                    pos_counts[p] = pos_counts.get(p, 0) + 1
        ideal = {"QB": 2, "RB": 5, "WR": 5, "TE": 1, "K": 1, "DST": 1}
        score = sum(abs(pos_counts.get(p, 0) - t) for p, t in ideal.items())
        counts = " ".join(f"{p}={pos_counts.get(p, 0)}" for p in ["QB", "RB", "WR", "TE", "K", "DST"])
        print(f"    Team {team.team_id:>2}: score={score}  {counts}")


# Run for 12-team half PPR
log, state = run_simulation(12, "half_ppr")
print_results(log, state, 12, "half_ppr")
