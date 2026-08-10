"""Pass networks from WhoScored/Opta event data (OFFLINE batch — never run by
the app at request time; Selenium is too slow/fragile for that).

For a match, per team: node = a player's average successful-pass origin, sized
by involvement; edge = pass volume between a teammate pair (receiver via Opta's
related_player_id). Output appended to data/processed/pass_networks.parquet as
a long table (kind = node | edge) the Team Dashboard reads.

Run:  python -m etl.pass_networks --match 1821050
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
import soccerdata as sd

from etl.config import LEAGUES, SOCCERDATA_CACHE
from etl.io_utils import PROCESSED_DIR, write_parquet_atomic

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pass_networks")

MIN_PAIR_PASSES = 3   # edges below this are visual noise
TOP_N = 11            # approximate the starting XI by involvement


def _team_network(te: pd.DataFrame, league: str, season: str,
                  team: str, match: str) -> pd.DataFrame | None:
    # Receiver = the next same-team touch (Opta's related_player_id is unset on
    # passes here). te is already in chronological order and team-filtered, so
    # shift(-1) gives the next time this team touched the ball.
    te = te.copy()
    te["receiver"] = te["player"].shift(-1)

    passes = te[(te["type"] == "Pass") & (te["outcome_type"] == "Successful")].copy()
    passes = passes.dropna(subset=["x", "y", "player"])
    if passes.empty:
        return None

    nodes = (passes.groupby("player")
             .agg(x=("x", "mean"), y=("y", "mean"), involvement=("x", "size"))
             .reset_index())
    top = nodes.sort_values("involvement", ascending=False).head(TOP_N)
    keep = set(top["player"])

    e = passes.dropna(subset=["receiver"])
    e = e[e["player"].isin(keep) & e["receiver"].isin(keep)]
    e = e[e["player"] != e["receiver"]]
    pair = e.assign(a=e[["player", "receiver"]].min(axis=1),
                    b=e[["player", "receiver"]].max(axis=1))
    edges = (pair.groupby(["a", "b"]).size().reset_index(name="count"))
    edges = edges[edges["count"] >= MIN_PAIR_PASSES]

    pos = top.set_index("player")[["x", "y"]]
    edges["x"] = edges["a"].map(pos["x"]); edges["y"] = edges["a"].map(pos["y"])
    edges["x_end"] = edges["b"].map(pos["x"]); edges["y_end"] = edges["b"].map(pos["y"])

    nd = top.rename(columns={"player": "label"})[["label", "x", "y", "involvement"]].copy()
    nd["kind"] = "node"
    ed = edges[["x", "y", "x_end", "y_end", "count"]].copy()
    ed["kind"] = "edge"
    block = pd.concat([nd, ed], ignore_index=True)
    block["league"], block["season"], block["team"], block["match"] = league, season, team, match
    return block


def build_for_match(match_id: int, league: str, season: str) -> pd.DataFrame:
    ws = sd.WhoScored(leagues=league, seasons=season,
                      data_dir=Path(SOCCERDATA_CACHE), headless=True)
    ev = ws.read_events(match_id=match_id).reset_index()
    match = ev["game"].iloc[0] if "game" in ev.columns else str(match_id)
    frames = []
    for team in ev["team"].dropna().unique():
        block = _team_network(ev[ev["team"] == team], league, season, team, match)
        if block is not None:
            frames.append(block)
    out = pd.concat(frames, ignore_index=True)
    log.info("match %s -> %d rows (%d teams)", match, len(out), out["team"].nunique())
    return out


def _append(new: pd.DataFrame) -> None:
    """Merge into pass_networks.parquet, replacing any same (match, team)."""
    path = PROCESSED_DIR / "pass_networks.parquet"
    if path.exists():
        old = pd.read_parquet(path)
        key = set(zip(new["match"], new["team"]))
        old = old[~old.apply(lambda r: (r["match"], r["team"]) in key, axis=1)]
        new = pd.concat([old, new], ignore_index=True)
    write_parquet_atomic(new, "pass_networks")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", type=int, required=True, help="WhoScored game_id")
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--season", default="2425")
    args = ap.parse_args()
    if args.league not in LEAGUES:
        raise SystemExit(f"league must be one of {list(LEAGUES)}")
    _append(build_for_match(args.match, args.league, args.season))
    log.info("appended pass network for match %s", args.match)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
