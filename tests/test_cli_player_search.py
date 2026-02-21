"""Tests for CLI player search and input parsing."""

import pytest

from src.draft_manager.draft_controller import DraftController
from src.draft_manager.draft_state import DraftState, LeagueConfig
from src.ui.player_search import PlayerSearcher, normalize_name


# ── Helpers ──────────────────────────────────────────────────────────


def _make_league_config(**overrides):
    defaults = {
        "league_id": "test",
        "league_size": 4,
        "scoring_format": "half_ppr",
        "draft_type": "snake",
        "draft_mode": "simulation",
        "data_year": 2025,
        "roster_slots": {
            "QB": 1, "RB": 2, "WR": 2, "TE": 1,
            "FLEX": 1, "DST": 1, "K": 1, "BENCH": 6,
        },
    }
    defaults.update(overrides)
    return LeagueConfig(**defaults)


def _make_player_data():
    """Create players with realistic names for search testing."""
    players = {}
    specs = [
        ("josh_allen_qb_buf", "Josh Allen", "QB", "BUF", 1),
        ("jalen_hurts_qb_phi", "Jalen Hurts", "QB", "PHI", 2),
        ("saquon_barkley_rb_phi", "Saquon Barkley", "RB", "PHI", 3),
        ("breece_hall_rb_nyj", "Breece Hall", "RB", "NYJ", 4),
        ("jamarr_chase_wr_cin", "Ja'Marr Chase", "WR", "CIN", 5),
        ("ceedee_lamb_wr_dal", "CeeDee Lamb", "WR", "DAL", 6),
        ("amon_ra_st_brown_wr_det", "Amon-Ra St. Brown", "WR", "DET", 7),
        ("travis_kelce_te_kc", "Travis Kelce", "TE", "KC", 8),
        ("james_cook_rb_buf", "James Cook III", "RB", "BUF", 9),
        ("bijan_robinson_rb_atl", "Bijan Robinson", "RB", "ATL", 10),
        ("odell_beckham_wr_mia", "Odell Beckham Jr.", "WR", "MIA", 11),
        ("irv_smith_te_cin", "Irv Smith Jr.", "TE", "CIN", 12),
        ("devonta_smith_wr_phi", "DeVonta Smith", "WR", "PHI", 13),
        ("k1", "Tyler Bass", "K", "BUF", 14),
        ("dst1", "Philadelphia Eagles", "DST", "PHI", 15),
    ]
    for pid, name, pos, team, rank in specs:
        players[pid] = {
            "player_id": pid,
            "name": name,
            "position": pos,
            "team": team,
            "overall_rank": rank,
            "projections": {
                "standard": 100.0,
                "half_ppr": 110.0,
                "full_ppr": 120.0,
            },
            "baseline_vor": {
                "standard": 20.0,
                "half_ppr": 22.0,
                "full_ppr": 24.0,
            },
        }
    return players


def _make_searcher():
    """Create a PlayerSearcher with test data."""
    config = _make_league_config()
    player_data = _make_player_data()
    team_names = [f"Team {i+1}" for i in range(4)]
    draft_state = DraftState.create_new(
        league_config=config,
        team_names=team_names,
        human_team_id=0,
        player_data=player_data,
    )
    controller = DraftController(draft_state)
    return PlayerSearcher(controller)


# ── normalize_name tests ─────────────────────────────────────────────


class TestNormalizeName:
    def test_lowercase(self):
        assert normalize_name("Josh Allen") == "josh allen"

    def test_strips_jr(self):
        assert normalize_name("Odell Beckham Jr.") == "odell beckham"

    def test_strips_iii(self):
        assert normalize_name("James Cook III") == "james cook"

    def test_strips_sr(self):
        assert normalize_name("Some Player Sr.") == "some player"

    def test_strips_ii(self):
        assert normalize_name("Player Name II") == "player name"

    def test_strips_iv(self):
        assert normalize_name("Player Name IV") == "player name"

    def test_strips_v(self):
        assert normalize_name("Player Name V") == "player name"

    def test_no_suffix(self):
        assert normalize_name("Ja'Marr Chase") == "ja'marr chase"

    def test_strips_whitespace(self):
        assert normalize_name("  Josh Allen  ") == "josh allen"


# ── parse_input tests ────────────────────────────────────────────────


