"""CSV export for draft results."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict

from src.ui.config import REACH_STEAL_LABEL_THRESHOLD, STEAL_STRONG_THRESHOLD


def _reach_label(delta: int) -> str:
    """Return a plain-text reach/steal label for a given pick delta.

    delta = pick_number - overall_rank  (positive = steal, negative = reach)
    """
    if delta >= STEAL_STRONG_THRESHOLD:
        return "STEAL"
    if delta >= REACH_STEAL_LABEL_THRESHOLD:
        return "Value"
    if delta <= -REACH_STEAL_LABEL_THRESHOLD:
        return "REACH"
    return ""


class DraftExporter:
    """Exports draft results to CSV."""

    def export_to_csv(
        self,
        draft_state,
        scoring_format: str,
        output_dir: str = "data/exports",
    ) -> Path:
        """Write all picks to a CSV file and return its path.

        Columns: pick_number, round, pick_in_round, team_name, player_name,
                 position, nfl_team, slot, proj_pts, adp, reach_delta, reach_label
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_id = draft_state.draft_id[:8]
        filename = out_dir / f"draft_{short_id}_{timestamp}.csv"

        league_size = draft_state.league_config.league_size

        with open(filename, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "pick_number", "round", "pick_in_round",
                "team_name", "player_name", "position", "nfl_team", "slot",
                "proj_pts", "adp", "reach_delta", "reach_label",
            ])
            for pick in draft_state.all_picks:
                info = draft_state.player_data.get(pick.player_id, {})
                team = draft_state.teams[pick.team_id] if 0 <= pick.team_id < len(draft_state.teams) else None
                team_name = team.team_name if team else "?"
                pick_in_round = ((pick.pick_number - 1) % league_size) + 1
                proj = info.get("projections", {}).get(scoring_format, 0)
                adp = info.get("overall_rank")
                delta = pick.pick_number - adp if adp is not None else 0
                label = _reach_label(delta) if adp is not None else ""
                writer.writerow([
                    pick.pick_number,
                    pick.round,
                    pick_in_round,
                    team_name,
                    info.get("name", pick.player_id),
                    info.get("position", "?"),
                    info.get("team", "?"),
                    pick.slot or "",
                    f"{proj:.1f}",
                    adp,
                    delta,
                    label,
                ])

        return filename
