"""Run the complete FantasyPros data pipeline.

Usage:
    python -m src.data_pipeline.run_update [year] [data_dir]

Examples:
    python -m src.data_pipeline.run_update 2025
    python -m src.data_pipeline.run_update 2025 /path/to/csvs
"""

import json
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.data_pipeline.cleaning import DataCleaner
from src.data_pipeline.config import PROCESSED_DATA_DIR, RAW_DATA_DIR
from src.data_pipeline.ingestion import FantasyProsIngester
from src.data_pipeline.transformation import DataTransformer
from src.data_pipeline.vor_calculation import VORCalculator
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)


def _safe(val, default=None):
    """Return *default* when *val* is NaN/None/pd.NA, else the value."""
    if val is None or val is pd.NA:
        return default
    if isinstance(val, float) and math.isnan(val):
        return default
    return val


def _safe_int(val):
    """Convert *val* to int, returning None for non-numeric values (e.g. '-')."""
    val = _safe(val)
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _player_to_dict(row: pd.Series) -> dict:
    """Convert a single player row to the output JSON structure."""
    sf = _safe

    return {
        "player_id": row["player_id"],
        "name": row["Player"],
        "position": str(row["Position"]) if _safe(row.get("Position")) is not None else None,
        "team": sf(row.get("Team_Abbr")),
        "bye_week": _safe_int(row.get("Bye_Week")),
        "tier": _safe_int(row.get("Tier")),
        "overall_rank": _safe_int(row.get("Overall_Rank")),
        "position_rank": _safe_int(row.get("Pos_Rank")),
        "stats": {
            "pass_att": float(sf(row.get("Pass_Att"), 0)),
            "pass_cmp": float(sf(row.get("Pass_Cmp"), 0)),
            "pass_yds": float(sf(row.get("Pass_Yds"), 0)),
            "pass_td": float(sf(row.get("Pass_TD"), 0)),
            "pass_int": float(sf(row.get("Pass_Int"), 0)),
            "rush_att": float(sf(row.get("Rush_Att"), 0)),
            "rush_yds": float(sf(row.get("Rush_Yds"), 0)),
            "rush_td": float(sf(row.get("Rush_TD"), 0)),
            "rec": float(sf(row.get("Rec"), 0)),
            "rec_yds": float(sf(row.get("Rec_Yds"), 0)),
            "rec_td": float(sf(row.get("Rec_TD"), 0)),
            "fl": float(sf(row.get("FL"), 0)),
            "fg": float(sf(row.get("FG"), 0)),
            "fga": float(sf(row.get("FGA"), 0)),
            "xpt": float(sf(row.get("XPT"), 0)),
        },
        "projections": {
            "standard": float(sf(row.get("FPTS_Standard"), 0)),
            "half_ppr": float(sf(row.get("FPTS_HalfPPR"), 0)),
            "full_ppr": float(sf(row.get("FPTS_FullPPR"), 0)),
        },
        "baseline_vor": {
            "standard": float(sf(row.get("VOR_Standard"), 0)),
            "half_ppr": float(sf(row.get("VOR_HalfPPR"), 0)),
            "full_ppr": float(sf(row.get("VOR_FullPPR"), 0)),
        },
    }


def run_pipeline(
    year: int = 2025,
    data_dir: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Run the complete FantasyPros data pipeline.

    Args:
        year: Season year.
        data_dir: Directory containing raw CSVs.
            Defaults to ``data/raw/{year}``.
        output_dir: Directory for JSON output.
            Defaults to ``data/processed/``.

    Returns:
        Path to the generated JSON file.

    Raises:
        FileNotFoundError: If the data directory doesn't exist.
    """
    if data_dir is None:
        data_dir = RAW_DATA_DIR / str(year)
    if output_dir is None:
        output_dir = PROCESSED_DATA_DIR

    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    logger.info("Starting pipeline for %d season (data: %s)", year, data_dir)

    # 1. Ingest
    logger.info("Step 1/5: Ingesting CSV files...")
    ingester = FantasyProsIngester(data_dir, year)
    raw = ingester.read_all()
    logger.info(
        "Loaded: %d rankings, %d QBs, %d FLEX, %d Ks, %d DSTs",
        len(raw["rankings"]), len(raw["qb"]),
        len(raw["flex"]), len(raw["k"]), len(raw["dst"]),
    )

    # 2. Clean
    logger.info("Step 2/5: Cleaning data...")
    cleaner = DataCleaner()
    cleaned = cleaner.clean_all(raw)

    # 3. Transform
    logger.info("Step 3/5: Transforming and merging data...")
    transformer = DataTransformer()
    players_df = transformer.transform(cleaned)
    logger.info("Transformed: %d total players", len(players_df))

    # 3b. Drop players with no recognized position
    no_pos = players_df["Position"].isna()
    if no_pos.any():
        logger.warning(
            "Dropping %d players with no recognized position: %s",
            no_pos.sum(),
            players_df.loc[no_pos, "Player"].tolist(),
        )
        players_df = players_df[~no_pos].reset_index(drop=True)

    # 4. VOR
    logger.info("Step 4/5: Calculating baseline VOR...")
    vor_calc = VORCalculator()
    players_df = vor_calc.calculate_baseline_vor(players_df, league_size=12)

    # 5. Output JSON
    logger.info("Step 5/5: Generating JSON output...")
    players_list = [_player_to_dict(row) for _, row in players_df.iterrows()]

    output_data = {
        "metadata": {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "FantasyPros",
            "season": year,
            "league_size": 12,
            "scoring_systems": ["standard", "half_ppr", "full_ppr"],
            "total_players": len(players_list),
        },
        "players": players_list,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"players_{year}.json"

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    # Update latest symlink
    latest_link = output_dir / "players_latest.json"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(output_file.name)

    # Summary
    pos_counts: dict[str, int] = {}
    for p in players_list:
        pos = p["position"] or "UNKNOWN"
        pos_counts[pos] = pos_counts.get(pos, 0) + 1

    logger.info("Pipeline complete! Output: %s", output_file)
    logger.info("  Total players: %d", len(players_list))
    logger.info(
        "  By position: %s",
        ", ".join(f"{k}={v}" for k, v in sorted(pos_counts.items())),
    )

    return output_file


if __name__ == "__main__":
    setup_logging()

    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    data_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    try:
        output = run_pipeline(year, data_dir)
        print(f"Pipeline complete: {output}")
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)
