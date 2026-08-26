"""Single ETL entrypoint the weekly scheduler calls: fetch -> transform -> merge.

Incremental by design: it rebuilds only the season(s) passed (default the live
CURRENT_SEASON) and MERGES them into the committed Parquet, leaving the frozen
historical seasons untouched. That keeps the weekly job fast and polite to the
sources, and safe before the new season has any matches — a failed or empty
fetch leaves last-good data in place rather than wiping it.

Each stage is isolated: a WhoScored (Selenium) failure must not prevent the
FBref-backed player/league tables from refreshing. Writes are atomic, so a
partial run never leaves data/processed in a broken state (tech spec §4).

Run:  python -m etl.run_all                 # refresh the current season
      python -m etl.run_all --seasons 2627  # explicit
      python -m etl.run_all --seasons 2526 2627  # a couple of seasons
"""
from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("run_all")


def _merge_season(name: str, new_df: pd.DataFrame, seasons: list[str]) -> int:
    """Replace the given seasons' rows in the committed <name>.parquet with the
    freshly built rows, preserving every other season. Returns the merged row
    count. An empty build is skipped so a transient blank fetch can't wipe data."""
    from etl.config import PROCESSED_DIR
    from etl.io_utils import write_parquet_atomic

    if new_df is None or new_df.empty:
        log.warning("%s: fresh build empty for %s — keeping existing data", name, seasons)
        return -1

    path = PROCESSED_DIR / f"{name}.parquet"
    if path.exists() and "season" in new_df.columns:
        old = pd.read_parquet(path)
        if "season" in old.columns:
            old = old[~old["season"].isin(seasons)]
            merged = pd.concat([old, new_df], ignore_index=True)
        else:
            merged = new_df
    else:
        merged = new_df
    write_parquet_atomic(merged, name)
    return len(merged)


def stage_players(seasons: list[str]) -> bool:
    """Rebuild + merge the Player Profile tables (FBref basics + Understat xG).

    FBref now sits behind a Cloudflare CAPTCHA (soccerdata 1.9); this stage may
    fail for the live season until it lifts. It is isolated from stage_league so
    a blocked FBref never stops the Understat-only standings from refreshing."""
    try:
        from etl.build_players import build

        players, metrics = build(seasons)
        for name, df in (("players", players), ("player_metrics", metrics)):
            n = _merge_season(name, df, seasons)
            log.info("  %s -> %s rows", name, n if n >= 0 else "unchanged")
        log.info("Players stage OK for %s", seasons)
        return True
    except Exception:
        log.exception("Players stage FAILED (FBref CAPTCHA?) — trying Understat-only")
        # Fallback: FBref is gated but Understat still serves the leaderboard
        # metrics, so keep the Home leaderboards current. No player_metrics is
        # written, so Player Profile stays clean; a later full FBref build
        # replaces these rows via _merge_season.
        try:
            from etl.build_players import build_understat_only

            n = _merge_season("players", build_understat_only(seasons), seasons)
            log.info("  players (Understat-only) -> %s rows",
                     n if n >= 0 else "unchanged")
            return n >= 0
        except Exception:
            log.exception("Understat-only fallback FAILED — keeping last-good")
            return False


def stage_league(seasons: list[str]) -> bool:
    """Rebuild + merge standings and per-match team stats (Understat only).

    Kept separate from stage_players on purpose: Understat is reachable when
    FBref is CAPTCHA-gated, so the league table and team dashboard can pick up
    the new season even while player stats lag."""
    try:
        from etl.standings import build_standings, build_team_match

        for name, df in (("standings", build_standings(seasons)),
                         ("team_match", build_team_match(seasons))):
            n = _merge_season(name, df, seasons)
            log.info("  %s -> %s rows", name, n if n >= 0 else "unchanged")
        log.info("League stage OK for %s", seasons)
        return True
    except Exception:
        log.exception("League stage FAILED — keeping last-good data")
        return False


def stage_shots(seasons: list[str]) -> bool:
    """Fetch + merge Understat shot events for the shot map / territory views."""
    try:
        from etl.shots import fetch_shots

        shots = fetch_shots(seasons)
        n = _merge_season("shots", shots, seasons)
        log.info("Shots stage OK: shots -> %s rows", n if n >= 0 else "unchanged")
        return True
    except Exception:
        log.exception("Shots stage FAILED — keeping last-good data")
        return False


def stage_whoscored() -> bool:
    """Pass networks / Player DNA come from WhoScored/Opta events, scraped
    OFFLINE via `python -m etl.pass_networks --featured` then `etl.build_dna` /
    `etl.build_passes` (Selenium — too slow/fragile to run inside the weekly
    job). Intentionally a no-op here; refresh those locally when needed."""
    log.info("Pass networks / DNA are built offline; see etl.pass_networks")
    return True


def main() -> int:
    from etl.config import CURRENT_SEASON

    ap = argparse.ArgumentParser(description="Incremental weekly ETL refresh.")
    ap.add_argument("--seasons", nargs="+", default=[CURRENT_SEASON],
                    help="seasons to rebuild + merge (default: the live season)")
    args = ap.parse_args()
    seasons = args.seasons

    ok_players = stage_players(seasons)
    ok_league = stage_league(seasons)
    ok_shots = stage_shots(seasons)
    # Non-fatal: as long as we didn't corrupt anything, exit 0 so the scheduler
    # commit step still runs with whatever refreshed successfully.
    log.info("run_all done for %s. players=%s league=%s shots=%s",
             seasons, ok_players, ok_league, ok_shots)
    return 0 if (ok_players or ok_league or ok_shots) else 1


if __name__ == "__main__":
    sys.exit(main())
