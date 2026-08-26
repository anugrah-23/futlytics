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
import json
import logging
import time
import unicodedata
from pathlib import Path

import pandas as pd
import soccerdata as sd

from etl.config import (CURRENT_SEASON, FULL_COVERAGE_FROM, LEAGUES, SEASONS,
                        SOCCERDATA_CACHE)
from etl.dna_events import EVENTS_DIR, load_match
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


def _team_network(te: pd.DataFrame, starters: set[str], league: str,
                  season: str, team: str, match: str) -> pd.DataFrame | None:
    """One team's pass network, restricted to its STARTING XI.

    Nodes are the players who started the match (Opta ``isFirstEleven``), so the
    goalkeeper is always kept and substitutes are excluded — a proper "starting
    shape" rather than a top-N-by-involvement view that could drop a low-touch
    keeper or promote a busy sub. ``te`` is this team's touches in chronological
    order; the receiver is approximated by the next same-team touch (Opta's
    related_player_id is unset on these passes)."""
    te = te.copy()
    te["receiver"] = te["player"].shift(-1)

    passes = te[(te["type"] == "Pass") & (te["outcome"] == 1)].copy()
    passes = passes.dropna(subset=["x", "y", "player"])
    passes = passes[passes["player"].isin(starters)]  # starting XI only
    if passes.empty:
        return None

    nodes = (passes.groupby("player")
             .agg(x=("x", "mean"), y=("y", "mean"), involvement=("x", "size"))
             .reset_index())
    keep = set(nodes["player"])  # starters who completed at least one pass

    e = passes.dropna(subset=["receiver"])
    e = e[e["receiver"].isin(keep)]      # links between starters only
    e = e[e["player"] != e["receiver"]]
    pair = e.assign(a=e[["player", "receiver"]].min(axis=1),
                    b=e[["player", "receiver"]].max(axis=1))
    edges = (pair.groupby(["a", "b"]).size().reset_index(name="count"))
    edges = edges[edges["count"] >= MIN_PAIR_PASSES]

    pos = nodes.set_index("player")[["x", "y"]]
    edges["x"] = edges["a"].map(pos["x"]); edges["y"] = edges["a"].map(pos["y"])
    edges["x_end"] = edges["b"].map(pos["x"]); edges["y_end"] = edges["b"].map(pos["y"])

    nd = nodes.rename(columns={"player": "label"})[["label", "x", "y", "involvement"]].copy()
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


def _match_display_name(match_json: dict) -> str:
    """"YYYY-MM-DD Home-Away" — matches the schedule-derived name used before, so
    rebuilt rows replace old ones on the (match, team) key."""
    date = (match_json.get("startDate") or "")[:10]
    return f'{date} {match_json["home"]["name"]}-{match_json["away"]["name"]}'.strip()


def _network_from_cache(league: str, season: str, match_id: int) -> pd.DataFrame | None:
    """Build both teams' starting-XI networks from the cached Opta match JSON.

    Reads the raw event stream the scrape already cached (no Selenium), which
    carries the authoritative lineup (isFirstEleven / position) that soccerdata's
    tabular read_events does not expose."""
    path = EVENTS_DIR / f"{league}_{season}" / f"{int(match_id)}.json"
    if not path.exists():
        return None
    events, meta = load_match(path)
    if events.empty or meta.empty or "is_starter" not in meta.columns:
        return None
    match = _match_display_name(json.loads(path.read_text(encoding="utf-8")))
    frames = []
    for team in meta["team"].dropna().unique():
        starters = set(meta[(meta["team"] == team) & (meta["is_starter"])]["player"])
        if not starters:
            continue
        te = events[events["team"] == team].sort_values("seq")
        block = _team_network(te, starters, league, season, team, match)
        if block is not None:
            frames.append(block)
    if not frames:
        return None
    out = pd.concat(frames, ignore_index=True)
    out["game_id"] = int(match_id)
    log.info("match %s -> %d rows (%d teams)", match, len(out), out["team"].nunique())
    return out


