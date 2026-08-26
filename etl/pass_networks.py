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
import time
import unicodedata
from pathlib import Path

import pandas as pd
import soccerdata as sd

from etl.config import CURRENT_SEASON, LEAGUES, SEASONS, SOCCERDATA_CACHE
from etl.io_utils import PROCESSED_DIR, write_parquet_atomic

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pass_networks")

MIN_PAIR_PASSES = 3   # edges below this are visual noise
TOP_N = 11            # approximate the starting XI by involvement

# Featured clubs to build pass-network history for (WhoScored won't scale to all
# ~10k Top-5 matches). Aliases are matched loosely against WhoScored team names.
# Aliases chosen to resolve under either WhoScored naming convention via
# bidirectional substring match, without colliding with other clubs:
#   "Bayer Leverkusen" (not "Bayer" -> would hit "Bayern"),
#   "AC Milan" (not "Milan" -> would hit "Inter Milan"),
#   "PSG"/"Paris Saint-Germain" (not "Paris" -> would hit newly-promoted Paris FC).
FEATURED_TEAMS: dict[str, list[str]] = {
    "ENG-Premier League": ["Manchester City", "Manchester United", "Arsenal",
                           "Liverpool", "Tottenham", "Chelsea"],
    "ESP-La Liga": ["Barcelona", "Real Madrid", "Atletico Madrid"],
    "GER-Bundesliga": ["Bayern", "Bayer Leverkusen", "Dortmund"],
    "FRA-Ligue 1": ["Paris Saint-Germain", "PSG"],
    "ITA-Serie A": ["Inter", "AC Milan", "Roma", "Juventus", "Napoli"],
}


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
    # Keep the pair's player labels on the edge so season-averaging can match
    # links across matches exactly (older rows without these fall back to
    # nearest-node snapping in viz.average_pass_network).
    ed = edges[["a", "b", "x", "y", "x_end", "y_end", "count"]].rename(
        columns={"a": "label", "b": "label_end"}).copy()
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
    out["game_id"] = int(match_id)  # stable key for resume/skip in batch mode
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


# --- Batch mode: featured teams across seasons -------------------------------

