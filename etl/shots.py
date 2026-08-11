"""Shot-event data from Understat for the Team Dashboard shot map.

Understat gives every shot with xG, pitch location, situation and result —
enough for a shots-for / shots-against map with xG-weighted markers. Reliable
HTTP source (no Selenium), unlike the event data the other tactical views need.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import soccerdata as sd

from etl.config import LEAGUES, SEASONS, SOCCERDATA_CACHE
from etl.understat_source import read_with_retry

log = logging.getLogger(__name__)

KEEP = ["league", "season", "game_id", "team", "player", "xg", "location_x",
        "location_y", "minute", "body_part", "situation", "result",
        "assist_player"]


def fetch_shots(seasons: list[str] | None = None) -> pd.DataFrame:
    # Fetch per-league so a single malformed match (a known soccerdata Understat
    # roster-parse bug) can't wipe out every league's shot data.
    frames = []
    for lg in LEAGUES:
        try:
            us = sd.Understat(leagues=lg, seasons=seasons or SEASONS,
                              data_dir=Path(SOCCERDATA_CACHE))
            frames.append(read_with_retry(
                lambda us=us: us.read_shot_events().reset_index(), f"shots {lg}"))
            log.info("shots fetched: %s", lg)
        except Exception as exc:
            log.warning("shots FAILED for %s (skipped): %s", lg, exc)
    if not frames:
        raise RuntimeError("Understat shot events failed for all leagues")
    df = pd.concat(frames, ignore_index=True)
    df = df[[c for c in KEEP if c in df.columns]].copy()
    df["xg"] = pd.to_numeric(df["xg"], errors="coerce")
    # Understat coords are 0-1 with x toward the attacked goal; scale to 0-100
    # (mplsoccer 'opta' pitch) for plotting.
    df["x"] = pd.to_numeric(df["location_x"], errors="coerce") * 100.0
    df["y"] = pd.to_numeric(df["location_y"], errors="coerce") * 100.0
    df["is_goal"] = df["result"].eq("Goal")
    df = df.drop(columns=["location_x", "location_y"])
    log.info("shots -> %s", df.shape)
    return df


def main() -> int:
    import argparse

    from etl.io_utils import write_parquet_atomic

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", default=["2425"])
    args = ap.parse_args()
    df = fetch_shots(args.seasons)
    write_parquet_atomic(df, "shots")
    log.info("wrote shots (%d rows)", len(df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
