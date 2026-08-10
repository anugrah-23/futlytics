"""Fetch match event data from WhoScored (Opta) via soccerdata.

This scraper is Selenium-based and the most fragile part of the pipeline
(tech spec §11). It requires a headless Chrome/Chromium on the runner.
Keep it isolated so a WhoScored failure never blocks the FBref-backed
player profiles / league tables.
"""
from __future__ import annotations

import logging

import pandas as pd
import soccerdata as sd

from etl.config import LEAGUES, SOCCERDATA_CACHE

log = logging.getLogger(__name__)


def _whoscored(seasons: list[str]) -> sd.WhoScored:
    return sd.WhoScored(
        leagues=list(LEAGUES.keys()),
        seasons=seasons,
        data_dir=SOCCERDATA_CACHE,
        headless=True,
    )


def fetch_events_for_matches(seasons: list[str], match_ids: list[int]) -> pd.DataFrame:
    """Pull event streams for specific matches (event-level pitch data).

    We fetch by explicit match id rather than whole seasons to stay within
    free-tier compute/etiquette limits — the team dashboard uses samples,
    not every match at once.
    """
    ws = _whoscored(seasons)
    frames: list[pd.DataFrame] = []
    for mid in match_ids:
        try:
            frames.append(ws.read_events(match_id=mid))
        except Exception as exc:
            log.warning("WhoScored events for match_id=%s failed: %s", mid, exc)
    if not frames:
        raise RuntimeError("WhoScored returned no events for any requested match")
    return pd.concat(frames, ignore_index=True)


def fetch_schedule(seasons: list[str]) -> pd.DataFrame:
    """WhoScored schedule → the match_id list that read_events needs."""
    return _whoscored(seasons).read_schedule()