def build_for_match(match_id: int, league: str, season: str,
                    ws: "sd.WhoScored | None" = None) -> pd.DataFrame:
    # read_events fetches the match and caches its raw Opta JSON; we then build
    # the network from that cache so we get the lineup (starters/GK) it carries.
    # Reuse the caller's reader when given so the schedule is resolved once.
    if ws is None:
        ws = sd.WhoScored(leagues=league, seasons=season,
                          data_dir=Path(SOCCERDATA_CACHE), headless=True)
    ws.read_events(match_id=match_id)  # side effect: cache the raw match JSON
    out = _network_from_cache(league, season, match_id)
    if out is None:
        raise RuntimeError(f"no usable cached events for match {match_id}")
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
                   limit: int | None = None,
                   all_teams: bool = False) -> int:
    """Scrape pass networks for the played matches in scope, resuming past
    already-built matches. Returns the number of matches newly built.

    Coverage is per-season (config.FULL_COVERAGE_FROM): seasons at/after the
    threshold build a network for EVERY team in EVERY played match; earlier
    seasons stay limited to FEATURED_TEAMS (they were never fully backfilled).
    ``all_teams=True`` forces full coverage for every season in scope.

    WhoScored/Selenium is slow (~30-90s/match) and rate-limits, so this is a
    resumable grind: re-run to continue; --limit caps a single run.
    """
    seasons = seasons or SEASONS
    leagues = leagues or list(LEAGUES)
    done = _existing_game_ids()
    built = 0

    for league in leagues:
        for season in seasons:
            full = all_teams or (season >= FULL_COVERAGE_FROM)
            if not full and league not in FEATURED_TEAMS:
                continue
            # Two readers on the same cache. The SCHEDULE reader re-fetches the
            # live-season calendar fresh (no_cache) so newly-played matches show
            # up; a frozen early-season cache would hide them. The EVENTS reader
            # stays cached: completed-match events are immutable, and — crucially
            # — a no_cache events reader would re-scrape the whole calendar (~2min)
            # before EVERY match, which does not scale to all-teams volume. It
            # reads the calendar the schedule reader just cached, then caches each
            # match's events for instant resume.
            ws = sd.WhoScored(leagues=league, seasons=season,
                              data_dir=Path(SOCCERDATA_CACHE), headless=True,
                              no_cache=(season == CURRENT_SEASON))
            ws_ev = sd.WhoScored(leagues=league, seasons=season,
                                 data_dir=Path(SOCCERDATA_CACHE), headless=True,
                                 no_cache=False)
            try:
                sched = _schedule(ws)
            except Exception as exc:
                log.warning("schedule FAILED %s %s (skipped): %s", league, season, exc)
                continue
            if "game_id" not in sched.columns:
                log.warning("no game_id in schedule for %s %s; cols=%s",
                            league, season, list(sched.columns))
                continue

            played = _played_mask(sched)
            if full:
                sel = played                       # every played match
                scope = "all-teams"
            else:
                names = set(sched["home_team"].dropna()) | set(sched["away_team"].dropna())
                featured = _resolve_featured(names, FEATURED_TEAMS.get(league, []))
                if not featured:
                    continue
                sel = played & (sched["home_team"].isin(featured)
                                | sched["away_team"].isin(featured))
                scope = "featured"

            todo = sched[sel].dropna(subset=["game_id"]).copy()
            todo["game_id"] = pd.to_numeric(todo["game_id"], errors="coerce").astype("Int64")
            todo = todo.dropna(subset=["game_id"])
            pending = [int(g) for g in todo["game_id"].tolist() if int(g) not in done]
            log.info("%s %s [%s]: %d played matches, %d pending (%d already built)",
                     league, season, scope, len(todo), len(pending), len(todo) - len(pending))

            for gid in pending:
                if limit is not None and built >= limit:
                    log.info("hit --limit %d; stopping (resume by re-running)", limit)
                    return built
                try:
                    _append(build_for_match(gid, league, season, ws=ws_ev))
                    done.add(gid)
                    built += 1
                except Exception as exc:
                    log.warning("match %s FAILED (%s %s): %s", gid, league, season, exc)
                time.sleep(1.0)
    log.info("batch done: %d matches newly built", built)
    return built


def rebuild_cached(seasons: list[str] | None = None,
                   leagues: list[str] | None = None) -> int:
    """Regenerate pass networks for every already-cached match, in place, from
    the raw Opta JSON — no scraping. Use this to re-apply the current builder
    (e.g. the starting-XI node selection) to matches scraped earlier. Rows for a
    rebuilt game_id replace the old ones; other seasons/games are untouched."""
    seasons = seasons or SEASONS
    leagues = leagues or list(LEAGUES)
    blocks, ids = [], set()
    for league in leagues:
        for season in seasons:
            d = EVENTS_DIR / f"{league}_{season}"
            if not d.is_dir():
                continue
            n = 0
            for fp in sorted(d.glob("*.json")):
                gid = int(fp.stem)
                try:
                    out = _network_from_cache(league, season, gid)
                except Exception as exc:
                    log.warning("rebuild %s FAILED: %s", fp.name, exc)
                    continue
                if out is not None:
                    blocks.append(out)
                    ids.add(gid)
                    n += 1
            if n:
                log.info("%s %s: rebuilt %d cached matches", league, season, n)
    if not blocks:
        log.info("rebuild_cached: nothing to do")
        return 0
    new = pd.concat(blocks, ignore_index=True)
    path = PROCESSED_DIR / "pass_networks.parquet"
    if path.exists():
        old = pd.read_parquet(path)
        if "game_id" in old.columns:
            old = old[~pd.to_numeric(old["game_id"], errors="coerce").isin(ids)]
        new = pd.concat([old, new], ignore_index=True)
    write_parquet_atomic(new, "pass_networks")
    log.info("rebuild_cached: %d matches rebuilt, %d rows total", len(ids), len(new))
    return len(ids)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build WhoScored pass networks (single match or featured batch).")
    ap.add_argument("--match", type=int, help="single WhoScored game_id")
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--season", default="2425")
    # Batch mode (featured teams across seasons):
    ap.add_argument("--featured", action="store_true",
                    help="batch-scrape matches (resumable); coverage per season "
                         "via config.FULL_COVERAGE_FROM")
    ap.add_argument("--all-teams", action="store_true",
                    help="force full (every team, every match) coverage for all "
                         "seasons in scope, not just those past the threshold")
    ap.add_argument("--rebuild-cached", action="store_true",
                    help="regenerate networks for already-cached matches from the "
                         "raw JSON (no scraping); applies the current builder")
    ap.add_argument("--seasons", nargs="+", help="seasons for --featured (default: all)")
    ap.add_argument("--leagues", nargs="+", help="leagues for --featured (default: all)")
    ap.add_argument("--limit", type=int, help="max matches this run (--featured)")
    args = ap.parse_args()

    if args.rebuild_cached:
        n = rebuild_cached(args.seasons, args.leagues)
        log.info("rebuild complete: %d matches", n)
        return 0

    if args.featured:
        n = build_featured(args.seasons, args.leagues, args.limit,
                           all_teams=args.all_teams)
        log.info("batch complete: %d matches newly built", n)
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
