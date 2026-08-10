"""Thin data-access layer for the Streamlit app.

Pages NEVER read Parquet directly (tech spec §6) — they call these functions,
which own st.cache_data so repeated navigation doesn't re-read from disk.
Also the single place that degrades gracefully when a refresh left data absent.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

PROCESSED = Path(__file__).resolve().parent / "data" / "processed"


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    """Load a processed table by name, or empty DataFrame if not yet built."""
    path = PROCESSED / f"{name}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def last_updated(name: str = "poc_player_stats") -> str:
    """Human 'data last updated' string for the stale-data note (design §5)."""
    path = PROCESSED / f"{name}.parquet"
    if not path.exists():
        return "no data yet"
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return ts.strftime("%Y-%m-%d %H:%M UTC")


def has_data() -> bool:
    return PROCESSED.exists() and any(PROCESSED.glob("*.parquet"))
