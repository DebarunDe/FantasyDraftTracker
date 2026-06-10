"""Tests for PlayerDatabaseClient (no live DB required — uses mock HTTP)."""

from unittest.mock import MagicMock, patch

import pytest

from src.data_pipeline.player_db_client import (
    PlayerDBConnectionError,
    PlayerDataNotFoundError,
    PlayerDatabaseClient,
    _dec,
    _enc,
    _player_pk,
    _reconstruct_player,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestEncDec:
    def test_enc_positive_float(self):
        assert _enc(376.6, 100) == 37660

    def test_enc_negative_float(self):
        assert _enc(-30.5, 100) == -3050

    def test_enc_zero(self):
        assert _enc(0.0, 100) == 0

    def test_dec_positive(self):
        assert _dec(37660, 100) == pytest.approx(376.6)

    def test_dec_negative(self):
        assert _dec(-3050, 100) == pytest.approx(-30.5)

    def test_roundtrip(self):
        for v in [0.0, 1.23, -45.67, 999.99]:
            assert _dec(_enc(v, 100), 100) == pytest.approx(v, abs=0.01)

    def test_stat_scale(self):
        assert _enc(519.2, 10) == 5192
        assert _dec(5192, 10) == pytest.approx(519.2)


class TestPlayerPk:
    def test_season_2025_index_0(self):
        assert _player_pk(2025, 0) == 20250000

    def test_season_2025_index_1(self):
        assert _player_pk(2025, 1) == 20250001

    def test_season_2026_does_not_collide(self):
        assert _player_pk(2026, 0) != _player_pk(2025, 0)

    def test_capacity_per_season(self):
        # 10,000 slots per season — index 9999 must not overflow into next season
        assert _player_pk(2025, 9999) < _player_pk(2026, 0)


class TestReconstructPlayer:
    def _player_row(self):
        return {
            "player_pk": 20250000,
            "player_id": "josh_allen_qb_buf",
            "name": "Josh Allen",
            "position": "QB",
            "nfl_team": "BUF",
            "bye_week": 7,
            "tier": 4,
            "overall_rank": 23,
            "position_rank": 1,
            "proj_standard_x100": 37660,
            "proj_half_ppr_x100": 37660,
            "proj_full_ppr_x100": 37660,
            "vor_standard_x100": 9966,
            "vor_half_ppr_x100": 9966,
            "vor_full_ppr_x100": 9966,
        }

    def _stats_row(self):
        return {
            "pass_att_x10": 5192,
            "pass_cmp_x10": 3325,
            "pass_yds_x10": 39041,
            "pass_td_x10": 290,
            "pass_int_x10": 104,
            "rush_att_x10": 1159,
            "rush_yds_x10": 5725,
            "rush_td_x10": 107,
            "rec_x10": 0,
            "rec_yds_x10": 0,
            "rec_td_x10": 0,
            "fl_x10": 34,
            "fg_x10": 0,
            "fga_x10": 0,
            "xpt_x10": 0,
        }

    def test_identity_fields(self):
        p = _reconstruct_player(self._player_row(), self._stats_row())
        assert p["player_id"] == "josh_allen_qb_buf"
        assert p["name"] == "Josh Allen"
        assert p["position"] == "QB"
        assert p["team"] == "BUF"
        assert p["bye_week"] == 7
        assert p["tier"] == 4
        assert p["overall_rank"] == 23
        assert p["position_rank"] == 1

    def test_projections_decoded(self):
        p = _reconstruct_player(self._player_row(), self._stats_row())
        assert p["projections"]["standard"] == pytest.approx(376.6)
        assert p["projections"]["half_ppr"] == pytest.approx(376.6)
        assert p["projections"]["full_ppr"] == pytest.approx(376.6)

    def test_vor_decoded(self):
        p = _reconstruct_player(self._player_row(), self._stats_row())
        assert p["baseline_vor"]["standard"] == pytest.approx(99.66)
        assert p["baseline_vor"]["half_ppr"] == pytest.approx(99.66)

    def test_stats_decoded(self):
        p = _reconstruct_player(self._player_row(), self._stats_row())
        assert p["stats"]["pass_att"] == pytest.approx(519.2)
        assert p["stats"]["rush_yds"] == pytest.approx(572.5)
        assert p["stats"]["fl"] == pytest.approx(3.4)

    def test_negative_vor(self):
        row = self._player_row()
        row["vor_standard_x100"] = -3050
        p = _reconstruct_player(row, self._stats_row())
        assert p["baseline_vor"]["standard"] == pytest.approx(-30.5)

    def test_missing_stats_row_defaults_to_zero(self):
        p = _reconstruct_player(self._player_row(), {})
        assert p["stats"]["pass_att"] == 0.0
        assert p["stats"]["rec"] == 0.0

    def test_zero_bye_week_becomes_none(self):
        row = self._player_row()
        row["bye_week"] = 0
        p = _reconstruct_player(row, {})
        assert p["bye_week"] is None


# ---------------------------------------------------------------------------
# PlayerDatabaseClient — HTTP interactions (mocked)
# ---------------------------------------------------------------------------


def _make_client(mock_http_client):
    """Return a PlayerDatabaseClient whose internal httpx.Client is replaced."""
    client = PlayerDatabaseClient.__new__(PlayerDatabaseClient)
    client._base = "http://localhost:8090"
    client._client = mock_http_client
    return client


def _ok_resp(body):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = body
    resp.raise_for_status.return_value = None
    return resp


def _err_resp(status, text="error"):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return resp


class TestEnsureTables:
    def test_creates_missing_tables(self):
        http = MagicMock()
        http.get.return_value = _ok_resp([])  # no tables yet
        http.post.return_value = _ok_resp({"ok": True})

        client = _make_client(http)
        client.ensure_tables()

        # Should have called POST /tables three times
        assert http.post.call_count == 3

    def test_skips_existing_tables(self):
        http = MagicMock()
        existing = [
            {"name": "players"},
            {"name": "player_stats"},
            {"name": "seasons"},
        ]
        http.get.return_value = _ok_resp(existing)
        http.post.return_value = _ok_resp({"ok": True})

        client = _make_client(http)
        client.ensure_tables()

        http.post.assert_not_called()

    def test_raises_on_server_error(self):
        http = MagicMock()
        http.get.return_value = _err_resp(500)

        client = _make_client(http)
        with pytest.raises(PlayerDBConnectionError):
            client.ensure_tables()


class TestSeasonExists:
    def test_returns_true_when_sentinel_present(self):
        http = MagicMock()
        http.get.return_value = _ok_resp({"rows": [{"season_pk": 2025}], "count": 1})

        client = _make_client(http)
        assert client.season_exists(2025) is True

    def test_returns_false_when_no_rows(self):
        http = MagicMock()
        http.get.return_value = _ok_resp({"rows": [], "count": 0})

        client = _make_client(http)
        assert client.season_exists(2025) is False

    def test_returns_false_on_connection_error(self):
        import httpx

        http = MagicMock()
        http.get.side_effect = httpx.ConnectError("refused")

        client = _make_client(http)
        assert client.season_exists(2025) is False


class TestFetchSeason:
    def _setup_fetch(self, http, player_rows, stats_rows):
        """Configure mock to return sentinel + player + stats responses."""
        sentinel_resp = _ok_resp({"rows": [{"season_pk": 2025}], "count": 1})
        players_resp = _ok_resp({"rows": player_rows, "count": len(player_rows)})
        stats_resp = _ok_resp({"rows": stats_rows, "count": len(stats_rows)})
        http.get.side_effect = [sentinel_resp, players_resp, stats_resp]

    def _minimal_player_row(self, idx=0):
        return {
            "player_pk": _player_pk(2025, idx),
            "player_id": f"player_{idx}",
            "name": f"Player {idx}",
            "position": "QB",
            "nfl_team": "BUF",
            "bye_week": 7,
            "tier": 1,
            "overall_rank": idx + 1,
            "position_rank": idx + 1,
            "proj_standard_x100": 37660,
            "proj_half_ppr_x100": 37660,
            "proj_full_ppr_x100": 37660,
            "vor_standard_x100": 9966,
            "vor_half_ppr_x100": 9966,
            "vor_full_ppr_x100": 9966,
        }

    def _minimal_stats_row(self, idx=0):
        return {
            "player_pk": _player_pk(2025, idx),
            "pass_att_x10": 5192,
            "pass_cmp_x10": 0,
            "pass_yds_x10": 0,
            "pass_td_x10": 0,
            "pass_int_x10": 0,
            "rush_att_x10": 0,
            "rush_yds_x10": 0,
            "rush_td_x10": 0,
            "rec_x10": 0,
            "rec_yds_x10": 0,
            "rec_td_x10": 0,
            "fl_x10": 0,
            "fg_x10": 0,
            "fga_x10": 0,
            "xpt_x10": 0,
        }

    def test_returns_dict_keyed_by_player_id(self):
        http = MagicMock()
        self._setup_fetch(
            http,
            [self._minimal_player_row(0), self._minimal_player_row(1)],
            [self._minimal_stats_row(0), self._minimal_stats_row(1)],
        )

        client = _make_client(http)
        result = client.fetch_season(2025)

        assert "player_0" in result
        assert "player_1" in result
        assert len(result) == 2

    def test_player_dict_has_expected_keys(self):
        http = MagicMock()
        self._setup_fetch(
            http,
            [self._minimal_player_row(0)],
            [self._minimal_stats_row(0)],
        )

        client = _make_client(http)
        result = client.fetch_season(2025)
        p = result["player_0"]

        for key in ("player_id", "name", "position", "team", "bye_week",
                    "tier", "overall_rank", "position_rank",
                    "stats", "projections", "baseline_vor"):
            assert key in p, f"Missing key: {key}"

    def test_raises_when_season_not_found(self):
        http = MagicMock()
        http.get.return_value = _ok_resp({"rows": [], "count": 0})

        client = _make_client(http)
        with pytest.raises(PlayerDataNotFoundError):
            client.fetch_season(2099)

    def test_raises_on_network_error(self):
        import httpx

        http = MagicMock()
        http.get.side_effect = httpx.ConnectError("refused")

        client = _make_client(http)
        with pytest.raises(PlayerDBConnectionError):
            client.fetch_season(2025)

    def test_stats_merged_by_player_pk(self):
        http = MagicMock()
        p_row = self._minimal_player_row(0)
        s_row = self._minimal_stats_row(0)
        s_row["pass_att_x10"] = 5192
        self._setup_fetch(http, [p_row], [s_row])

        client = _make_client(http)
        result = client.fetch_season(2025)
        assert result["player_0"]["stats"]["pass_att"] == pytest.approx(519.2)


class TestLoadSeason:
    def test_inserts_rows_then_sentinel(self):
        http = MagicMock()
        http.post.return_value = _ok_resp({"ok": True})

        client = _make_client(http)
        players = [
            {
                "player_id": "p1",
                "name": "P1",
                "position": "QB",
                "team": "BUF",
                "bye_week": 7,
                "tier": 1,
                "overall_rank": 1,
                "position_rank": 1,
                "projections": {"standard": 300.0, "half_ppr": 300.0, "full_ppr": 300.0},
                "baseline_vor": {"standard": 50.0, "half_ppr": 50.0, "full_ppr": 50.0},
                "stats": {k: 0.0 for k in (
                    "pass_att", "pass_cmp", "pass_yds", "pass_td", "pass_int",
                    "rush_att", "rush_yds", "rush_td", "rec", "rec_yds",
                    "rec_td", "fl", "fg", "fga", "xpt"
                )},
            }
        ]
        metadata = {"generated_at": "2025-01-01T00:00:00Z", "source": "FantasyPros"}

        client.load_season(players, metadata, season=2025)

        # 1 player row + 1 stats row + 1 seasons sentinel = 3 POST calls
        assert http.post.call_count == 3

    def test_player_pk_uses_season_encoding(self):
        http = MagicMock()
        http.post.return_value = _ok_resp({"ok": True})

        client = _make_client(http)
        players = [
            {
                "player_id": "p1", "name": "P1", "position": "QB", "team": "BUF",
                "bye_week": 7, "tier": 1, "overall_rank": 1, "position_rank": 1,
                "projections": {"standard": 0.0, "half_ppr": 0.0, "full_ppr": 0.0},
                "baseline_vor": {"standard": 0.0, "half_ppr": 0.0, "full_ppr": 0.0},
                "stats": {k: 0.0 for k in (
                    "pass_att", "pass_cmp", "pass_yds", "pass_td", "pass_int",
                    "rush_att", "rush_yds", "rush_td", "rec", "rec_yds",
                    "rec_td", "fl", "fg", "fga", "xpt"
                )},
            }
        ]
        client.load_season(players, {}, season=2025)

        # First POST is the players row; check player_pk
        first_call_body = http.post.call_args_list[0][1]["json"]
        assert first_call_body["values"]["player_pk"] == _player_pk(2025, 0)
