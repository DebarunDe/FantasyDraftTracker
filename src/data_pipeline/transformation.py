"""Data transformation for FantasyPros data.

Merges the five cleaned DataFrames into a single unified player table:
- Combines QB, FLEX (RB/WR/TE), K, and DST projections
- Calculates Standard, Half-PPR, and Full-PPR scoring variants
- Merges projection data with rankings data
- Generates unique player IDs
"""

import logging
import math

import pandas as pd

from src.data_pipeline.cleaning import DataCleaner  # noqa: F401 – used for strip_name_suffix

logger = logging.getLogger(__name__)

# Sentinel values for players missing from the rankings file
UNRANKED_OVERALL = 999
UNRANKED_TIER = 99

# Keys expected in the cleaned data dict passed to transform()
_REQUIRED_KEYS = {"qb", "flex", "k", "dst", "rankings"}


class DataTransformer:
    """Merges and transforms cleaned FantasyPros data."""

    # ------------------------------------------------------------------
    # Merge all projection files into one DataFrame
    # ------------------------------------------------------------------
    def merge_projections(
        self,
        qb_df: pd.DataFrame,
        flex_df: pd.DataFrame,
        k_df: pd.DataFrame,
        dst_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Combine all projection DataFrames into a unified table.

        Every row will have:
            Player, Player_Norm, Team_Abbr, Position, FPTS, and all stat columns.
        Missing stats for a position are filled with 0.
        """
        rows: list[dict] = []

        # --- QBs ---
        for _, r in qb_df.iterrows():
            rows.append(self._make_row(
                r, position="QB",
                pass_att=r.get("Pass_Att", 0),
                pass_cmp=r.get("Pass_Cmp", 0),
                pass_yds=r.get("Pass_Yds", 0),
                pass_td=r.get("Pass_TD", 0),
                pass_int=r.get("Pass_Int", 0),
                rush_att=r.get("Rush_Att", 0),
                rush_yds=r.get("Rush_Yds", 0),
                rush_td=r.get("Rush_TD", 0),
                fl=r.get("FL", 0),
            ))

        # --- FLEX (RB / WR / TE) ---
        for _, r in flex_df.iterrows():
            rows.append(self._make_row(
                r, position=r.get("Position", "FLEX"),
                rush_att=r.get("Rush_Att", 0),
                rush_yds=r.get("Rush_Yds", 0),
                rush_td=r.get("Rush_TD", 0),
                rec=r.get("Rec", 0),
                rec_yds=r.get("Rec_Yds", 0),
                rec_td=r.get("Rec_TD", 0),
                fl=r.get("FL", 0),
            ))

        # --- Kickers ---
        for _, r in k_df.iterrows():
            rows.append(self._make_row(
                r, position="K",
                fg=r.get("FG", 0),
                fga=r.get("FGA", 0),
                xpt=r.get("XPT", 0),
            ))

        # --- DST ---
        for _, r in dst_df.iterrows():
            rows.append(self._make_row(
                r, position="DST",
            ))

        merged = pd.DataFrame(rows)
        logger.info("Merged projections: %d total players", len(merged))
        return merged

    @staticmethod
    def _safe_float(val, default: float = 0.0) -> float:
        """Convert *val* to float, replacing None/NaN with *default*."""
        if val is None or val is pd.NA or (isinstance(val, float) and math.isnan(val)):
            return default
        return float(val)

    def _make_row(
        self,
        row: pd.Series,
        position: str,
        pass_att: float = 0, pass_cmp: float = 0,
        pass_yds: float = 0, pass_td: float = 0, pass_int: float = 0,
        rush_att: float = 0, rush_yds: float = 0, rush_td: float = 0,
        rec: float = 0, rec_yds: float = 0, rec_td: float = 0,
        fl: float = 0,
        fg: float = 0, fga: float = 0, xpt: float = 0,
    ) -> dict:
        """Build a unified row dict from a source row and explicit stats."""
        sf = self._safe_float
        return {
            "Player": row.get("Player") or row.get("PLAYER NAME"),
            "Player_Norm": row.get("Player_Norm"),
            "Team_Abbr": row.get("Team_Abbr"),
            "Position": position,
            "FPTS": sf(row.get("FPTS")),
            "Pass_Att": sf(pass_att),
            "Pass_Cmp": sf(pass_cmp),
            "Pass_Yds": sf(pass_yds),
            "Pass_TD": sf(pass_td),
            "Pass_Int": sf(pass_int),
            "Rush_Att": sf(rush_att),
            "Rush_Yds": sf(rush_yds),
            "Rush_TD": sf(rush_td),
            "Rec": sf(rec),
            "Rec_Yds": sf(rec_yds),
            "Rec_TD": sf(rec_td),
            "FL": sf(fl),
            "FG": sf(fg),
            "FGA": sf(fga),
            "XPT": sf(xpt),
        }

    # ------------------------------------------------------------------
    # Scoring variants
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_scoring_variants(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Standard, Half-PPR, and Full-PPR projected points.

        The FPTS column from FantasyPros is Full PPR (1 point per reception).
        We derive the other formats by subtracting reception value.

        Adds columns: FPTS_Standard, FPTS_HalfPPR, FPTS_FullPPR
        """
        out = df.copy()
        rec = out["Rec"].fillna(0)

        out["FPTS_FullPPR"] = out["FPTS"]
        out["FPTS_HalfPPR"] = out["FPTS"] - (rec * 0.5)
        out["FPTS_Standard"] = out["FPTS"] - rec

        logger.info("Calculated scoring variants for %d players", len(out))
        return out

    # ------------------------------------------------------------------
    # Merge with rankings
    # ------------------------------------------------------------------
    @staticmethod
    def merge_with_rankings(
        projections_df: pd.DataFrame,
        rankings_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge projections with rankings data (overall rank, bye week, tier).

        Uses a two-pass strategy to handle inconsistent name suffixes
        (e.g. "James Cook III" in projections vs "James Cook" in rankings)
        without risking incorrect merges for distinct players who share
        a base name (e.g. Marvin Harrison vs Marvin Harrison Jr.).

        Pass 1: Exact match on (Player_Norm, Position).
        Pass 2: For still-unmatched rows, match on suffix-stripped name.
        """
        strip = DataCleaner.strip_name_suffix

        # Columns to pull from rankings
        rank_cols = [
            "Player_Norm", "Position", "RK", "Pos_Rank",
            "BYE WEEK", "TIERS", "ECR VS. ADP",
        ]
        available = [c for c in rank_cols if c in rankings_df.columns]
        rank_subset = rankings_df[available].copy()

        # Drop duplicate keys so the left join stays 1:1
        rank_subset = rank_subset.drop_duplicates(
            subset=["Player_Norm", "Position"], keep="first"
        )

        # Columns that the merge will add (used to detect matched rows)
        rank_value_cols = [c for c in rank_subset.columns
                          if c not in ("Player_Norm", "Position")]

        # --- Pass 1: exact match ---
        merged = projections_df.merge(
            rank_subset,
            on=["Player_Norm", "Position"],
            how="left",
            validate="m:1",
        )

        # Identify rows that didn't match (RK is null)
        unmatched = merged["RK"].isna() if "RK" in merged.columns else pd.Series(True, index=merged.index)
        n_pass1 = (~unmatched).sum()

        # --- Pass 2: suffix-stripped fallback for unmatched rows ---
        if unmatched.any():
            # Build suffix-stripped keys for unmatched projections
            unmatched_df = merged.loc[unmatched].copy()
            unmatched_df["_base_name"] = unmatched_df["Player_Norm"].apply(strip)

            # Build suffix-stripped keys for rankings (only rows not
            # already consumed by pass 1)
            matched_rank_keys = set(
                zip(
                    merged.loc[~unmatched, "Player_Norm"],
                    merged.loc[~unmatched, "Position"],
                )
            )
            rank_remaining = rank_subset[
                ~rank_subset.apply(
                    lambda r: (r["Player_Norm"], r["Position"]) in matched_rank_keys,
                    axis=1,
                )
            ].copy()
            rank_remaining["_base_name"] = rank_remaining["Player_Norm"].apply(strip)
            rank_remaining = rank_remaining.drop_duplicates(
                subset=["_base_name", "Position"], keep="first"
            )

            # Drop pass-1 rank columns from unmatched rows before re-merging
            unmatched_df = unmatched_df.drop(columns=rank_value_cols, errors="ignore")

            fallback = unmatched_df.merge(
                rank_remaining.drop(columns=["Player_Norm"]).rename(
                    columns={"_base_name": "_base_name"}
                ),
                on=["_base_name", "Position"],
                how="left",
            )

            n_pass2 = fallback["RK"].notna().sum() if "RK" in fallback.columns else 0
            if n_pass2:
                logger.info(
                    "Suffix-stripped fallback matched %d additional player(s)", n_pass2
                )

            # Drop helper column and splice back
            fallback = fallback.drop(columns=["_base_name"])
            merged = pd.concat(
                [merged.loc[~unmatched], fallback], ignore_index=True
            )

        # Rename for clarity
        rename_map = {
            "RK": "Overall_Rank",
            "BYE WEEK": "Bye_Week",
            "TIERS": "Tier",
            "ECR VS. ADP": "ECR_vs_ADP",
        }
        merged = merged.rename(
            columns={k: v for k, v in rename_map.items() if k in merged.columns}
        )

        # Fill missing ranking data for players not in the rankings file
        if "Overall_Rank" in merged.columns:
            merged["Overall_Rank"] = merged["Overall_Rank"].fillna(UNRANKED_OVERALL).astype(int)
        if "Tier" in merged.columns:
            merged["Tier"] = merged["Tier"].fillna(UNRANKED_TIER).astype(int)

        total_matched = merged["Overall_Rank"].ne(UNRANKED_OVERALL).sum() if "Overall_Rank" in merged.columns else 0
        logger.info(
            "Merged with rankings: %d matched (%d exact, %d fallback), %d unmatched",
            total_matched, n_pass1, total_matched - n_pass1,
            merged["Overall_Rank"].eq(UNRANKED_OVERALL).sum() if "Overall_Rank" in merged.columns else len(merged),
        )
        return merged

    # ------------------------------------------------------------------
    # Player IDs
    # ------------------------------------------------------------------
    @staticmethod
    def generate_player_ids(df: pd.DataFrame) -> pd.DataFrame:
        """Generate unique player IDs.

        Format: {name}_{position}_{team}
        Example: jamarr_chase_wr_cin
        """
        def _make_id(row):
            name = str(row.get("Player_Norm") or row.get("Player") or "unknown")
            name = (
                name.lower()
                .replace("'", "")
                .replace(".", "")
                .replace("-", "_")
                .replace(" ", "_")
            )
            pos = str(row.get("Position", "unk")).lower()
            team = str(row.get("Team_Abbr") or "fa").lower()
            return f"{name}_{pos}_{team}"

        out = df.copy()
        out["player_id"] = out.apply(_make_id, axis=1)

        # Disambiguate collisions by appending a numeric suffix
        dupes = out["player_id"].duplicated(keep=False)
        if dupes.any():
            dupe_ids = out.loc[dupes, "player_id"].unique().tolist()
            logger.warning("Duplicate player_ids detected: %s", dupe_ids)
            for pid in dupe_ids:
                mask = out["player_id"] == pid
                suffixes = range(1, mask.sum() + 1)
                out.loc[mask, "player_id"] = [
                    f"{pid}_{i}" for i in suffixes
                ]

        logger.info("Generated %d player IDs", len(out))
        return out

    # ------------------------------------------------------------------
    # Full transformation pipeline
    # ------------------------------------------------------------------
    def transform(
        self, cleaned: dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """Run the full transformation pipeline on cleaned data.

        Args:
            cleaned: dict from DataCleaner.clean_all() with keys
                     rankings, qb, flex, k, dst.

        Returns:
            Unified DataFrame with all players, scoring variants,
            rankings data, and player IDs.

        Raises:
            ValueError: if *cleaned* is missing any required keys.
        """
        missing = _REQUIRED_KEYS - cleaned.keys()
        if missing:
            raise ValueError(f"Missing required DataFrames: {missing}")

        # 1. Merge all projections
        merged = self.merge_projections(
            cleaned["qb"], cleaned["flex"], cleaned["k"], cleaned["dst"],
        )

        # 2. Calculate scoring variants
        merged = self.calculate_scoring_variants(merged)

        # 3. Merge with rankings
        merged = self.merge_with_rankings(merged, cleaned["rankings"])

        # 4. Generate player IDs
        merged = self.generate_player_ids(merged)

        logger.info("Transformation complete: %d players", len(merged))
        return merged
