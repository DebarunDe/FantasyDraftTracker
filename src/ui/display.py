"""Rich-based display components for the draft CLI."""

from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.ui.config import (
    POSITION_COLORS,
    RECENT_PICKS_DISPLAY_COUNT,
    SCORING_DISPLAY_NAMES,
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

        title = (
            f"Round {draft_state.current_round}, "
            f"Pick {((draft_state.current_pick - 1) % draft_state.league_config.league_size) + 1} "
            f"(Overall: {draft_state.current_pick})"
        )
        body = (
            f"  On the Clock: [bold]{team.team_name}[/bold]{human_tag}\n"
            f"  {scoring}  |  {draft_state.league_config.league_size} Teams  "
            f"|  {total_rounds} Rounds"
        )
        self.console.print(Panel(body, title=title, border_style="bright_blue"))

    def show_pick_banner(self, pick, player_info: Dict, team_name: str) -> None:
        """Display a prominent banner for a just-made pick."""
        pos = player_info.get("position", "?")
        color = POSITION_COLORS.get(pos, "white")
        nfl_team = player_info.get("team", "?")
        slot = pick.slot or pos

        body = (
            f"  PICK #{pick.pick_number}: [bold]{player_info.get('name', '?')}[/bold] "
            f"([{color}]{pos}[/{color}] - {nfl_team})\n"
            f"  {team_name}  |  Round {pick.round}  |  Slot: {slot}"
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

    def show_help(self) -> None:
        """Display available commands."""
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
            "  [cyan]b[/cyan] / [cyan]board[/cyan]      Re-display draft board\n"
            "  [cyan]save[/cyan]            Save draft state\n"
            "  [cyan]sim[/cyan]             Simulate all remaining picks automatically\n"
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
