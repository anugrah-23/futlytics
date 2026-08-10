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
# Current season + at least one prior for trend context (PRD §6).
SEASONS: list[str] = ["2324", "2425"]
CURRENT_SEASON: str = "2425"

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
