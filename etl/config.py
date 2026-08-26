"""Central ETL configuration: leagues, seasons, paths.

Single source of truth so fetch/transform/app all agree on scope.
"""
from __future__ import annotations

from pathlib import Path

# --- Scope: Top 5 European leagues -------------------------------------------
# Keys are soccerdata's canonical league identifiers (used by FBref & WhoScored).
LEAGUES: dict[str, str] = {
    "ENG-Premier League": "Premier League",
    "ESP-La Liga": "La Liga",
    "ITA-Serie A": "Serie A",
    "GER-Bundesliga": "Bundesliga",
    "FRA-Ligue 1": "Ligue 1",
}

# Seasons in soccerdata's short form: "2324" == 2023/24.
# Historical seasons 2020/21 -> 2025/26 plus the live 2026/27 season, which the
# weekly refresh keeps up to date (PRD §6). CURRENT_SEASON is the only one the
# scheduled job rebuilds each week — the rest are frozen in the committed data.
SEASONS: list[str] = ["2021", "2122", "2223", "2324", "2425", "2526", "2627"]
CURRENT_SEASON: str = "2627"

# Pass-network coverage: historical seasons were scraped for FEATURED_TEAMS only
# (WhoScored/Selenium can't scale to ~1,750 matches/season retroactively). From
# this season forward we build a pass network for EVERY team in EVERY played
# match, accumulated incrementally by the weekly job. Season codes are
# zero-padded 4-digit strings, so a plain string compare is chronological.
FULL_COVERAGE_FROM: str = "2627"

# --- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"          # gitignored: soccerdata cache + raw pulls
PROCESSED_DIR = DATA_DIR / "processed"  # committed: app-facing Parquet
TMP_DIR = DATA_DIR / "tmp"          # gitignored: atomic-write staging

for _d in (RAW_DIR, PROCESSED_DIR, TMP_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# soccerdata caches raw scraped pages here (respectful re-use, no re-fetch).
SOCCERDATA_CACHE = RAW_DIR / "soccerdata_cache"