def _norm(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _resolve_featured(actual_names: set[str], aliases: list[str]) -> set[str]:
    """Actual WhoScored team names matching any featured alias (bidirectional
    substring on accent-folded text — tolerant of either naming convention)."""
    out = set()
    norm_aliases = [_norm(a) for a in aliases]
    for name in actual_names:
        n = _norm(name)
        if any(a in n or n in a for a in norm_aliases):
            out.add(name)
    return out


def _schedule(ws: sd.WhoScored) -> pd.DataFrame:
    """Schedule as a flat frame with game_id/home_team/away_team columns."""
    sched = ws.read_schedule().reset_index()
    ren = {}
    for c in sched.columns:
        lc = c.lower()
        if lc in ("game_id", "match_id"):
            ren[c] = "game_id"
        elif lc in ("home_team", "home"):
            ren[c] = "home_team"
        elif lc in ("away_team", "away"):
            ren[c] = "away_team"
    return sched.rename(columns=ren)


def _played_mask(sched: pd.DataFrame) -> pd.Series:
    """Matches actually played, so a live-season batch doesn't waste ~30-60s of
    Selenium apiece failing to read events for future fixtures. Prefer a recorded
    score; fall back to WhoScored status==6 (full time) or a past kickoff date."""
    if "home_score" in sched.columns:
        m = sched["home_score"].notna()
        if m.any():
            return m
    if "status" in sched.columns:
        m = pd.to_numeric(sched["status"], errors="coerce").eq(6)
        if m.any():
            return m
    if "date" in sched.columns:
        d = pd.to_datetime(sched["date"], errors="coerce", utc=True)
        return d.notna() & (d <= pd.Timestamp.now(tz="UTC"))
    return pd.Series(True, index=sched.index)


def _existing_game_ids() -> set[int]:
    path = PROCESSED_DIR / "pass_networks.parquet"
    if not path.exists():
        return set()
    df = pd.read_parquet(path)
    if "game_id" not in df.columns:
        return set()
    return set(pd.to_numeric(df["game_id"], errors="coerce").dropna().astype(int))


def build_featured(seasons: list[str] | None = None,
                   leagues: list[str] | None = None,
                   limit: int | None = None) -> int:
    """Scrape pass networks for every FEATURED_TEAMS match in scope, resuming
    past already-built matches. Returns the number of matches newly built.

    WhoScored/Selenium is slow (~30-90s/match) and rate-limits, so this is a
    resumable grind: re-run to continue; --limit caps a single run.
    """
    seasons = seasons or SEASONS
    leagues = leagues or list(FEATURED_TEAMS)
    done = _existing_game_ids()
    built = 0

    for league in leagues:
        aliases = FEATURED_TEAMS.get(league, [])
        if not aliases:
            continue
        for season in seasons:
            # Live-season schedule re-fetched fresh so newly-played matches
            # appear; a frozen early-season cache would hide them (same reason
            # the Understat readers use no_cache for CURRENT_SEASON).
            ws = sd.WhoScored(leagues=league, seasons=season,
                              data_dir=Path(SOCCERDATA_CACHE), headless=True,
                              no_cache=(season == CURRENT_SEASON))
            try:
                sched = _schedule(ws)
            except Exception as exc:
                log.warning("schedule FAILED %s %s (skipped): %s", league, season, exc)
                continue
            if "game_id" not in sched.columns:
                log.warning("no game_id in schedule for %s %s; cols=%s",
                            league, season, list(sched.columns))
                continue

            names = set(sched["home_team"].dropna()) | set(sched["away_team"].dropna())
            featured = _resolve_featured(names, aliases)
            log.info("%s %s: resolved featured -> %s", league, season,
                     sorted(featured) or "NONE")
            if not featured:
                continue

            mask = (sched["home_team"].isin(featured) | sched["away_team"].isin(featured))
            todo = sched[mask & _played_mask(sched)].dropna(subset=["game_id"]).copy()
            todo["game_id"] = pd.to_numeric(todo["game_id"], errors="coerce").astype("Int64")
            todo = todo.dropna(subset=["game_id"])
            pending = [int(g) for g in todo["game_id"].tolist() if int(g) not in done]
            log.info("%s %s: %d played featured matches, %d pending (%d already built)",
                     league, season, len(todo), len(pending), len(todo) - len(pending))

            for gid in pending:
                if limit is not None and built >= limit:
                    log.info("hit --limit %d; stopping (resume by re-running)", limit)
                    return built
                try:
                    _append(build_for_match(gid, league, season))
                    done.add(gid)
                    built += 1
                except Exception as exc:
                    log.warning("match %s FAILED (%s %s): %s", gid, league, season, exc)
                time.sleep(1.0)
    log.info("batch done: %d matches newly built", built)
    return built


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build WhoScored pass networks (single match or featured batch).")
    ap.add_argument("--match", type=int, help="single WhoScored game_id")
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--season", default="2425")
    # Batch mode (featured teams across seasons):
    ap.add_argument("--featured", action="store_true",
                    help="batch-scrape FEATURED_TEAMS matches (resumable)")
    ap.add_argument("--seasons", nargs="+", help="seasons for --featured (default: all)")
    ap.add_argument("--leagues", nargs="+", help="leagues for --featured (default: all)")
    ap.add_argument("--limit", type=int, help="max matches this run (--featured)")
    args = ap.parse_args()

    if args.featured:
        n = build_featured(args.seasons, args.leagues, args.limit)
        log.info("featured batch complete: %d matches newly built", n)
        return 0

    if args.match is None:
        raise SystemExit("provide --match <game_id> or --featured")
    if args.league not in LEAGUES:
        raise SystemExit(f"league must be one of {list(LEAGUES)}")
    _append(build_for_match(args.match, args.league, args.season))
    log.info("appended pass network for match %s", args.match)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
