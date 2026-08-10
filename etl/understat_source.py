"""Understat player season stats: xG / xA / key passes — the analytical layer
FBref no longer serves.

Understat shares FBref's (league, season, team, player) index and league keys,
so cross-source joining is a normalized-name match within league+season.
Uses soccerdata's Understat reader (tls-client bypasses Cloudflare).
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import soccerdata as sd

from etl.config import LEAGUES, SEASONS, SOCCERDATA_CACHE

log = logging.getLogger(__name__)

# Understat metrics we consume (all populated).
UNDERSTAT_COLUMNS = ["goals", "xg", "np_goals", "np_xg", "assists", "xa",
                     "shots", "key_passes", "xg_chain", "xg_buildup"]


def fetch(seasons: list[str] | None = None) -> pd.DataFrame:
    """Tidy Understat table indexed by (league, season, team, player)."""
    us = sd.Understat(
        leagues=list(LEAGUES.keys()),
        seasons=seasons or SEASONS,
        data_dir=Path(SOCCERDATA_CACHE),
    )
    df = us.read_player_season_stats().reset_index()
    keep = ["league", "season", "team", "player"] + [
        c for c in UNDERSTAT_COLUMNS if c in df.columns
    ]
    out = df[keep].copy()
    log.info("Understat -> %s", out.shape)
    return out
