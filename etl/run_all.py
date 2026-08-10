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


def stage_players() -> bool:
    """Build + persist the Player Profile tables (FBref + Understat)."""
    try:
        from etl.build_players import build_all
        from etl.config import SEASONS
        from etl.io_utils import write_parquet_atomic

        players, metrics, standings = build_all(SEASONS)
        write_parquet_atomic(players, "players")
        write_parquet_atomic(metrics, "player_metrics")
        write_parquet_atomic(standings, "standings")
        log.info("Players stage OK: %d players, %d metric rows, %d standings rows",
                 len(players), len(metrics), len(standings))
        return True
    except Exception:
        log.exception("Players stage FAILED — keeping last-good data")
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
    ok_players = stage_players()
    ok_ws = stage_whoscored()
    # Non-fatal: as long as we didn't corrupt anything, exit 0 so the scheduler
    # commit step still runs with whatever refreshed successfully.
    log.info("run_all done. players=%s whoscored=%s", ok_players, ok_ws)
    return 0 if (ok_players or ok_ws) else 1


if __name__ == "__main__":
    sys.exit(main())
