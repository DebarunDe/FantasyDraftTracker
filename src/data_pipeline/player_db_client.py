"""HTTP client for the DistributedDatabaseSystem player catalog.

Encapsulates all interactions with the distributed DB: table creation, season
loads (pipeline → DB), and season fetches (DB → DraftInitializer).

Float values are stored as scaled integers because the DB only supports INT,
TEXT, and BOOL:
  - Projected points and VOR: ×100  (e.g. 376.6 → 37660)
  - Stats:                     ×10   (e.g. 519.2 → 5192)

Primary key scheme: player_pk = season × 10_000 + sequential_index
This gives 10,000 slots per season and is stable across pipeline re-runs.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_SCALE_PTS = 100   # 2 decimal places for projections / VOR
_SCALE_STAT = 10   # 1 decimal place for raw stats

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class PlayerDBConnectionError(Exception):
    """Raised when the DB server is unreachable or returns an unexpected error."""


class PlayerDataNotFoundError(Exception):
    """Raised when the requested season has not been loaded into the DB."""


# ---------------------------------------------------------------------------
# Table definitions
# ---------------------------------------------------------------------------

_PLAYERS_TABLE = {
    "name": "players",
    "columns": [
        {"name": "player_pk",           "type": "INT"},
        {"name": "season",              "type": "INT"},
        {"name": "player_id",           "type": "TEXT"},
        {"name": "name",                "type": "TEXT"},
        {"name": "position",            "type": "TEXT"},
        {"name": "nfl_team",            "type": "TEXT"},
        {"name": "bye_week",            "type": "INT"},
        {"name": "tier",                "type": "INT"},
        {"name": "overall_rank",        "type": "INT"},
        {"name": "position_rank",       "type": "INT"},
        {"name": "proj_standard_x100",  "type": "INT"},
        {"name": "proj_half_ppr_x100",  "type": "INT"},
        {"name": "proj_full_ppr_x100",  "type": "INT"},
        {"name": "vor_standard_x100",   "type": "INT"},
        {"name": "vor_half_ppr_x100",   "type": "INT"},
        {"name": "vor_full_ppr_x100",   "type": "INT"},
    ],
}

_PLAYER_STATS_TABLE = {
    "name": "player_stats",
    "columns": [
        {"name": "stat_pk",       "type": "INT"},
        {"name": "player_pk",     "type": "INT"},
        {"name": "season",        "type": "INT"},
        {"name": "pass_att_x10",  "type": "INT"},
        {"name": "pass_cmp_x10",  "type": "INT"},
        {"name": "pass_yds_x10",  "type": "INT"},
        {"name": "pass_td_x10",   "type": "INT"},
        {"name": "pass_int_x10",  "type": "INT"},
        {"name": "rush_att_x10",  "type": "INT"},
        {"name": "rush_yds_x10",  "type": "INT"},
        {"name": "rush_td_x10",   "type": "INT"},
        {"name": "rec_x10",       "type": "INT"},
        {"name": "rec_yds_x10",   "type": "INT"},
        {"name": "rec_td_x10",    "type": "INT"},
        {"name": "fl_x10",        "type": "INT"},
        {"name": "fg_x10",        "type": "INT"},
        {"name": "fga_x10",       "type": "INT"},
        {"name": "xpt_x10",       "type": "INT"},
    ],
}

_SEASONS_TABLE = {
    "name": "seasons",
    "columns": [
        {"name": "season_pk",      "type": "INT"},
        {"name": "season",         "type": "INT"},
        {"name": "generated_at",   "type": "TEXT"},
        {"name": "source",         "type": "TEXT"},
        {"name": "total_players",  "type": "INT"},
    ],
}

_ALL_TABLES = [_PLAYERS_TABLE, _PLAYER_STATS_TABLE, _SEASONS_TABLE]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class PlayerDatabaseClient:
    """Wraps all HTTP interactions with the DistributedDatabaseSystem.

    Args:
        base_url: HTTP base URL of the DB server (e.g. "http://localhost:8090").
        api_key:  Bearer token configured via -api-keys on the server.
        timeout:  Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8090",
        api_key: str = "fantasy-draft-key",
        timeout: float = 30.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def ensure_tables(self) -> None:
        """Create the three player tables if they do not already exist."""
        existing = self._list_tables()
        for table_def in _ALL_TABLES:
            if table_def["name"] not in existing:
                self._create_table(table_def)
                logger.info("Created table: %s", table_def["name"])
            else:
                logger.debug("Table already exists: %s", table_def["name"])

    def _list_tables(self) -> set[str]:
        resp = self._get("/tables")
        return {t["name"] for t in resp}

    def _create_table(self, table_def: dict) -> None:
        self._post("/tables", table_def)

    # ------------------------------------------------------------------
    # Write path (pipeline → DB)
    # ------------------------------------------------------------------

    def load_season(
        self,
        players: list[dict],
        metadata: dict,
        season: int,
    ) -> None:
        """Insert or overwrite all player rows for a season.

        Writes players, then stats, then the seasons sentinel last so that
        a partially-written season never looks complete.

        Args:
            players:  List of player dicts as produced by run_update._player_to_dict().
            metadata: The "metadata" block from the pipeline JSON output.
            season:   Season year (e.g. 2025).
        """
        logger.info("Loading %d players for season %d into DB...", len(players), season)

        for idx, player in enumerate(players):
            pk = _player_pk(season, idx)
            self._insert_player_row(pk, season, player)

        for idx, player in enumerate(players):
            pk = _player_pk(season, idx)
            self._insert_stats_row(pk, season, player)

        self._insert_season_sentinel(season, metadata, len(players))
        logger.info("Season %d fully loaded into DB (%d players).", season, len(players))

    def _insert_player_row(self, pk: int, season: int, player: dict) -> None:
        proj = player.get("projections", {})
        vor = player.get("baseline_vor", {})
        self._post(
            "/tables/players/rows",
            {
                "values": {
                    "player_pk":          pk,
                    "season":             season,
                    "player_id":          player.get("player_id") or "",
                    "name":               player.get("name") or "",
                    "position":           player.get("position") or "",
                    "nfl_team":           player.get("team") or "",
                    "bye_week":           player.get("bye_week") or 0,
                    "tier":               player.get("tier") or 0,
                    "overall_rank":       player.get("overall_rank") or 0,
                    "position_rank":      player.get("position_rank") or 0,
                    "proj_standard_x100": _enc(proj.get("standard", 0.0), _SCALE_PTS),
                    "proj_half_ppr_x100": _enc(proj.get("half_ppr", 0.0), _SCALE_PTS),
                    "proj_full_ppr_x100": _enc(proj.get("full_ppr", 0.0), _SCALE_PTS),
                    "vor_standard_x100":  _enc(vor.get("standard", 0.0), _SCALE_PTS),
                    "vor_half_ppr_x100":  _enc(vor.get("half_ppr", 0.0), _SCALE_PTS),
                    "vor_full_ppr_x100":  _enc(vor.get("full_ppr", 0.0), _SCALE_PTS),
                }
            },
        )

    def _insert_stats_row(self, pk: int, season: int, player: dict) -> None:
        s = player.get("stats", {})
        self._post(
            "/tables/player_stats/rows",
            {
                "values": {
                    "stat_pk":      pk,
                    "player_pk":    pk,
                    "season":       season,
                    "pass_att_x10": _enc(s.get("pass_att", 0.0), _SCALE_STAT),
                    "pass_cmp_x10": _enc(s.get("pass_cmp", 0.0), _SCALE_STAT),
                    "pass_yds_x10": _enc(s.get("pass_yds", 0.0), _SCALE_STAT),
                    "pass_td_x10":  _enc(s.get("pass_td", 0.0), _SCALE_STAT),
                    "pass_int_x10": _enc(s.get("pass_int", 0.0), _SCALE_STAT),
                    "rush_att_x10": _enc(s.get("rush_att", 0.0), _SCALE_STAT),
                    "rush_yds_x10": _enc(s.get("rush_yds", 0.0), _SCALE_STAT),
                    "rush_td_x10":  _enc(s.get("rush_td", 0.0), _SCALE_STAT),
                    "rec_x10":      _enc(s.get("rec", 0.0), _SCALE_STAT),
                    "rec_yds_x10":  _enc(s.get("rec_yds", 0.0), _SCALE_STAT),
                    "rec_td_x10":   _enc(s.get("rec_td", 0.0), _SCALE_STAT),
                    "fl_x10":       _enc(s.get("fl", 0.0), _SCALE_STAT),
                    "fg_x10":       _enc(s.get("fg", 0.0), _SCALE_STAT),
                    "fga_x10":      _enc(s.get("fga", 0.0), _SCALE_STAT),
                    "xpt_x10":      _enc(s.get("xpt", 0.0), _SCALE_STAT),
                }
            },
        )

    def _insert_season_sentinel(
        self, season: int, metadata: dict, total_players: int
    ) -> None:
        self._post(
            "/tables/seasons/rows",
            {
                "values": {
                    "season_pk":     season,
                    "season":        season,
                    "generated_at":  metadata.get("generated_at", ""),
                    "source":        metadata.get("source", "FantasyPros"),
                    "total_players": total_players,
                }
            },
        )

    # ------------------------------------------------------------------
    # Read path (DB → DraftInitializer)
    # ------------------------------------------------------------------

    def season_exists(self, season: int) -> bool:
        """Return True if the seasons sentinel row exists for *season*."""
        try:
            rows = self._get(f"/tables/seasons/rows?where=season={season}")
            return rows.get("count", 0) > 0
        except PlayerDBConnectionError:
            return False

    def fetch_season(self, season: int) -> dict[str, dict]:
        """Fetch all players for *season* and return {player_id → player_dict}.

        The returned dicts match the structure produced by run_update._player_to_dict()
        so they can be dropped directly into DraftState.player_data.

        Raises:
            PlayerDataNotFoundError: if the seasons sentinel is absent.
            PlayerDBConnectionError: on network/HTTP failure.
        """
        # Call _get directly (not season_exists) so that network errors surface
        # as PlayerDBConnectionError rather than being swallowed and misreported
        # as PlayerDataNotFoundError.
        sentinel = self._get(f"/tables/seasons/rows?where=season={season}")
        if sentinel.get("count", 0) == 0:
            raise PlayerDataNotFoundError(
                f"Season {season} has not been loaded into the player DB. "
                "Run the pipeline with USE_PLAYER_DB=true first."
            )

        player_rows = self._get(f"/tables/players/rows?where=season={season}")
        stats_rows = self._get(f"/tables/player_stats/rows?where=season={season}")

        stats_by_pk: dict[int, dict] = {
            row["player_pk"]: row for row in stats_rows.get("rows", [])
        }

        result: dict[str, dict] = {}
        for row in player_rows.get("rows", []):
            pk = row["player_pk"]
            stats = stats_by_pk.get(pk, {})
            player = _reconstruct_player(row, stats)
            result[player["player_id"]] = player

        logger.info(
            "Fetched %d players for season %d from DB.", len(result), season
        )
        return result

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str) -> Any:
        url = self._base + path
        try:
            resp = self._client.get(url)
        except httpx.RequestError as exc:
            raise PlayerDBConnectionError(
                f"Cannot reach player DB at {url}: {exc}"
            ) from exc
        if resp.status_code >= 500:
            raise PlayerDBConnectionError(
                f"Player DB returned {resp.status_code} for GET {path}: {resp.text}"
            )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> Any:
        url = self._base + path
        try:
            resp = self._client.post(url, json=body)
        except httpx.RequestError as exc:
            raise PlayerDBConnectionError(
                f"Cannot reach player DB at {url}: {exc}"
            ) from exc
        if resp.status_code >= 500:
            raise PlayerDBConnectionError(
                f"Player DB returned {resp.status_code} for POST {path}: {resp.text}"
            )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PlayerDatabaseClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _player_pk(season: int, index: int) -> int:
    return season * 10_000 + index


