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

        tables = build_all(SEASONS)
        for name, df in tables.items():
            write_parquet_atomic(df, name)
        log.info("Players stage OK: %s",
                 ", ".join(f"{n}={len(d)}" for n, d in tables.items()))
        return True
    except Exception:
        log.exception("Players stage FAILED — keeping last-good data")
        return False


def stage_shots() -> bool:
    """Fetch Understat shot events for the shot map / territory views."""
    try:
        from etl.config import SEASONS
        from etl.io_utils import write_parquet_atomic
        from etl.shots import fetch_shots

        shots = fetch_shots(SEASONS)
        write_parquet_atomic(shots, "shots")
        log.info("Shots stage OK: %d shots", len(shots))
        return True
    except Exception:
        log.exception("Shots stage FAILED — keeping last-good data")
        return False


def stage_whoscored() -> bool:
    """Pass networks come from WhoScored/Opta events, scraped OFFLINE via
    `python -m etl.pass_networks --match <id>` (Selenium — too slow/fragile to
    run inside the weekly job across all matches). Intentionally a no-op here."""
    log.info("Pass networks are built offline; see etl.pass_networks")
    return True


def main() -> int:
    ok_players = stage_players()
    ok_shots = stage_shots()
    # Non-fatal: as long as we didn't corrupt anything, exit 0 so the scheduler
    # commit step still runs with whatever refreshed successfully.
    log.info("run_all done. players=%s shots=%s", ok_players, ok_shots)
    return 0 if (ok_players or ok_shots) else 1


if __name__ == "__main__":
    sys.exit(main())