class TestParseInput:
    def setup_method(self):
        self.searcher = _make_searcher()

    def test_number(self):
        result = self.searcher.parse_input("3")
        assert result == {"type": "number", "value": 3}

    def test_command_available(self):
        result = self.searcher.parse_input("a")
        assert result["type"] == "command"
        assert result["command"] == "a"

    def test_command_available_with_args(self):
        result = self.searcher.parse_input("a qb")
        assert result["type"] == "command"
        assert result["command"] == "a"
        assert result["args"] == "qb"

    def test_command_roster(self):
        result = self.searcher.parse_input("r")
        assert result["type"] == "command"
        assert result["command"] == "r"

    def test_command_roster_with_team(self):
        result = self.searcher.parse_input("roster 3")
        assert result["type"] == "command"
        assert result["command"] == "roster"
        assert result["args"] == "3"

    def test_command_search(self):
        result = self.searcher.parse_input("s kelce")
        assert result["type"] == "command"
        assert result["command"] == "s"
        assert result["args"] == "kelce"

    def test_command_help(self):
        result = self.searcher.parse_input("h")
        assert result["type"] == "command"
        assert result["command"] == "h"

    def test_command_quit(self):
        result = self.searcher.parse_input("q")
        assert result["type"] == "command"
        assert result["command"] == "q"

    def test_command_recommend(self):
        result = self.searcher.parse_input("rec")
        assert result["type"] == "command"
        assert result["command"] == "rec"

    def test_command_save(self):
        result = self.searcher.parse_input("save")
        assert result["type"] == "command"
        assert result["command"] == "save"

    def test_name_query(self):
        result = self.searcher.parse_input("patrick mahomes")
        assert result == {"type": "name", "query": "patrick mahomes"}

    def test_empty_input(self):
        result = self.searcher.parse_input("")
        assert result["type"] == "name"
        assert result["query"] == ""

    def test_whitespace_only(self):
        result = self.searcher.parse_input("   ")
        assert result["type"] == "name"
        assert result["query"] == ""


# ── search tests ─────────────────────────────────────────────────────


class TestSearch:
    def setup_method(self):
        self.searcher = _make_searcher()

    def test_exact_match(self):
        results = self.searcher.search("Josh Allen")
        assert len(results) == 1
        assert results[0]["name"] == "Josh Allen"

    def test_case_insensitive(self):
        results = self.searcher.search("josh allen")
        assert len(results) == 1
        assert results[0]["name"] == "Josh Allen"

    def test_starts_with(self):
        results = self.searcher.search("josh al")
        assert len(results) >= 1
        assert results[0]["name"] == "Josh Allen"

    def test_substring_match(self):
        results = self.searcher.search("kelce")
        assert len(results) == 1
        assert results[0]["name"] == "Travis Kelce"

    def test_token_match(self):
        results = self.searcher.search("ja chase")
        assert len(results) == 1
        assert results[0]["name"] == "Ja'Marr Chase"

    def test_suffix_normalized_match(self):
        """'james cook' should match 'James Cook III' via suffix normalization."""
        results = self.searcher.search("james cook")
        assert len(results) == 1
        assert results[0]["name"] == "James Cook III"

    def test_no_results(self):
        results = self.searcher.search("zzzznonexistent")
        assert results == []

    def test_empty_query(self):
        results = self.searcher.search("")
        assert results == []

    def test_multiple_matches_sorted_by_rank(self):
        """'smith' should match multiple players, sorted by rank."""
        results = self.searcher.search("smith")
        assert len(results) >= 2
        ranks = [r["overall_rank"] for r in results]
        assert ranks == sorted(ranks)

    def test_position_filter(self):
        results = self.searcher.search("allen", position="QB")
        assert all(r["position"] == "QB" for r in results)

    def test_position_filter_excludes_other_positions(self):
        results = self.searcher.search("smith", position="TE")
        assert all(r["position"] == "TE" for r in results)
        assert len(results) == 1
        assert results[0]["name"] == "Irv Smith Jr."


# ── resolve_by_number tests ──────────────────────────────────────────


class TestResolveByNumber:
    def test_valid_number(self):
        players = [{"player_id": "a"}, {"player_id": "b"}, {"player_id": "c"}]
        result = PlayerSearcher.resolve_by_number(2, players)
        assert result["player_id"] == "b"

    def test_first_number(self):
        players = [{"player_id": "a"}, {"player_id": "b"}]
        result = PlayerSearcher.resolve_by_number(1, players)
        assert result["player_id"] == "a"

    def test_last_number(self):
        players = [{"player_id": "a"}, {"player_id": "b"}, {"player_id": "c"}]
        result = PlayerSearcher.resolve_by_number(3, players)
        assert result["player_id"] == "c"

    def test_zero_returns_none(self):
        players = [{"player_id": "a"}]
        assert PlayerSearcher.resolve_by_number(0, players) is None

    def test_negative_returns_none(self):
        players = [{"player_id": "a"}]
        assert PlayerSearcher.resolve_by_number(-1, players) is None

    def test_out_of_range_returns_none(self):
        players = [{"player_id": "a"}, {"player_id": "b"}]
        assert PlayerSearcher.resolve_by_number(5, players) is None

    def test_empty_list_returns_none(self):
        assert PlayerSearcher.resolve_by_number(1, []) is None
