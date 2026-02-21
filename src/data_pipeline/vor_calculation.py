"""Baseline VOR (Value Over Replacement) calculation.

For each position and scoring format, identifies the "replacement player"
(the N-th best player, where N is the number typically drafted in a 12-team
league) and computes every player's value relative to that baseline.
"""

import logging

import pandas as pd

from src.data_pipeline.config import calculate_baseline_count

logger = logging.getLogger(__name__)

# Scoring format suffixes matching columns produced by DataTransformer
_SCORING_FORMATS = ("Standard", "HalfPPR", "FullPPR")


class VORCalculator:
    """Calculate baseline VOR for each player across scoring formats."""

    def calculate_baseline_vor(
        self,
        players_df: pd.DataFrame,
        league_size: int = 12,
    ) -> pd.DataFrame:
        """Add VOR columns to *players_df*.

        For each position and scoring format:
        1. Sort players by projected points (descending).
        2. Calculate league-size-dependent baseline count.
        3. Average ±1 rank around baseline for robustness (Petersen method).
        4. VOR = player_fpts - replacement_fpts.

        Negative VOR is preserved — it indicates a below-replacement player.

        Args:
            players_df: DataFrame with columns ``Position`` and
                ``FPTS_Standard``, ``FPTS_HalfPPR``, ``FPTS_FullPPR``.
            league_size: Number of teams in the league.

        Returns:
            Copy of *players_df* with added columns
            ``VOR_Standard``, ``VOR_HalfPPR``, ``VOR_FullPPR``.
        """
        out = players_df.copy()
        positions = out["Position"].unique()

        for fmt in _SCORING_FORMATS:
            fpts_col = f"FPTS_{fmt}"
            vor_col = f"VOR_{fmt}"
            out[vor_col] = 0.0

            for position in positions:
                baseline_count = calculate_baseline_count(position, league_size)
                pos_mask = out["Position"] == position
                pos_df = (
                    out.loc[pos_mask]
                    .dropna(subset=[fpts_col])
                    .sort_values(fpts_col, ascending=False)
                )

                if pos_df.empty:
                    continue

                # Replacement index: the first player outside the baseline
                repl_idx = min(baseline_count, len(pos_df) - 1)

                # Average ±1 rank for robustness (Petersen methodology)
                repl_low = max(0, repl_idx - 1)
                repl_high = min(len(pos_df) - 1, repl_idx + 1)
                replacement_fpts = pos_df.iloc[repl_low:repl_high + 1][fpts_col].mean()

                out.loc[pos_mask, vor_col] = (
                    out.loc[pos_mask, fpts_col] - replacement_fpts
                )

                logger.debug(
                    "VOR %s %s: replacement=#%d (%.1f pts avg), range=[%.1f, %.1f]",
                    fmt, position, repl_idx + 1, replacement_fpts,
                    out.loc[pos_mask, vor_col].max(),
                    out.loc[pos_mask, vor_col].min(),
                )

        logger.info(
            "Calculated baseline VOR for %d players (%d-team league)",
            len(out), league_size,
        )
        return out
