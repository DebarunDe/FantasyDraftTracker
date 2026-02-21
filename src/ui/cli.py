"""Main CLI application for the Fantasy Draft Tracker."""

import logging
from typing import Dict, List, Optional

from rich.console import Console

from src.draft_manager.draft_controller import DraftController
from src.draft_manager.draft_initializer import DraftInitializer
from src.draft_manager.draft_rules import DraftRules, ValidationError
from src.draft_manager.draft_state import DraftState
from src.draft_manager.state_persistence import StatePersistence
from src.simulation_engine.computer_drafter import ComputerDrafter
from src.simulation_engine.vor_calculator import DynamicVORCalculator
from src.ui.config import AVAILABLE_PLAYERS_DEFAULT_LIMIT, VOR_RECOMMENDATIONS_COUNT
from src.ui.display import DraftDisplay
from src.ui.player_search import PlayerSearcher
from src.ui.setup_wizard import SetupWizard

logger = logging.getLogger(__name__)


class DraftApp:
    """Main CLI application for the Fantasy Draft Tracker."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.display = DraftDisplay(self.console)
        self.persistence = StatePersistence()
        self.draft_state: Optional[DraftState] = None
        self.controller: Optional[DraftController] = None
        self.vor_calculator: Optional[DynamicVORCalculator] = None
        self.computer_drafter: Optional[ComputerDrafter] = None
        self.searcher: Optional[PlayerSearcher] = None
        self.last_displayed_players: List[Dict] = []

    def run(self) -> None:
        """Main application entry point."""
        while True:
            wizard = SetupWizard(self.console, self.persistence)
            result = wizard.run()

            if result["action"] == "quit":
                self.console.print("Goodbye!")
                return

            if result["action"] == "new":
                self._create_new_draft(result)
            elif result["action"] == "resume":
                self._resume_draft(result["draft_state"])

            self.console.print()
            self.display.show_success("Draft is ready! Entering draft loop...")
            self.console.print()

            if self._draft_loop():
                return  # User quit mid-draft — "Goodbye!" already printed

            if self.controller and self.controller.is_complete:
                summary = self.controller.get_draft_summary()
                self.display.show_draft_summary(
                    summary, self.draft_state.league_config.scoring_format
                )
                self._post_draft_menu()

    def _create_new_draft(self, config: Dict) -> None:
        """Create a new draft from wizard configuration."""
        initializer = DraftInitializer()
        self.draft_state = initializer.create_draft(
            league_size=config["league_size"],
            scoring_format=config["scoring_format"],
            roster_slots=config["roster_slots"],
            team_names=config["team_names"],
            human_team_id=config["human_team_id"],
            data_year=config["data_year"],
        )
        self._init_components()
        self.persistence.save_draft(self.draft_state)

    def _resume_draft(self, draft_state: DraftState) -> None:
        """Resume a saved draft."""
        self.draft_state = draft_state
        self._init_components()
        self.display.show_success(
            f"Resumed draft at Round {draft_state.current_round}, "
            f"Pick {draft_state.current_pick}"
        )

    def _init_components(self) -> None:
        """Initialize controller, VOR calculator, computer drafter, and searcher."""
        self.controller = DraftController(self.draft_state)
        self.vor_calculator = DynamicVORCalculator(
            self.draft_state.league_config.scoring_format,
            self.draft_state.league_config.league_size,
        )
        self.computer_drafter = ComputerDrafter(
            vor_calculator=self.vor_calculator,
            strategy="balanced",
        )
        self.searcher = PlayerSearcher(self.controller)

    def _draft_loop(self) -> bool:
        """Main draft pick loop. Returns True if the user quit mid-draft."""
        while not self.controller.is_complete:
            if not self._handle_pick_turn():
                return True  # User quit
        return False

    def _handle_pick_turn(self) -> bool:
        """Handle a single pick turn. Returns False if user quit."""
        current_team = self.draft_state.get_current_team()

        if not current_team.is_human:
            return self._handle_computer_turn()

        # Human turn: show full board and wait for input
        self._show_draft_board()
        player_id = self._get_user_pick()
        if player_id is None:
            return False

        self._execute_pick(player_id)
        return True

    def _handle_computer_turn(self) -> bool:
        """Auto-pick for a computer team using the ADP-blended ComputerDrafter.

        Returns True if a pick was made, False if no legal pick was available.
        """
        current_team = self.draft_state.get_current_team()
        self.console.print(
            f"\n[dim]  {current_team.team_name} is on the clock...[/dim]"
        )

        available = self.controller.get_available_players()

        # Filter to players this team can legally draft (position limits respected).
        # The VOR scores may rank a player highly even when that position slot is full.
        rules = DraftRules(self.draft_state)
        legal = [
            p for p in available
            if rules.validate_pick(current_team.team_id, p["player_id"])[0]
        ]

        if not legal:
            logger.warning(
                "No legal picks for %s — roster may be full", current_team.team_name
            )
            return False

        player_id = self.computer_drafter.make_pick(
            self.draft_state, legal, current_team.team_id
        )
        self._execute_pick(player_id)
        return True

    def _show_draft_board(self) -> None:
        """Display current draft board."""
        self.last_displayed_players = []
        self.console.print()
        self.display.show_draft_header(self.draft_state)

        if self.draft_state.all_picks:
            self.display.show_recent_picks(
                self.draft_state.all_picks,
                self.draft_state.player_data,
                self.draft_state.teams,
            )

        self._show_recommendations()

        self.console.print()
        self.console.print(
            "[dim]\\[name/# to pick] \\[a]vailable \\[r]oster "
            "\\[s]earch \\[rec] \\[h]elp \\[q]uit[/dim]"
        )

    def _get_user_pick(self) -> Optional[str]:
        """Get player_id from user input. Returns None if user quits."""
        current_team = self.draft_state.get_current_team()
        if current_team.is_human:
            prompt = f"[bold]{current_team.team_name} Pick > [/bold]"
        else:
            prompt = f"[bold]Enter pick for {current_team.team_name} > [/bold]"

        while True:
            try:
                raw = self.console.input(prompt).strip()
            except EOFError:
                self._handle_quit()
                return None

            if not raw:
                continue

            parsed = self.searcher.parse_input(raw)

            if parsed["type"] == "command":
                result = self._handle_command(parsed["command"], parsed["args"])
                if result in ("quit", "simulate"):
                    return None
                if result == "redisplay":
                    self._show_draft_board()
                continue

            if parsed["type"] == "number":
                if not self.last_displayed_players:
                    self.display.show_error(
                        "No player list displayed yet. "
                        "Use [a]vailable or [rec] first."
                    )
                    continue
                player = self.searcher.resolve_by_number(
                    parsed["value"], self.last_displayed_players
                )
                if player is None:
                    self.display.show_error(
                        f"No player at #{parsed['value']}. "
                        f"Valid range: 1-{len(self.last_displayed_players)}"
                    )
                    continue
                confirmed = self._confirm_pick(player)
                if confirmed:
                    return confirmed
                continue

            # Name search
            results = self.searcher.search(parsed["query"])
            if not results:
                self.display.show_error(
                    f"No available players matching '{parsed['query']}'"
                )
                continue

            if len(results) == 1:
                confirmed = self._confirm_pick(results[0])
                if confirmed:
                    return confirmed
                continue

            # Multiple matches — show list for disambiguation
            scoring = self.draft_state.league_config.scoring_format
            self.display.show_search_results(results, scoring)
            self.last_displayed_players = results
            self.console.print("[dim]Enter # to select, or search again[/dim]")

    def _confirm_pick(self, player: Dict) -> Optional[str]:
        """Ask user to confirm a pick. Returns player_id or None."""
        name = player.get("name", "?")
        pos = player.get("position", "?")
        team = player.get("team", "?")

        try:
            raw = self.console.input(
                f"  Draft [bold]{name}[/bold] ({pos} - {team})? [Y/n]: "
            ).strip().lower()
        except EOFError:
            return None

        if raw in ("", "y", "yes"):
            return player.get("player_id")
        return None

    def _execute_pick(self, player_id: str) -> None:
        """Execute a pick, show banner, and auto-save."""
        current_team_id = self.draft_state.current_team_id
        try:
            pick = self.controller.make_pick(current_team_id, player_id)
        except ValidationError as e:
            self.display.show_error(str(e))
            return

        player_info = self.draft_state.get_player_info(player_id)
        team = self.draft_state.get_team(pick.team_id)
        self.display.show_pick_banner(pick, player_info, team.team_name)

        try:
            self.persistence.save_draft(self.draft_state)
        except OSError as e:
            self.display.show_error(f"Auto-save failed: {e}")

    def _handle_command(self, command: str, args: str) -> Optional[str]:
        """Handle a CLI command. Returns 'quit', 'redisplay', or None."""
        scoring = self.draft_state.league_config.scoring_format

        if command in ("q", "quit"):
            self._handle_quit()
            return "quit"

        if command in ("h", "help"):
            self.display.show_help()
            return None

        if command in ("b", "board"):
            return "redisplay"

        if command in ("a", "available"):
            self._handle_available(args, scoring)
            return None

        if command in ("r", "roster"):
            self._handle_roster(args, scoring)
            return None

        if command in ("s", "search"):
            self._handle_search(args, scoring)
            return None

        if command in ("rec", "recommend"):
            self._show_recommendations()
            return None

        if command == "save":
            try:
                self.persistence.save_draft(self.draft_state)
                self.display.show_success("Draft saved.")
            except OSError as e:
                self.display.show_error(f"Save failed: {e}")
            return None

        if command in ("sim", "simulate"):
            return self._simulate_rest_of_draft()

        return None

    def _simulate_rest_of_draft(self) -> Optional[str]:
        """Auto-pick all remaining turns (human and computer) using ComputerDrafter.

        Returns 'simulate' when the draft is complete so the caller can exit
        the input loop and hand off to the post-draft summary.  Returns None if
        the user cancels.
        """
        try:
            raw = self.console.input(
                "Simulate all remaining picks? [Y/n]: "
            ).strip().lower()
        except EOFError:
            return None

        if raw not in ("", "y", "yes"):
            return None

        self.console.print("\n[dim]Simulating remaining picks...[/dim]\n")
        while not self.controller.is_complete:
            if not self._handle_computer_turn():
                self.display.show_error("Simulation stopped: a team has no legal picks.")
                break

        if self.controller.is_complete:
            self.display.show_success("Simulation complete!")
            return "simulate"
        return None

    def _handle_available(self, args: str, scoring: str) -> None:
        """Handle 'available' command with optional position/limit args."""
        position = None
        limit = AVAILABLE_PLAYERS_DEFAULT_LIMIT
        parts = args.strip().split()

        for part in parts:
            upper = part.upper()
            if upper in ("QB", "RB", "WR", "TE", "K", "DST"):
                position = upper
            else:
                try:
                    limit = int(part)
                except ValueError:
                    pass

        players = self.controller.get_available_players(position=position)

        # Sort by baseline VOR for the current scoring format
        players.sort(
            key=lambda p: p.get("baseline_vor", {}).get(scoring, 0),
            reverse=True,
        )

        displayed = self.display.show_available_players(
            players, scoring, limit=limit
        )
        self.last_displayed_players = displayed

    def _handle_roster(self, args: str, scoring: str) -> None:
        """Handle 'roster' command with optional team number."""
        team_id = self.draft_state.current_team_id
        if args.strip():
            try:
                n = int(args.strip())
                if 1 <= n <= self.draft_state.league_config.league_size:
                    team_id = n - 1
                else:
                    self.display.show_error(
                        f"Team number must be 1-{self.draft_state.league_config.league_size}"
                    )
                    return
            except ValueError:
                self.display.show_error("Usage: r [team_number]")
                return

        team = self.draft_state.get_team(team_id)
        roster = self.controller.get_team_roster(team_id)
        self.display.show_team_roster(
            team.team_name,
            roster,
            scoring,
            self.draft_state.league_config.roster_slots,
        )

    def _handle_search(self, args: str, scoring: str) -> None:
        """Handle 'search' command."""
        if not args.strip():
            self.display.show_error("Usage: s <player name>")
            return

        results = self.searcher.search(args.strip())
        if not results:
            self.display.show_error(f"No available players matching '{args.strip()}'")
            return

        self.display.show_search_results(results, scoring)
        self.last_displayed_players = results

    def _show_recommendations(self) -> None:
        """Show VOR-based recommendations for the current team."""
        current_team = self.draft_state.get_current_team()
        vor_results = self.vor_calculator.calculate_from_draft_state(
            self.draft_state, current_team.team_id
        )
        scoring = self.draft_state.league_config.scoring_format
        displayed = self.display.show_vor_recommendations(
            vor_results,
            self.draft_state.player_data,
            scoring,
            limit=VOR_RECOMMENDATIONS_COUNT,
        )
        self.last_displayed_players = displayed

    def _handle_quit(self) -> None:
        """Save state and exit."""
        if self.draft_state and not self.draft_state.is_complete:
            try:
                self.persistence.save_draft(self.draft_state)
                self.display.show_success("Draft saved.")
            except OSError as e:
                self.display.show_error(f"Failed to save: {e}")
        self.console.print("Goodbye!")

    def _post_draft_menu(self) -> None:
        """After draft completion, let user view rosters."""
        scoring = self.draft_state.league_config.scoring_format
        self.console.print()

        while True:
            try:
                raw = self.console.input(
                    "View team roster? [team #/all/quit to menu]: "
                ).strip().lower()
            except EOFError:
                break

            if raw in ("q", "quit", ""):
                break

            if raw == "all":
                for team in self.draft_state.teams:
                    roster = self.controller.get_team_roster(team.team_id)
                    self.display.show_team_roster(
                        team.team_name,
                        roster,
                        scoring,
                        self.draft_state.league_config.roster_slots,
                    )
                continue

            try:
                n = int(raw)
                if 1 <= n <= self.draft_state.league_config.league_size:
                    team = self.draft_state.get_team(n - 1)
                    roster = self.controller.get_team_roster(n - 1)
                    self.display.show_team_roster(
                        team.team_name,
                        roster,
                        scoring,
                        self.draft_state.league_config.roster_slots,
                    )
                else:
                    self.display.show_error(
                        f"Team number must be 1-{self.draft_state.league_config.league_size}"
                    )
            except ValueError:
                self.display.show_error("Enter a team number, 'all', or 'quit'.")


def main():
    """Entry point for the Fantasy Draft Tracker CLI."""
    from src.logging_config import setup_logging

    setup_logging(log_level="WARNING")

    app = DraftApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app.console.print("\n[yellow]Draft interrupted. Saving state...[/yellow]")
        if app.draft_state and not app.draft_state.is_complete:
            try:
                app.persistence.save_draft(app.draft_state)
                app.console.print("[green]State saved successfully.[/green]")
            except Exception:
                app.console.print("[red]Failed to save state.[/red]")
        app.console.print("Goodbye!")


if __name__ == "__main__":
    main()
