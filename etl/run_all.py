"""Single ETL entrypoint the weekly scheduler calls: fetch -> transform -> write.

Each stage is isolated: a WhoScored (Selenium) failure must not prevent the
FBref-backed player/league tables from refreshing. Writes are atomic, so a
partial run never leaves data/processed in a broken state (tech spec §4).

Run:  python -m etl.run_all
"""
from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("run_all")


def stage_fbref() -> bool:
    """Fetch + persist FBref-derived tables. Returns True on success."""
    try:
        from etl.fetch_fbref import fetch_player_season_stats
        from etl.io_utils import write_parquet_atomic

        players = fetch_player_season_stats()
        players = players.reset_index()
        players.columns = ["_".join(str(c) for c in col).strip("_")
                           if isinstance(col, tuple) else str(col)
                           for col in players.columns]
        write_parquet_atomic(players, "player_season_stats_raw")
        log.info("FBref stage OK: %d player rows", len(players))
        return True
    except Exception:
        log.exception("FBref stage FAILED — keeping last-good data")
        return False


def stage_whoscored() -> bool:
    """Fetch a sample of match events for the team dashboard. Fragile; optional."""
    try:
        # Intentionally minimal in Phase 0 — wired up fully in Phase 3.
        log.info("WhoScored stage skipped in Phase 0 (enabled in Phase 3)")
        return True
    except Exception:
        log.exception("WhoScored stage FAILED — keeping last-good data")
        return False


def main() -> int:
    ok_fb = stage_fbref()
    ok_ws = stage_whoscored()
    # Non-fatal: as long as we didn't corrupt anything, exit 0 so the scheduler
    # commit step still runs with whatever refreshed successfully.
    log.info("run_all done. fbref=%s whoscored=%s", ok_fb, ok_ws)
    return 0 if (ok_fb or ok_ws) else 1


if __name__ == "__main__":
    sys.exit(main())