def _enc(value: float, scale: int) -> int:
    """Encode a float as a scaled integer for storage in the INT column."""
    return int(round(value * scale))


def _dec(value: int, scale: int) -> float:
    """Decode a scaled integer back to float."""
    return value / scale


def _reconstruct_player(player_row: dict, stats_row: dict) -> dict:
    """Rebuild the nested player dict that DraftState expects."""
    return {
        "player_id":    player_row["player_id"],
        "name":         player_row["name"],
        "position":     player_row["position"],
        "team":         player_row["nfl_team"],
        "bye_week":     player_row["bye_week"] or None,
        "tier":         player_row["tier"] or None,
        "overall_rank": player_row["overall_rank"] or None,
        "position_rank": player_row["position_rank"] or None,
        "stats": {
            "pass_att": _dec(stats_row.get("pass_att_x10", 0), _SCALE_STAT),
            "pass_cmp": _dec(stats_row.get("pass_cmp_x10", 0), _SCALE_STAT),
            "pass_yds": _dec(stats_row.get("pass_yds_x10", 0), _SCALE_STAT),
            "pass_td":  _dec(stats_row.get("pass_td_x10", 0), _SCALE_STAT),
            "pass_int": _dec(stats_row.get("pass_int_x10", 0), _SCALE_STAT),
            "rush_att": _dec(stats_row.get("rush_att_x10", 0), _SCALE_STAT),
            "rush_yds": _dec(stats_row.get("rush_yds_x10", 0), _SCALE_STAT),
            "rush_td":  _dec(stats_row.get("rush_td_x10", 0), _SCALE_STAT),
            "rec":      _dec(stats_row.get("rec_x10", 0), _SCALE_STAT),
            "rec_yds":  _dec(stats_row.get("rec_yds_x10", 0), _SCALE_STAT),
            "rec_td":   _dec(stats_row.get("rec_td_x10", 0), _SCALE_STAT),
            "fl":       _dec(stats_row.get("fl_x10", 0), _SCALE_STAT),
            "fg":       _dec(stats_row.get("fg_x10", 0), _SCALE_STAT),
            "fga":      _dec(stats_row.get("fga_x10", 0), _SCALE_STAT),
            "xpt":      _dec(stats_row.get("xpt_x10", 0), _SCALE_STAT),
        },
        "projections": {
            "standard": _dec(player_row.get("proj_standard_x100", 0), _SCALE_PTS),
            "half_ppr": _dec(player_row.get("proj_half_ppr_x100", 0), _SCALE_PTS),
            "full_ppr": _dec(player_row.get("proj_full_ppr_x100", 0), _SCALE_PTS),
        },
        "baseline_vor": {
            "standard": _dec(player_row.get("vor_standard_x100", 0), _SCALE_PTS),
            "half_ppr": _dec(player_row.get("vor_half_ppr_x100", 0), _SCALE_PTS),
            "full_ppr": _dec(player_row.get("vor_full_ppr_x100", 0), _SCALE_PTS),
        },
    }
