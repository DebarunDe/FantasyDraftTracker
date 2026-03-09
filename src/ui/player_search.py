"""Player search and input parsing for the CLI."""

from typing import Dict, List, Optional

from src.draft_manager.draft_controller import DraftController
from src.ui.config import COMMANDS, SEARCH_RESULTS_LIMIT

# Name suffixes to strip for matching
_SUFFIXES = (" jr.", " sr.", " iii", " ii", " iv", " v")


class PlayerSearcher:
    """Resolve user input to a player from available players."""

    def __init__(self, controller: DraftController):
        self.controller = controller

    def parse_input(self, raw: str) -> Dict:
        """Parse user input to determine intent.

        Returns one of:
            {"type": "command", "command": str, "args": str}
            {"type": "number", "value": int}
            {"type": "name", "query": str}
        """
        stripped = raw.strip()
        if not stripped:
            return {"type": "name", "query": ""}

        parts = stripped.split(maxsplit=1)
        first = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if first in COMMANDS:
            return {"type": "command", "command": first, "args": args}

        try:
            value = int(stripped)
            return {"type": "number", "value": value}
        except ValueError:
            pass

        return {"type": "name", "query": stripped}

    def search(self, query: str, position: Optional[str] = None) -> List[Dict]:
        """Search available players by name.

        Multi-pass strategy:
        1. Exact full name match (case-insensitive, suffix-normalized)
        2. Starts-with match
        3. Substring match
        4. Token match (all query words must appear in name)

        Returns list of matching player dicts sorted by overall_rank.
        """
        query_norm = normalize_name(query)
        if not query_norm:
            return []

        available = self.controller.get_available_players(position=position)

        # Pass 1: Exact match
        exact = [p for p in available if normalize_name(p["name"]) == query_norm]
        if exact:
            return _sort_by_rank(exact)

        # Pass 2: Starts-with
        starts = [p for p in available if normalize_name(p["name"]).startswith(query_norm)]
        if starts:
            return _sort_by_rank(starts)

        # Pass 3: Substring
        substring = [p for p in available if query_norm in normalize_name(p["name"])]
        if substring:
            return _sort_by_rank(substring)[:SEARCH_RESULTS_LIMIT]

        # Pass 4: Token match (all words must appear)
        tokens = query_norm.split()
        if tokens:
            token_match = [
                p for p in available if all(t in normalize_name(p["name"]) for t in tokens)
            ]
            return _sort_by_rank(token_match)[:SEARCH_RESULTS_LIMIT]

        return []

    @staticmethod
    def resolve_by_number(number: int, player_list: List[Dict]) -> Optional[Dict]:
        """Resolve a 1-based number selection from a displayed list."""
        if 1 <= number <= len(player_list):
            return player_list[number - 1]
        return None


def normalize_name(name: str) -> str:
    """Normalize a player name for comparison.

    Lowercases and strips common suffixes (Jr., Sr., III, II, IV, V).
    """
    normalized = name.strip().lower()
    for suffix in _SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
            break
    return normalized


def _sort_by_rank(players: List[Dict]) -> List[Dict]:
    """Sort players by overall_rank ascending (best first)."""
    return sorted(players, key=lambda p: p.get("overall_rank", 999))
