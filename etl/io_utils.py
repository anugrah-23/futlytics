"""Safe Parquet I/O with atomic writes.

Resilience requirement (tech spec §4, §7): never leave data/ half-written.
Write to a temp path, then atomically replace the target so the app always
reads a complete file or the previous good one.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from etl.config import PROCESSED_DIR, TMP_DIR


# --- memory optimisation -----------------------------------------------------
# Repetitive text columns balloon ~50x in RAM as object dtype (e.g. player_passes
# was 835MB, mostly 4 string columns over 2.8M rows) and OOM the ~1GB Streamlit
# Community Cloud instance. Store them as category (int codes + tiny lookup) so
# the app loads compactly. Excludes columns used as groupby keys downstream
# (playerId is int; pass_networks.label is grouped in viz.average_pass_network),
# and drops columns the app never reads. Baked into write_parquet_atomic so the
# weekly refresh keeps producing lean data.
_CATEGORICAL: dict[str, list[str]] = {
    "player_passes": ["league", "season", "nkey"],
    "player_dna": ["league", "season", "player", "team", "pos_group", "nkey",
                   "concept", "param_key", "label", "unit"],
    "player_metrics": ["league", "season", "team", "player", "concept",
                       "metric_key", "label", "unit"],
    "shots": ["league", "season", "team", "player", "body_part", "situation",
              "result", "assist_player"],
    "pass_networks": ["league", "season", "team", "kind", "match"],
}
_DROP: dict[str, list[str]] = {
    "player_passes": ["team"],   # not used by the passing map; ~186MB in RAM
}


def optimize_dtypes(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Drop unused columns and downcast repetitive text to category for <name>."""
    drop = [c for c in _DROP.get(name, []) if c in df.columns]
    if drop:
        df = df.drop(columns=drop)
    cats = [c for c in _CATEGORICAL.get(name, []) if c in df.columns]
    if cats:
        df = df.astype({c: "category" for c in cats})
    return df


def write_parquet_atomic(df: pd.DataFrame, name: str) -> Path:
    """Write df to data/processed/<name>.parquet atomically.

    Returns the final path. On any failure the previous file is untouched.
    """
    df = optimize_dtypes(df, name)
    target = PROCESSED_DIR / f"{name}.parquet"
    tmp = TMP_DIR / f"{name}.parquet.tmp"
    df.to_parquet(tmp, index=False)
    os.replace(tmp, target)  # atomic on same filesystem
    return target


def merge_season_parquet(df: pd.DataFrame, name: str, seasons: list[str]) -> int:
    """Replace the given seasons' rows in <name>.parquet with df's freshly built
    rows, preserving every other (frozen) season, then write atomically.

    Lets an incremental job rebuild only the live season without discarding
    history. An empty/None df is a no-op (returns -1) so a transient blank fetch
    can't wipe committed data. Returns the merged row count.
    """
    if df is None or df.empty:
        return -1
    target = PROCESSED_DIR / f"{name}.parquet"
    if target.exists() and "season" in df.columns:
        old = pd.read_parquet(target)
        if "season" in old.columns:
            old = old[~old["season"].isin(seasons)]
            df = pd.concat([old, df], ignore_index=True)
    write_parquet_atomic(df, name)
    return len(df)


def read_parquet(name: str) -> pd.DataFrame:
    """Read data/processed/<name>.parquet. Raises FileNotFoundError if absent."""
    path = PROCESSED_DIR / f"{name}.parquet"
    return pd.read_parquet(path)


def exists(name: str) -> bool:
    return (PROCESSED_DIR / f"{name}.parquet").exists()
