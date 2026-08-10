"""Fetch aggregated player/team season stats from FBref via soccerdata.

FBref is the non-Selenium source (plain HTTP), so it's the reliable backbone
for player percentile profiles and league tables.
"""
from __future__ import annotations

import logging

import pandas as pd
import soccerdata as sd

from etl.config import LEAGUES, SEASONS, SOCCERDATA_CACHE

log = logging.getLogger(__name__)

# FBref "stat types" we need for the player-profile concept groups.
PLAYER_STAT_TYPES = [
    "standard",
    "passing",
    "passing_types",
    "shooting",
    "possession",
    "defense",
    "gca",          # goal- and shot-creating actions (decision-making / final third)
    "misc",
]


def _fbref(seasons: list[str] | None = None) -> sd.FBref:
    return sd.FBref(
        leagues=list(LEAGUES.keys()),
        seasons=seasons or SEASONS,
        data_dir=SOCCERDATA_CACHE,
    )


def fetch_player_season_stats(seasons: list[str] | None = None) -> pd.DataFrame:
    """Wide table of per-player season stats across all stat types, merged."""
    fb = _fbref(seasons)
    frames: list[pd.DataFrame] = []
    for stat_type in PLAYER_STAT_TYPES:
        try:
            df = fb.read_player_season_stats(stat_type=stat_type)
            frames.append(df)
        except Exception as exc:  # one stat type failing must not kill the rest
            log.warning("FBref player stat_type=%s failed: %s", stat_type, exc)
    if not frames:
        raise RuntimeError("FBref returned no player stats for any stat type")
    # soccerdata returns MultiIndex columns; join on the shared player index.
    merged = frames[0]
    for extra in frames[1:]:
        new_cols = [c for c in extra.columns if c not in merged.columns]
        merged = merged.join(extra[new_cols], how="outer")
    return merged


def fetch_team_season_stats(seasons: list[str] | None = None) -> pd.DataFrame:
    fb = _fbref(seasons)
    return fb.read_team_season_stats(stat_type="standard")


def fetch_standings(seasons: list[str] | None = None) -> pd.DataFrame:
    """League tables. read_schedule is the source of truth for results."""
    fb = _fbref(seasons)
    return fb.read_schedule()
