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

from etl.config import CURRENT_SEASON, LEAGUES, SEASONS, SOCCERDATA_CACHE
from etl.understat_patch import apply_patch
from etl.understat_source import read_with_retry

log = logging.getLogger(__name__)

KEEP = ["league", "season", "game_id", "team", "player", "xg", "location_x",
        "location_y", "minute", "body_part", "situation", "result",
        "assist_player"]


def fetch_shots(seasons: list[str] | None = None) -> pd.DataFrame:
    # Fetch per-(league, season): a single malformed match (a known soccerdata
    # Understat roster-parse bug that hits some Bundesliga games) then only skips
    # its own season, instead of wiping out a whole league across all seasons.
    apply_patch()  # fix soccerdata's list-roster crash (recovers Bundesliga)
    seasons = seasons or SEASONS
    frames = []
    for lg in LEAGUES:
        for sn in seasons:
            try:
                us = sd.Understat(leagues=lg, seasons=sn, data_dir=Path(SOCCERDATA_CACHE),
                                  no_cache=(sn == CURRENT_SEASON))
                fr = read_with_retry(
                    lambda us=us: us.read_shot_events().reset_index(),
                    f"shots {lg} {sn}", tries=5)
                frames.append(fr)
                log.info("shots fetched: %s %s (%d)", lg, sn, len(fr))
            except Exception as exc:
                log.warning("shots FAILED %s %s (skipped): %s", lg, sn, exc)
    if not frames:
        raise RuntimeError("Understat shot events failed for all league-seasons")
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
