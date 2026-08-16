"""Build the per-player passing-map table from cached WhoScored/Opta events.

Featured-club-only (same source as Player DNA). One row per pass by any player
in a featured match, with origin/destination and a few type flags, so the
Player Profile can draw a season passing map for the selected player without the
app ever touching raw event JSONs.

Output (data/processed/):
  player_passes.parquet   (league, season, playerId, nkey, team, x, y, end_x,
                           end_y, outcome, prog, final_third, keypass, assist, cross)

Run:  python -m etl.build_passes --seasons 2425 2324
"""
from __future__ import annotations

import argparse
import logging
import unicodedata

import numpy as np
import pandas as pd

from etl.build_dna import FEATURED_LEAGUES, _norm
from etl.dna_events import ATT_PEN_X, FINAL_THIRD_X, load_events
from etl.io_utils import merge_season_parquet

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("build_passes")

PROG_MIN = 10.0
BOX_Y = (21.1, 78.9)


def build(seasons: list[str], leagues: list[str] | None = None) -> pd.DataFrame:
    leagues = leagues or FEATURED_LEAGUES
    ev, _meta = load_events(leagues, seasons)
    if ev.empty:
        log.warning("no cached events for %s %s", leagues, seasons)
        return pd.DataFrame()

    p = ev[(ev["type"] == "Pass")].copy()
    p = p.dropna(subset=["x", "y", "end_x", "end_y"])
    completed = p["outcome"] == 1
    p["prog"] = (completed & ((p["end_x"] - p["x"]) >= PROG_MIN)).to_numpy()
    p["final_third"] = (completed & (p["x"] < FINAL_THIRD_X)
                        & (p["end_x"] >= FINAL_THIRD_X)).to_numpy()
    p["keypass"] = p["is_keypass"].to_numpy()
    p["assist"] = p["is_assist"].to_numpy()
    p["cross"] = p["is_cross"].to_numpy()
    p["nkey"] = p["player"].map(_norm)

    out = p[["league", "season", "playerId", "nkey", "team", "x", "y",
             "end_x", "end_y", "outcome", "prog", "final_third", "keypass",
             "assist", "cross"]].copy()
    # shrink: coords float32, flags int8
    for c in ("x", "y", "end_x", "end_y"):
        out[c] = out[c].astype("float32")
    for c in ("outcome", "prog", "final_third", "keypass", "assist", "cross"):
        out[c] = out[c].astype("int8")
    out["playerId"] = out["playerId"].astype("int32")
    log.info("player_passes -> %s (%d players)", out.shape, out["playerId"].nunique())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", default=["2425"])
    ap.add_argument("--leagues", nargs="+", default=None)
    args = ap.parse_args()
    df = build(args.seasons, args.leagues)
    if df.empty:
        log.error("no passes built"); return 1
    n = merge_season_parquet(df, "player_passes", args.seasons)
    log.info("wrote player_passes (%d rows total; merged seasons %s)", n, args.seasons)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
