"""Interactive draft setup wizard."""

from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.draft_manager.config import (
    DEFAULT_LEAGUE_SIZE,
    DEFAULT_ROSTER_SLOTS,
    DEFAULT_SCORING_FORMAT,
)
from src.draft_manager.state_persistence import StatePersistence
from src.ui.config import SCORING_DISPLAY_NAMES, VALID_LEAGUE_SIZES


class SetupWizard:
    """Interactive draft configuration flow using Rich console."""

    def __init__(self, console: Console, persistence: StatePersistence):
        self.console = console
        self.persistence = persistence

    def run(self) -> Dict:
        """Run the full setup wizard.

        Returns one of:
            {"action": "new", "league_size": int, "scoring_format": str,
             "roster_slots": dict, "team_names": list, "pick_trades": list,
             "human_team_id": int, "data_year": int}
            {"action": "resume", "draft_state": DraftState}
            {"action": "quit"}
        """
        while True:
            choice = self._show_main_menu()

            if choice == "1":
                config = self._configure_new_draft()
                if config is not None:
                    return config
                # User cancelled during configuration, show menu again

            elif choice == "2":
                result = self._show_resume_menu()
                if result is not None:
                    return result
                # User went back, show menu again

            elif choice == "3":
                return {"action": "quit"}

    def _show_main_menu(self) -> str:
        """Display main menu and get choice."""
        self.console.print()
        self.console.print(
            Panel(
                "[bold]Fantasy Draft Tracker[/bold]",
                border_style="bright_blue",
                expand=False,
            )
        )
        self.console.print()
        self.console.print("  1. Start New Draft")
        self.console.print("  2. Resume Saved Draft")
        self.console.print("  3. Quit")
        self.console.print()

        while True:
            choice = self.console.input("[bold]Select [1-3]: [/bold]").strip()
            if choice in ("1", "2", "3"):
                return choice
            self.console.print("[red]Please enter 1, 2, or 3.[/red]")

    def _configure_new_draft(self) -> Optional[Dict]:
        """Step through league configuration. Returns config dict or None."""
        self.console.print()
        self.console.print("[bold]-- League Configuration --[/bold]")
        self.console.print()

        draft_mode = self._configure_draft_mode()
        league_size = self._configure_league_size()
        scoring_format = self._configure_scoring_format()
        roster_slots = self._configure_roster_slots()
        team_names = self._configure_team_names(league_size)
        total_rounds = sum(roster_slots.values())
        pick_trades = self._configure_pick_trades(league_size, team_names, total_rounds)
        human_team_id = self._configure_draft_position(league_size)
        data_year = self._configure_data_year()

        # Show confirmation
        total_picks = league_size * total_rounds
        scoring_name = SCORING_DISPLAY_NAMES.get(scoring_format, scoring_format)
        mode_display = (
            "Simulation (AI opponents auto-pick)"
            if draft_mode == "simulation"
            else "Manual Tracker (record all picks manually)"
        )

        self.console.print()
        roster_str = " ".join(f"{k}:{v}" for k, v in roster_slots.items())
        body = (
            f"  Mode: {mode_display}\n"
            f"  League Size: {league_size}\n"
            f"  Scoring: {scoring_name}\n"
            f"  Your Team: {team_names[human_team_id]} (Pick #{human_team_id + 1})\n"
            f"  Roster: {roster_str}\n"
            f"  Total Rounds: {total_rounds}\n"
            f"  Total Picks: {total_picks}\n"
            f"  Data Year: {data_year}"
        )
        if pick_trades:
            trades_str = "\n".join(
                f"    Rd {t['round']}: {team_names[t['from_team_id']]} → "
                f"{team_names[t['to_team_id']]}"
                for t in pick_trades
            )
            body += f"\n  Traded Picks ({len(pick_trades)}):\n{trades_str}"
        self.console.print(Panel(body, title="Draft Configuration", border_style="green"))

        confirm = self.console.input("Start draft? [Y/n]: ").strip().lower()
        if confirm in ("", "y", "yes"):
            return {
                "action": "new",
                "draft_mode": draft_mode,
                "league_size": league_size,
                "scoring_format": scoring_format,
                "roster_slots": roster_slots,
                "team_names": team_names,
                "pick_trades": pick_trades,
                "human_team_id": human_team_id,
                "data_year": data_year,
            }
        return None

    def _configure_draft_mode(self) -> str:
        """Prompt for draft mode: simulation or manual tracker."""
        self.console.print("  Draft Mode:")
        self.console.print("    1. Simulation       - AI opponents auto-pick (recommended)")
        self.console.print("    2. Manual Tracker   - Record every pick yourself (for live drafts)")
        while True:
            raw = self.console.input("  Select [1-2] (1): ").strip()
            if raw in ("", "1"):
                return "simulation"
            if raw == "2":
                return "manual_tracker"
            self.console.print("[red]  Please enter 1 or 2.[/red]")

    def _configure_league_size(self) -> int:
        """Prompt for league size."""
        sizes_str = "/".join(str(s) for s in VALID_LEAGUE_SIZES)
        while True:
            raw = self.console.input(
                f"  League size [{sizes_str}] ({DEFAULT_LEAGUE_SIZE}): "
            ).strip()
            if raw == "":
                return DEFAULT_LEAGUE_SIZE
            try:
                size = int(raw)
                if size in VALID_LEAGUE_SIZES:
                    return size
                self.console.print(f"[red]  Must be one of: {sizes_str}[/red]")
            except ValueError:
                self.console.print("[red]  Please enter a number.[/red]")

    def _configure_scoring_format(self) -> str:
        """Prompt for scoring format."""
        formats = ["standard", "half_ppr", "full_ppr"]
        default_idx = formats.index(DEFAULT_SCORING_FORMAT) + 1

        self.console.print("  Scoring Format:")
        for i, fmt in enumerate(formats, 1):
            name = SCORING_DISPLAY_NAMES[fmt]
            rec = " (recommended)" if fmt == DEFAULT_SCORING_FORMAT else ""
            self.console.print(f"    {i}. {name}{rec}")

        while True:
            raw = self.console.input(f"  Select [1-3] ({default_idx}): ").strip()
            if raw == "":
                return DEFAULT_SCORING_FORMAT
            try:
                choice = int(raw)
                if 1 <= choice <= 3:
                    return formats[choice - 1]
                self.console.print("[red]  Please enter 1, 2, or 3.[/red]")
            except ValueError:
                self.console.print("[red]  Please enter a number.[/red]")

    def _configure_roster_slots(self) -> Dict[str, int]:
        """Prompt for roster configuration."""
        slots_str = " ".join(f"{k}:{v}" for k, v in DEFAULT_ROSTER_SLOTS.items())
        raw = self.console.input(f"  Use default roster? ({slots_str}) [Y/n]: ").strip().lower()

        if raw in ("", "y", "yes"):
            return dict(DEFAULT_ROSTER_SLOTS)

        # Custom configuration
        slots = {}
        for pos, default in DEFAULT_ROSTER_SLOTS.items():
            while True:
                val = self.console.input(f"    {pos} ({default}): ").strip()
                if val == "":
                    slots[pos] = default
                    break
                try:
                    n = int(val)
                    if n >= 0:
                        slots[pos] = n
                        break
                    self.console.print("[red]    Must be >= 0.[/red]")
                except ValueError:
                    self.console.print("[red]    Please enter a number.[/red]")
        return slots

    def _configure_team_names(self, league_size: int) -> List[str]:
        """Prompt for team names."""
        raw = self.console.input("  Auto-generate team names? [Y/n]: ").strip().lower()

        if raw in ("", "y", "yes"):
            return [f"Team {i + 1}" for i in range(league_size)]

        names = []
        for i in range(league_size):
            default = f"Team {i + 1}"
            name = self.console.input(f"    Team {i + 1} name ({default}): ").strip()
            names.append(name if name else default)
        return names

    def _configure_pick_trades(
        self, league_size: int, team_names: List[str], total_rounds: int
    ) -> List[Dict]:
        """Prompt user to enter any pre-draft pick trades.

        Returns a list of trade dicts: {"from_team_id": int, "round": int, "to_team_id": int}.
        Team numbers shown to the user are 1-indexed; stored 0-indexed.
        """
        raw = self.console.input("  Configure traded picks? [Y/n]: ").strip().lower()
        if raw not in ("", "y", "yes"):
            return []

        # Build a working copy of the snake order so we can validate each
        # trade as it is entered and show the updated order.
        from src.draft_manager.draft_state import DraftState

        working_order = DraftState._generate_snake_order(league_size, total_rounds)

        trades: List[Dict] = []

        self.console.print()
        self._show_pick_order(working_order, team_names)
        self.console.print()
        self.console.print("  Enter trades as: [bold]<teamA#> <roundA#> <teamB#> <roundB#>[/bold]")
        self.console.print("    Team A gives their Rd A pick; Team B gives their Rd B pick back.")
        self.console.print(
            "    Example: [dim]2 1 4 3[/dim]  "
            "(Team 2 gives Rd 1 to Team 4; Team 4 gives Rd 3 to Team 2)"
        )
        self.console.print("  Type [bold]done[/bold] when finished.")
        self.console.print()

        while True:
            raw = self.console.input("  > ").strip().lower()
            if raw in ("done", "d"):
                break
            if raw == "":
                continue

            parts = raw.split()
            if len(parts) != 4:
                self.console.print(
                    "[red]  Enter exactly four numbers: <teamA#> <roundA#> <teamB#> <roundB#>[/red]"
                )
                continue

            try:
                a_disp, rnd_a, b_disp, rnd_b = (
                    int(parts[0]),
                    int(parts[1]),
                    int(parts[2]),
                    int(parts[3]),
                )
            except ValueError:
                self.console.print("[red]  All four values must be integers.[/red]")
                continue

            if not (1 <= a_disp <= league_size):
                self.console.print(f"[red]  teamA# must be 1–{league_size}.[/red]")
                continue
            if not (1 <= b_disp <= league_size):
                self.console.print(f"[red]  teamB# must be 1–{league_size}.[/red]")
                continue
            if a_disp == b_disp:
                self.console.print("[red]  Teams must be different.[/red]")
                continue
            if not (1 <= rnd_a <= total_rounds):
                self.console.print(f"[red]  roundA# must be 1–{total_rounds}.[/red]")
                continue
            if not (1 <= rnd_b <= total_rounds):
                self.console.print(f"[red]  roundB# must be 1–{total_rounds}.[/red]")
                continue

            a_id = a_disp - 1
            b_id = b_disp - 1

            # Validate both teams own their respective picks.
            slots_a = working_order[rnd_a - 1]
            slots_b = working_order[rnd_b - 1]
            if a_id not in slots_a:
                self.console.print(
                    f"[red]  {team_names[a_id]} does not have a pick in Round {rnd_a}.[/red]"
                )
                continue
            if b_id not in slots_b:
                self.console.print(
                    f"[red]  {team_names[b_id]} does not have a pick in Round {rnd_b}.[/red]"
                )
                continue

            # Apply both halves atomically.
            slots_a[slots_a.index(a_id)] = b_id
            slots_b[slots_b.index(b_id)] = a_id
            trades.append({"from_team_id": a_id, "round": rnd_a, "to_team_id": b_id})
            trades.append({"from_team_id": b_id, "round": rnd_b, "to_team_id": a_id})

            self.console.print(
                f"  [green]✓[/green] {team_names[a_id]}'s Rd {rnd_a} ↔ "
                f"{team_names[b_id]}'s Rd {rnd_b}"
            )
            self.console.print()
            self._show_pick_order(working_order, team_names)
            self.console.print()
            self.console.print(
                "  Enter trades as: [bold]<teamA#> <roundA#> <teamB#> <roundB#>[/bold]"
            )
            self.console.print(
                "    Team A gives their Rd A pick; Team B gives their Rd B pick back."
            )
            self.console.print(
                "    Example: [dim]2 1 4 3[/dim]  "
                "(Team 2 gives Rd 1 to Team 4; Team 4 gives Rd 3 to Team 2)"
            )
            self.console.print("  Type [bold]done[/bold] when finished.")
            self.console.print()

        return trades

    def _show_pick_order(
        self,
        draft_order: List[List[int]],
        team_names: List[str],
        highlight_round: Optional[int] = None,
    ) -> None:
        """Print a compact draft order table (one row per round)."""
        self.console.print("  [bold]Draft pick order:[/bold]")
        for rnd_idx, slots in enumerate(draft_order):
            rnd_num = rnd_idx + 1
            direction = "→" if rnd_num % 2 == 1 else "←"
            names = ", ".join(team_names[tid] for tid in slots)
            line = f"    Rd {rnd_num:2d} ({direction}): {names}"
            if rnd_num == highlight_round:
                self.console.print(f"[bold yellow]{line}[/bold yellow]")
            else:
                self.console.print(line)

    def _configure_draft_position(self, league_size: int) -> int:
        """Prompt for human team draft position (1-based to user)."""
        while True:
            raw = self.console.input(f"  Your draft position [1-{league_size}] (1): ").strip()
            if raw == "":
                return 0
            try:
                pos = int(raw)
                if 1 <= pos <= league_size:
                    return pos - 1  # Convert to 0-based
                self.console.print(f"[red]  Must be between 1 and {league_size}.[/red]")
            except ValueError:
                self.console.print("[red]  Please enter a number.[/red]")

    def _configure_data_year(self) -> int:
        """Prompt for data year."""
        while True:
            raw = self.console.input("  Data year (2025): ").strip()
            if raw == "":
                return 2025
            try:
                year = int(raw)
                if 2020 <= year <= 2030:
                    return year
                self.console.print("[red]  Enter a year between 2020 and 2030.[/red]")
            except ValueError:
                self.console.print("[red]  Please enter a year.[/red]")

    def _show_resume_menu(self) -> Optional[Dict]:
        """List saved drafts and let user select one.

        Drafts are displayed in two sections — In Progress and Completed —
        with continuous numbering. Users can select a draft to resume or
        delete drafts with ``d <number>``.
        """
        drafts = self.persistence.list_saved_drafts()

        if not drafts:
            self.console.print("[yellow]  No saved drafts found.[/yellow]")
            return None

        in_progress = [d for d in drafts if not d["is_complete"]]
        completed = [d for d in drafts if d["is_complete"]]

        # Build ordered list with continuous numbering across sections.
        ordered: list = []
        ordered.extend(in_progress)
        ordered.extend(completed)

        # Display In Progress section
        if in_progress:
            ip_table = Table(title="In Progress", show_lines=False)
            self._add_draft_table_columns(ip_table)
            for draft in in_progress:
                idx = ordered.index(draft) + 1
                self._add_draft_table_row(ip_table, idx, draft)
            self.console.print(ip_table)
            self.console.print()

        # Display Completed section
        if completed:
            c_table = Table(title="Completed", show_lines=False)
            self._add_draft_table_columns(c_table)
            for draft in completed:
                idx = ordered.index(draft) + 1
                self._add_draft_table_row(c_table, idx, draft)
            self.console.print(c_table)
            self.console.print()

        if not in_progress and not completed:
            self.console.print("[yellow]  No saved drafts found.[/yellow]")
            return None

        self.console.print("[dim]  Enter # to resume, d # to delete, or 'back'[/dim]")

        while True:
            raw = self.console.input("  > ").strip()

            if raw.lower() in ("back", "b", ""):
                return None

            # Handle delete command: "d 2", "d2", "D 3"
            if raw.lower().startswith("d"):
                delete_part = raw[1:].strip()
                try:
                    del_idx = int(delete_part)
                    if 1 <= del_idx <= len(ordered):
                        target = ordered[del_idx - 1]
                        result = self._confirm_delete(target)
                        if result:
                            # Refresh the menu after deletion
                            return self._show_resume_menu()
                        continue
                    self.console.print(f"[red]  Enter a number between 1 and {len(ordered)}.[/red]")
                except ValueError:
                    self.console.print("[red]  Use 'd <number>' to delete a draft.[/red]")
                continue

            try:
                idx = int(raw)
                if 1 <= idx <= len(ordered):
                    draft_id = ordered[idx - 1]["draft_id"]
                    draft_state = self.persistence.load_draft(draft_id)
                    if draft_state is None:
                        self.console.print("[red]  Failed to load draft.[/red]")
                        continue
                    return {"action": "resume", "draft_state": draft_state}
                self.console.print(f"[red]  Enter a number between 1 and {len(ordered)}.[/red]")
            except ValueError:
                self.console.print("[red]  Enter a number, 'd <number>', or 'back'.[/red]")

    def _confirm_delete(self, draft: Dict) -> bool:
        """Prompt for delete confirmation and execute if confirmed."""
        draft_id_short = draft["draft_id"][:8] + "..."
        status = "completed" if draft["is_complete"] else "in progress"
        self.console.print(
            f"[yellow]  Delete draft {draft_id_short} ({status})? This cannot be undone.[/yellow]"
        )
        confirm = self.console.input("  Confirm delete? \\[y/N]: ").strip().lower()
        if confirm in ("y", "yes"):
            deleted = self.persistence.delete_draft(draft["draft_id"])
            if deleted:
                self.console.print("[green]  Draft deleted.[/green]")
                return True
            self.console.print("[red]  Failed to delete draft.[/red]")
        else:
            self.console.print("  Cancelled.")
        return False

    @staticmethod
    def _add_draft_table_columns(table: Table) -> None:
        """Add standard columns to a draft listing table."""
        table.add_column("#", justify="right", width=4)
        table.add_column("Draft ID", width=12)
        table.add_column("Started", width=20)
        table.add_column("Round", justify="right", width=6)
        table.add_column("Pick", justify="right", width=5)
        table.add_column("Teams", justify="right", width=6)
        table.add_column("Scoring", width=10)

    def _add_draft_table_row(self, table: Table, idx: int, draft: Dict) -> None:
        """Add a draft row to a table."""
        draft_id_short = draft["draft_id"][:8] + "..."
        scoring_name = SCORING_DISPLAY_NAMES.get(
            draft.get("scoring_format", ""), draft.get("scoring_format", "?")
        )
        table.add_row(
            str(idx),
            draft_id_short,
            draft.get("start_time", "?")[:19],
            str(draft.get("current_round", "?")),
            str(draft.get("current_pick", "?")),
            str(draft.get("league_size", "?")),
            scoring_name,
        )
