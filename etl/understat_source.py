"""Understat player season stats: xG / xA / key passes — the analytical layer
FBref no longer serves.

Understat shares FBref's (league, season, team, player) index and league keys,
so cross-source joining is a normalized-name match within league+season.
Uses soccerdata's Understat reader (tls-client bypasses Cloudflare).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, TypeVar

import pandas as pd
import soccerdata as sd

from etl.config import CURRENT_SEASON, LEAGUES, SEASONS, SOCCERDATA_CACHE

log = logging.getLogger(__name__)

# Understat metrics we consume (all populated).
UNDERSTAT_COLUMNS = ["goals", "xg", "np_goals", "np_xg", "assists", "xa",
                     "shots", "key_passes", "xg_chain", "xg_buildup"]

T = TypeVar("T")


def read_with_retry(fn: Callable[[], T], what: str,
                    tries: int = 8, base_delay: float = 5.0) -> T:
    """Call ``fn``, retrying on transient Understat drops with exponential
    backoff (capped). understat.com intermittently forcibly closes the tls
    connection; a single request usually lands within a few tries.
    """
    last: Exception | None = None
    for i in range(tries):
        try:
            return fn()
        except Exception as exc:  # tls/connection resets, 429s, parse hiccups
            last = exc
            wait = min(base_delay * (2 ** i), 90.0)
            log.warning("Understat %s failed (try %d/%d): %s — retry in %.0fs",
                        what, i + 1, tries, exc, wait)
            time.sleep(wait)
    raise RuntimeError(f"Understat {what} failed after {tries} tries") from last


def read_per_season(reader_fn: Callable[[str, str], pd.DataFrame],
                    seasons: list[str], what: str) -> pd.DataFrame:
    """Fetch each (league, season) as its OWN retryable request.

    Finest-grained resume: soccerdata caches per league-season, so a drop on
    one request never discards another's progress. reader_fn(league, season)
    must build a single-league/single-season reader and return its frame.
    """
    frames = []
    for lg in LEAGUES:
        for sn in seasons:
            df = read_with_retry(lambda lg=lg, sn=sn: reader_fn(lg, sn),
                                 f"{what} {lg} {sn}")
            frames.append(df)
            time.sleep(1.5)  # polite spacing between requests
    return pd.concat(frames, ignore_index=True)


def fetch(seasons: list[str] | None = None) -> pd.DataFrame:
    """Tidy Understat table indexed by (league, season, team, player)."""
    seasons = seasons or SEASONS

    def _one(lg: str, sn: str) -> pd.DataFrame:
        # Live season re-fetched fresh (its cached page freezes otherwise);
        # historical seasons stay cached. See standings._team_match_stats.
        us = sd.Understat(leagues=lg, seasons=sn, data_dir=Path(SOCCERDATA_CACHE),
                          no_cache=(sn == CURRENT_SEASON))
        return us.read_player_season_stats().reset_index()

    df = read_per_season(_one, seasons, "player stats")
    keep = ["league", "season", "team", "player"] + [
        c for c in UNDERSTAT_COLUMNS if c in df.columns
    ]
    out = df[keep].copy()
    log.info("Understat -> %s", out.shape)
    return out
