"""Phase 0 proof-of-concept: pull ONE league/season end to end and verify.

Run:  python -m etl.poc_pull
Goal: prove soccerdata works in this environment, inspect the shape/quality of
FBref output, and exercise the per-90 + percentile transforms on real data
before building any UI. Writes nothing to data/processed unless --write given.
"""
from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("poc")

POC_LEAGUE = "ENG-Premier League"
POC_SEASON = "2425"


def main(write: bool) -> int:
    import soccerdata as sd  # imported here so --help works without deps

    from etl.config import SOCCERDATA_CACHE
    from etl.transform import (
        per90,
        percentile_within_group,
        primary_position_group,
        is_limited_sample,
    )

    log.info("Pulling FBref standard player stats: %s %s", POC_LEAGUE, POC_SEASON)
    fb = sd.FBref(leagues=POC_LEAGUE, seasons=POC_SEASON, data_dir=SOCCERDATA_CACHE)
    df = fb.read_player_season_stats(stat_type="standard")
    log.info("Rows: %d  Cols: %d", len(df), df.shape[1])

    # soccerdata returns a MultiIndex on both axes; flatten for inspection.
    flat = df.copy()
    flat.columns = ["_".join(str(c) for c in col).strip("_") for col in flat.columns]
    flat = flat.reset_index()

    # Locate the minutes column (FBref: Playing Time -> Min).
    mins_col = next((c for c in flat.columns if c.lower().endswith("min")
                     and "90" not in c.lower()), None)
    pos_col = next((c for c in flat.columns if c.lower().endswith("pos")), None)
    gls_col = next((c for c in flat.columns if c.lower().endswith("_gls")
                    or c.lower() == "gls"), None)
    log.info("Detected columns -> minutes=%s position=%s goals=%s",
             mins_col, pos_col, gls_col)

    if not all([mins_col, pos_col, gls_col]):
        log.error("Could not auto-detect required columns. Columns present:\n%s",
                  "\n".join(flat.columns))
        return 2

    minutes = pd.to_numeric(flat[mins_col], errors="coerce").fillna(0)
    goals = pd.to_numeric(flat[gls_col], errors="coerce").fillna(0)
    grp = flat[pos_col].map(primary_position_group)

    flat["goals_per90"] = per90(goals, minutes)
    flat["goals_pct"] = percentile_within_group(flat["goals_per90"], grp, minutes)
    flat["limited_sample"] = is_limited_sample(minutes)

    ranked = flat[~flat["limited_sample"]].sort_values("goals_per90", ascending=False)
    log.info("Top 5 by goals/90 (min-minutes qualified):")
    cols = [c for c in ["player", pos_col, mins_col, "goals_per90", "goals_pct"]
            if c in ranked.columns]
    print(ranked[cols].head().to_string(index=False))

    log.info("Limited-sample players excluded from ranks: %d / %d",
             int(flat["limited_sample"].sum()), len(flat))

    if write:
        from etl.io_utils import write_parquet_atomic
        path = write_parquet_atomic(flat, "poc_player_stats")
        log.info("Wrote %s", path)

    log.info("PoC OK — soccerdata + transforms verified end to end.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="persist the flattened sample to data/processed/")
    args = ap.parse_args()
    sys.exit(main(args.write))
