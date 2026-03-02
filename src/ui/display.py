"""Rich-based display components for the draft CLI."""

from typing import Dict, List, Optional

from src.simulation_engine.models import Recommendation

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.ui.config import (
    POSITION_COLORS,
    REACH_STEAL_LABEL_THRESHOLD,
    RECENT_PICKS_DISPLAY_COUNT,
    SCORING_DISPLAY_NAMES,
    STEAL_STRONG_THRESHOLD,
    VOR_RECOMMENDATIONS_COUNT,
)


class DraftDisplay:
    """Stateless renderer for all draft CLI screens."""

    def __init__(self, console: Console):
        self.console = console

    # ------------------------------------------------------------------
    # Draft board
    # ------------------------------------------------------------------

    def show_draft_header(self, draft_state) -> None:
        """Display draft status: round, pick, on-the-clock team."""
        team = draft_state.get_current_team()
        total_rounds = draft_state.league_config.total_rounds()
        scoring = SCORING_DISPLAY_NAMES.get(
            draft_state.league_config.scoring_format,
            draft_state.league_config.scoring_format,
        )
        human_tag = "  [bold green]\\[YOU][/bold green]" if team.is_human else ""
        mode_tag = (
            "  [dim]| Manual Tracker[/dim]"
            if draft_state.league_config.draft_mode == "manual_tracker"
            else ""
        )

        title = (
            f"Round {draft_state.current_round}, "
            f"Pick {((draft_state.current_pick - 1) % draft_state.league_config.league_size) + 1} "
            f"(Overall: {draft_state.current_pick})"
        )
        body = (
            f"  On the Clock: [bold]{team.team_name}[/bold]{human_tag}\n"
            f"  {scoring}  |  {draft_state.league_config.league_size} Teams  "
            f"|  {total_rounds} Rounds{mode_tag}"
        )
        self.console.print(Panel(body, title=title, border_style="bright_blue"))

    @staticmethod
    def _reach_label(pick_number: int, overall_rank: int) -> str:
        """Return Rich-markup reach/steal label for a pick vs ADP.

        delta = pick_number - overall_rank (positive = fell = steal, negative = reach)
        Returns empty string when the delta is within normal variation.
        """
        if not overall_rank:
            return ""
        delta = pick_number - overall_rank
        if delta >= STEAL_STRONG_THRESHOLD:
            return f"[bold green]▲ STEAL +{delta}[/bold green]"
        if delta >= REACH_STEAL_LABEL_THRESHOLD:
            return f"[green]Value +{delta}[/green]"
        if delta <= -REACH_STEAL_LABEL_THRESHOLD:
            return f"[red]▼ REACH {delta}[/red]"
        return ""

    def show_pick_banner(self, pick, player_info: Dict, team_name: str) -> None:
        """Display a prominent banner for a just-made pick."""
        pos = player_info.get("position", "?")
        color = POSITION_COLORS.get(pos, "white")
        nfl_team = player_info.get("team", "?")
        slot = pick.slot or pos
        adp = player_info.get("overall_rank", 0)
        reach = self._reach_label(pick.pick_number, adp)

        adp_str = f"  ADP #{adp}" if adp else ""
        reach_str = f"  {reach}" if reach else ""

        body = (
            f"  PICK #{pick.pick_number}: [bold]{player_info.get('name', '?')}[/bold] "
            f"([{color}]{pos}[/{color}] - {nfl_team})\n"
            f"  {team_name}  |  Round {pick.round}  |  Slot: {slot}"
            f"{adp_str}{reach_str}"
        )
        self.console.print(Panel(body, border_style="bold green"))

    def show_recent_picks(
        self,
        picks: list,
        player_data: Dict,
        teams: list,
        limit: int = RECENT_PICKS_DISPLAY_COUNT,
    ) -> None:
        """Display table of recent picks."""
        recent = picks[-limit:] if picks else []
        if not recent:
            self.console.print("[dim]No picks yet.[/dim]")
            return

        table = Table(title="Recent Picks", show_lines=False, pad_edge=False)
        table.add_column("Rd", justify="right", style="dim", width=3)
        table.add_column("Pick", justify="right", width=4)
        table.add_column("Team", width=16)
        table.add_column("Player", width=24)
        table.add_column("Pos", width=4)
        table.add_column("Slot", width=5)

        for pick in recent:
            info = player_data.get(pick.player_id, {})
            pos = info.get("position", "?")
            color = POSITION_COLORS.get(pos, "white")
            team_name = teams[pick.team_id].team_name if pick.team_id < len(teams) else "?"

            table.add_row(
                str(pick.round),
                str(pick.pick_number),
                team_name,
                info.get("name", pick.player_id),
                f"[{color}]{pos}[/{color}]",
                pick.slot or "-",
            )

        self.console.print(table)

    # ------------------------------------------------------------------
    # Available players
    # ------------------------------------------------------------------

    def show_available_players(
        self,
        players: List[Dict],
        scoring_format: str,
        vor_results: Optional[Dict] = None,
        limit: int = 25,
    ) -> List[Dict]:
        """Display numbered table of available players.

        Returns the displayed list (for pick-by-number resolution).
        """
        displayed = players[:limit]
        total = len(players)

        table = Table(
            title=f"Available Players (showing {len(displayed)} of {total})",
            show_lines=False,
        )
        table.add_column("#", justify="right", width=4)
        table.add_column("Name", width=24)
        table.add_column("Pos", width=4)
        table.add_column("Team", width=5)
        table.add_column("Bye", justify="right", width=4)
        table.add_column("Proj Pts", justify="right", width=9)
        table.add_column("VOR", justify="right", width=7)

        for i, player in enumerate(displayed, 1):
            pos = player.get("position", "?")
            color = POSITION_COLORS.get(pos, "white")
            proj = player.get("projections", {}).get(scoring_format, 0)
            bye = player.get("bye_week")
            bye_str = str(bye) if bye is not None else "-"

            vor_val = ""
            player_id = player.get("player_id")
            if vor_results and player_id and player_id in vor_results:
                vor_val = f"{vor_results[player_id].dynamic_vor:.1f}"
            else:
                base_vor = player.get("baseline_vor", {}).get(scoring_format, 0)
                vor_val = f"{base_vor:.1f}"

            table.add_row(
                str(i),
                player.get("name", "?"),
                f"[{color}]{pos}[/{color}]",
                player.get("team", "?"),
                bye_str,
                f"{proj:.1f}",
                vor_val,
            )

        self.console.print(table)
        return displayed

    def show_search_results(
        self, results: List[Dict], scoring_format: str
    ) -> None:
        """Display search results in a numbered table."""
        if not results:
            self.console.print("[yellow]No players found.[/yellow]")
            return

        table = Table(title="Search Results", show_lines=False)
        table.add_column("#", justify="right", width=4)
        table.add_column("Name", width=24)
        table.add_column("Pos", width=4)
        table.add_column("Team", width=5)
        table.add_column("Proj Pts", justify="right", width=9)

        for i, player in enumerate(results, 1):
            pos = player.get("position", "?")
            color = POSITION_COLORS.get(pos, "white")
            proj = player.get("projections", {}).get(scoring_format, 0)

            table.add_row(
                str(i),
                player.get("name", "?"),
                f"[{color}]{pos}[/{color}]",
                player.get("team", "?"),
                f"{proj:.1f}",
            )

        self.console.print(table)

    # ------------------------------------------------------------------
    # Roster
    # ------------------------------------------------------------------

    def show_team_roster(
        self,
        team_name: str,
        roster: Dict[str, List[Dict]],
        scoring_format: str,
        roster_slots: Dict[str, int],
    ) -> None:
        """Display a team's roster with filled/empty slots."""
        table = Table(show_lines=False, pad_edge=False)
        table.add_column("Slot", width=8)
        table.add_column("Player", width=24)
        table.add_column("Pos", width=4)
        table.add_column("Team", width=5)
        table.add_column("Proj Pts", justify="right", width=9)

        slot_order = ["QB", "RB", "WR", "TE", "FLEX", "DST", "K", "BENCH"]
        for slot in slot_order:
            if slot not in roster_slots:
                continue
            count = roster_slots[slot]
            players = roster.get(slot, [])

            for i in range(count):
                slot_label = slot if count == 1 else f"{slot} {i + 1}"
                if i < len(players):
                    p = players[i]
                    pos = p.get("position", "?")
                    color = POSITION_COLORS.get(pos, "white")
                    proj = p.get("projections", {}).get(scoring_format, 0)
                    table.add_row(
                        slot_label,
                        p.get("name", "?"),
                        f"[{color}]{pos}[/{color}]",
                        p.get("team", "?"),
                        f"{proj:.1f}",
                    )
                else:
                    table.add_row(
                        slot_label,
                        "[dim]\\[empty][/dim]",
                        "-",
                        "-",
                        "-",
                    )

        self.console.print(
            Panel(table, title=f"{team_name} - Roster", border_style="bright_cyan")
        )

    # ------------------------------------------------------------------
    # VOR recommendations
    # ------------------------------------------------------------------

    def show_vor_recommendations(
        self,
        vor_results: Dict,
        player_data: Dict,
        scoring_format: str,
        limit: int = VOR_RECOMMENDATIONS_COUNT,
    ) -> List[Dict]:
        """Display top N players by dynamic VOR as recommendations.

        Returns the displayed player list for pick-by-number.
        """
        sorted_results = sorted(
            vor_results.values(),
            key=lambda v: v.dynamic_vor,
            reverse=True,
        )[:limit]

        table = Table(title="Recommendations", show_lines=False)
        table.add_column("#", justify="right", width=4)
        table.add_column("Name", width=24)
        table.add_column("Pos", width=4)
        table.add_column("Team", width=5)
        table.add_column("Proj Pts", justify="right", width=9)
        table.add_column("Dyn VOR", justify="right", width=8)

        displayed = []
        for vor in sorted_results:
            info = player_data.get(vor.player_id, {})
            if not info:
                continue
            pos = info.get("position", "?")
            color = POSITION_COLORS.get(pos, "white")
            proj = info.get("projections", {}).get(scoring_format, 0)

            displayed.append(info)
            table.add_row(
                str(len(displayed)),
                info.get("name", "?"),
                f"[{color}]{pos}[/{color}]",
                info.get("team", "?"),
                f"{proj:.1f}",
                f"{vor.dynamic_vor:.1f}",
            )

        self.console.print(table)
        return displayed

    def show_recommendations(
        self,
        recommendations: List[Recommendation],
    ) -> List[Dict]:
        """Display ranked recommendations with reasoning.

        Returns the displayed player list (as dicts) for pick-by-number.
        """
        table = Table(title="Recommendations", show_lines=False)
        table.add_column("#", justify="right", width=4)
        table.add_column("Name", width=22)
        table.add_column("Pos", width=4)
        table.add_column("Team", width=5)
        table.add_column("Proj Pts", justify="right", width=9)
        table.add_column("Dyn VOR", justify="right", width=8)
        table.add_column("Why", width=36)

        displayed: List[Dict] = []
        for rec in recommendations:
            color = POSITION_COLORS.get(rec.position, "white")
            displayed.append({"player_id": rec.player_id, "name": rec.player_name,
                               "position": rec.position, "team": rec.team})
            table.add_row(
                str(rec.rank),
                rec.player_name,
                f"[{color}]{rec.position}[/{color}]",
                rec.team,
                f"{rec.projected_points:.1f}",
                f"{rec.dynamic_vor:.1f}",
                f"[dim]{rec.reasoning}[/dim]",
            )

        self.console.print(table)
        return displayed

    # ------------------------------------------------------------------
    # Full draft board (all picks with reach/steal)
    # ------------------------------------------------------------------

    def show_full_draft_board(
        self,
        all_picks: list,
        player_data: Dict,
        teams: list,
    ) -> None:
        """Display all picks made so far with reach/steal delta column."""
        if not all_picks:
            self.console.print("[dim]No picks yet.[/dim]")
            return

        table = Table(
            title=f"Draft Board ({len(all_picks)} picks)",
            show_lines=False,
            pad_edge=False,
        )
        table.add_column("Rd", justify="right", style="dim", width=3)
        table.add_column("Pick", justify="right", width=4)
        table.add_column("Team", width=16)
        table.add_column("Player", width=24)
        table.add_column("Pos", width=4)
        table.add_column("Slot", width=5)
        table.add_column("Proj Pts", justify="right", width=8)
        table.add_column("ADP", justify="right", width=4)
        table.add_column("Δ", justify="right", width=7)

        for pick in all_picks:
            info = player_data.get(pick.player_id, {})
            pos = info.get("position", "?")
            color = POSITION_COLORS.get(pos, "white")
            team_name = teams[pick.team_id].team_name if pick.team_id < len(teams) else "?"
            adp = info.get("overall_rank", 0)

            # Projected points (display format-agnostic — use first available)
            projs = info.get("projections", {})
            proj = next(iter(projs.values()), 0) if projs else 0
            proj_str = f"{proj:.1f}" if proj else "-"

            adp_str = str(adp) if adp else "-"
            delta_str = ""
            if adp:
                delta = pick.pick_number - adp
                if delta >= STEAL_STRONG_THRESHOLD:
                    delta_str = f"[bold green]+{delta}[/bold green]"
                elif delta >= REACH_STEAL_LABEL_THRESHOLD:
                    delta_str = f"[green]+{delta}[/green]"
                elif delta <= -REACH_STEAL_LABEL_THRESHOLD:
                    delta_str = f"[red]{delta}[/red]"
                else:
                    delta_str = f"[dim]{'+' if delta > 0 else ''}{delta}[/dim]"

            table.add_row(
                str(pick.round),
                str(pick.pick_number),
                team_name,
                info.get("name", pick.player_id),
                f"[{color}]{pos}[/{color}]",
                pick.slot or "-",
                proj_str,
                adp_str,
                delta_str,
            )

        self.console.print(table)

    # ------------------------------------------------------------------
    # Team comparison
    # ------------------------------------------------------------------

    def show_team_comparison(
        self,
        teams: list,
        player_data: Dict,
        scoring_format: str,
        roster_slots: Dict,
        all_picks: list,
    ) -> None:
        """Display side-by-side team projected points and roster status."""
        total_roster_slots = sum(roster_slots.values())

        # Pre-compute per-team stats
        # Build pick lookup: player_id → pick for reach calc
        pick_by_player: Dict[str, object] = {p.player_id: p for p in all_picks}

        table = Table(title="Team Comparison", show_lines=True, pad_edge=False)
        table.add_column("#", justify="right", width=3)
        table.add_column("Team", width=18)
        table.add_column("Proj Pts", justify="right", width=9)
        for pos in ("QB", "RB", "WR", "TE"):
            if pos in roster_slots:
                table.add_column(pos, justify="right", width=7)
        table.add_column("Picks", justify="right", width=6)
        table.add_column("Avg Δ", justify="right", width=7)
        table.add_column("Best Steal", width=20)
        table.add_column("Worst Reach", width=20)

        teams_sorted = sorted(
            teams,
            key=lambda t: self._team_starter_pts(t, player_data, scoring_format),
            reverse=True,
        )

        for rank, team in enumerate(teams_sorted, 1):
            starter_pts = self._team_starter_pts(team, player_data, scoring_format)
            total_picks = team.get_total_picks()
            human_tag = " [bold green](You)[/bold green]" if team.is_human else ""
            status = f"{total_picks}/{total_roster_slots}"

            # Per-position starter points
            pos_pts = {}
            for pos in ("QB", "RB", "WR", "TE"):
                if pos not in roster_slots:
                    continue
                pts = sum(
                    player_data.get(pid, {}).get("projections", {}).get(scoring_format, 0)
                    for pid in team.roster.get(pos, [])
                )
                pos_pts[pos] = pts

            # Reach/steal analysis across team's picks
            deltas = []
            best_steal: Optional[Dict] = None
            worst_reach: Optional[Dict] = None
            for pid in team.picks:
                info = player_data.get(pid, {})
                adp = info.get("overall_rank", 0)
                pick = pick_by_player.get(pid)
                if not adp or not pick:
                    continue
                delta = pick.pick_number - adp
                deltas.append(delta)
                if best_steal is None or delta > best_steal["delta"]:
                    best_steal = {"name": info.get("name", "?"), "delta": delta}
                if worst_reach is None or delta < worst_reach["delta"]:
                    worst_reach = {"name": info.get("name", "?"), "delta": delta}

            avg_delta = sum(deltas) / len(deltas) if deltas else 0
            avg_str = f"{avg_delta:+.1f}" if deltas else "-"

            best_str = ""
            if best_steal and best_steal["delta"] >= REACH_STEAL_LABEL_THRESHOLD:
                best_str = f"[green]{best_steal['name']} (+{best_steal['delta']})[/green]"
            worst_str = ""
            if worst_reach and worst_reach["delta"] <= -REACH_STEAL_LABEL_THRESHOLD:
                worst_str = f"[red]{worst_reach['name']} ({worst_reach['delta']})[/red]"

            row = [
                str(rank),
                f"{team.team_name}{human_tag}",
                f"{starter_pts:.1f}",
            ]
            for pos in ("QB", "RB", "WR", "TE"):
                if pos in roster_slots:
                    row.append(f"{pos_pts.get(pos, 0):.1f}" if pos_pts.get(pos) else "-")
            row.extend([status, avg_str, best_str, worst_str])
            table.add_row(*row)

        self.console.print(table)

    @staticmethod
    def _team_starter_pts(team, player_data: Dict, scoring_format: str) -> float:
        """Projected points for a team's starting lineup (excludes bench)."""
        total = 0.0
        for slot, pids in team.roster.items():
            if slot == "BENCH":
                continue
            for pid in pids:
                total += player_data.get(pid, {}).get("projections", {}).get(scoring_format, 0)
        return total

    # ------------------------------------------------------------------
    # Draft summary
    # ------------------------------------------------------------------

    def show_draft_summary(self, summary: Dict, scoring_format: str) -> None:
        """Display final draft summary with standings."""
        self.console.print()
        self.console.print(
            Panel(
                "[bold]DRAFT COMPLETE![/bold]",
                border_style="bold green",
                expand=False,
            )
        )
        self.console.print()

        teams = summary.get("teams", [])
        teams_sorted = sorted(
            teams, key=lambda t: t.get("projected_points", 0), reverse=True
        )

        table = Table(title="Final Standings", show_lines=False)
        table.add_column("#", justify="right", width=4)
        table.add_column("Team", width=20)
        table.add_column("Proj Points", justify="right", width=12)
        table.add_column("", width=12)

        for rank, team in enumerate(teams_sorted, 1):
            tag = "[bold green](Your Team)[/bold green]" if team.get("is_human") else ""
            table.add_row(
                str(rank),
                team.get("team_name", "Unknown"),
                f"{team.get('projected_points', 0):,.1f}",
                tag,
            )

        self.console.print(table)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def show_help(self, is_manual_tracker: bool = False) -> None:
        """Display available commands."""
        sim_line = (
            ""
            if is_manual_tracker
            else "  [cyan]sim[/cyan]             Simulate all remaining picks automatically\n"
        )
        help_text = (
            "[bold]Commands:[/bold]\n"
            "  [cyan]<name>[/cyan]          Search and draft a player by name\n"
            "  [cyan]<number>[/cyan]        Draft player by number from last list\n"
            "  [cyan]a[/cyan] / [cyan]available[/cyan]  Show available players\n"
            "  [cyan]a <pos>[/cyan]         Filter available by position (e.g. 'a qb')\n"
            "  [cyan]a <n>[/cyan]           Show top N available (e.g. 'a 50')\n"
            "  [cyan]r[/cyan] / [cyan]roster[/cyan]     Show current team's roster\n"
            "  [cyan]r <n>[/cyan]           Show team N's roster (e.g. 'r 3')\n"
            "  [cyan]s <query>[/cyan]       Search players (e.g. 's kelce')\n"
            "  [cyan]rec[/cyan]             Show VOR recommendations\n"
            "  [cyan]b[/cyan] / [cyan]board[/cyan]      Show full draft board with reach/steal\n"
            "  [cyan]compare[/cyan]         Compare all teams' projected points\n"
            "  [cyan]export[/cyan]          Export draft picks to CSV\n"
            "  [cyan]save[/cyan]            Save draft state\n"
            + sim_line +
            "  [cyan]h[/cyan] / [cyan]help[/cyan]       Show this help\n"
            "  [cyan]q[/cyan] / [cyan]quit[/cyan]       Save and quit"
        )
        self.console.print(Panel(help_text, title="Help", border_style="dim"))

    def show_error(self, message: str) -> None:
        """Display error message."""
        self.console.print(f"[bold red]Error:[/bold red] {message}")

    def show_success(self, message: str) -> None:
        """Display success message."""
        self.console.print(f"[green]{message}[/green]")
