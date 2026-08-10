"""FBref player stats via robust data-stat parsing of the Big-5 pages.

Why not soccerdata's own reader:
  * it exposes only 5 stat types, and
  * its Big-5 multi-header parse mis-aligns (NA-ing the first column of every
    stat group).
We instead download the Big-5 combined page (one request per stat type) with
soccerdata's polite/cached session, then read cells by their stable FBref
`data-stat` attribute — position-independent, so no header-shift bug.

NOTE: many advanced FBref columns are simply blank at source right now (their
StatsBomb->Opta transition). We keep only the columns FBref actually populates;
xG/xA come from Understat instead (see understat_source).
"""
from __future__ import annotations

import logging

import pandas as pd
import soccerdata as sd
from lxml import html
from soccerdata.fbref import FBREF_API

from etl.config import SEASONS, SOCCERDATA_CACHE

log = logging.getLogger(__name__)

BIG5 = "Big 5 European Leagues Combined"

# URL page segment per stat type (segment == stat_type except these).
_PAGE = {"standard": "stats", "keeper": "keepers"}

# Columns (FBref data-stat keys) we actually consume, per stat type. Only
# source-populated ones — audited across all 2854 players.
FBREF_COLUMNS = {
    "standard": ["player", "nationality", "position", "team", "comp_level", "age",
                 "minutes", "minutes_90s", "goals", "assists", "goals_pens",
                 "pens_made", "cards_yellow", "cards_red"],
    "shooting": ["player", "team", "comp_level", "shots", "shots_on_target",
                 "shots_on_target_pct", "goals_per_shot", "goals_per_shot_on_target"],
    "defense": ["player", "team", "comp_level", "tackles_won", "interceptions"],
    "misc": ["player", "team", "comp_level", "fouls", "fouled", "offsides",
             "crosses", "own_goals"],
    "keeper": ["player", "nationality", "position", "team", "comp_level", "age",
               "gk_minutes", "minutes_90s", "gk_goals_against_per90",
               "gk_shots_on_target_against", "gk_saves", "gk_save_pct",
               "gk_clean_sheets_pct", "gk_pens_save_pct"],
}


def _map_league(text: str | None) -> str | None:
    t = (text or "").lower()
    if "premier" in t:
        return "ENG-Premier League"
    if "la liga" in t or "laliga" in t:
        return "ESP-La Liga"
    if "serie a" in t:
        return "ITA-Serie A"
    if "bundesliga" in t:
        return "GER-Bundesliga"
    if "ligue 1" in t:
        return "FRA-Ligue 1"
    return None


def _reader(seasons: list[str]) -> sd.FBref:
    # Big-5 is the only league key soccerdata accepts here; we only need .get().
    return sd.FBref(leagues=BIG5, seasons=seasons, data_dir=SOCCERDATA_CACHE)


def _download(fb: sd.FBref, stat_type: str) -> list[tuple[str, str]]:
    """Ensure each season's Big-5 page for stat_type is cached. Returns
    list of (season_key, filepath)."""
    page = _PAGE.get(stat_type, stat_type)
    out = []
    for (lkey, skey), season in fb.read_seasons().iterrows():
        filepath = fb.data_dir / f"players_{lkey}_{skey}_{stat_type}.html"
        url = (FBREF_API + "/".join(season.url.split("/")[:-1])
               + f"/{page}/players/" + season.url.split("/")[-1])
        fb.get(url, filepath)  # cached + rate-limited by soccerdata
        out.append((skey, str(filepath)))
    return out


def _parse(filepath: str, stat_type: str, season: str) -> pd.DataFrame:
    doc = html.parse(filepath).getroot()
    tbl = doc.get_element_by_id(f"stats_{stat_type}")
    tbody = tbl.find("tbody")
    wanted = set(FBREF_COLUMNS[stat_type])
    rows = []
    for tr in tbody.findall("tr"):
        if not tr.findall("td"):
            continue  # skip repeated header rows
        rec = {}
        for cell in tr.iter("td"):
            ds = cell.get("data-stat")
            if ds in wanted:
                rec[ds] = cell.text_content().strip()
        if not rec.get("player"):
            continue
        rec["league"] = _map_league(rec.get("comp_level"))
        rec["season"] = season
        rows.append(rec)
    df = pd.DataFrame(rows)
    return df[df["league"].notna()]


def fetch(stat_type: str, seasons: list[str] | None = None) -> pd.DataFrame:
    """One tidy FBref table (data-stat columns) for a stat type, all leagues."""
    fb = _reader(seasons or SEASONS)
    frames = [_parse(fp, stat_type, skey) for skey, fp in _download(fb, stat_type)]
    df = pd.concat(frames, ignore_index=True)
    log.info("FBref %-9s -> %s", stat_type, df.shape)
    return df
