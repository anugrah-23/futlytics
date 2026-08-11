"""League standings computed from Understat team match data.

Understat gives per-match goals + xG + expected points, so we build a table
that carries both the real table (Pts) and its expected-goals shadow
(xG, xGA, xGD, xPTS) — the analytics angle a plain points table misses.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
import soccerdata as sd

from etl.config import LEAGUES, SEASONS, SOCCERDATA_CACHE
from etl.understat_source import read_per_season

log = logging.getLogger(__name__)


def _side(df: pd.DataFrame, side: str) -> pd.DataFrame:
    """Extract one team-perspective (home/away) from the match table."""
    opp = "away" if side == "home" else "home"
    num = lambda c: pd.to_numeric(df[c], errors="coerce")  # noqa: E731
    return pd.DataFrame({
        "league": df["league"],
        "season": df["season"],
        "date": pd.to_datetime(df["date"], errors="coerce"),
        "team": df[f"{side}_team"],
        "opponent": df[f"{opp}_team"],
        "venue": side,
        "gf": num(f"{side}_goals"),
        "ga": num(f"{opp}_goals"),
        "xgf": num(f"{side}_xg"),
        "xga": num(f"{opp}_xg"),
        "pts": num(f"{side}_points"),
        "xpts": num(f"{side}_expected_points"),
        "ppda": num(f"{side}_ppda"),
        "deep": num(f"{side}_deep_completions"),
    })


def _team_match_stats(seasons: list[str] | None) -> pd.DataFrame:
    """All-league team-match table, each (league, season) fetched as its own
    retryable request so one connection drop can't abort the rest."""
    def _one(lg: str, sn: str) -> pd.DataFrame:
        us = sd.Understat(leagues=lg, seasons=sn, data_dir=Path(SOCCERDATA_CACHE))
        return us.read_team_match_stats().reset_index()

    return read_per_season(_one, seasons or SEASONS, "team match")


def _long(seasons: list[str] | None) -> pd.DataFrame:
    m = _team_match_stats(seasons)
    long = pd.concat([_side(m, "home"), _side(m, "away")], ignore_index=True)
    return long[long["gf"].notna()]  # played matches only


def build_team_match(seasons: list[str] | None = None) -> pd.DataFrame:
    """Per-team, per-match long table (pressing/xG trends for the dashboard)."""
    out = _long(seasons).sort_values(["league", "season", "team", "date"])
    log.info("team_match -> %s", out.shape)
    return out.reset_index(drop=True)


def build_standings(seasons: list[str] | None = None) -> pd.DataFrame:
    m = _team_match_stats(seasons)
    long = pd.concat([_side(m, "home"), _side(m, "away")], ignore_index=True)
    long = long[long["gf"].notna()]  # played matches only

    g = long.groupby(["league", "season", "team"], as_index=False).agg(
        MP=("gf", "size"),
        W=("pts", lambda s: int((s == 3).sum())),
        D=("pts", lambda s: int((s == 1).sum())),
        L=("pts", lambda s: int((s == 0).sum())),
        GF=("gf", "sum"),
        GA=("ga", "sum"),
        Pts=("pts", "sum"),
        xG=("xgf", "sum"),
        xGA=("xga", "sum"),
        xPTS=("xpts", "sum"),
    )
    g["GD"] = g["GF"] - g["GA"]
    g["xGD"] = (g["xG"] - g["xGA"]).round(1)
    g["xG"] = g["xG"].round(1)
    g["xGA"] = g["xGA"].round(1)
    g["xPTS"] = g["xPTS"].round(1)

    # Rank within league+season: Pts, then GD, then GF.
    g = g.sort_values(["league", "season", "Pts", "GD", "GF"],
                      ascending=[True, True, False, False, False])
    g["position"] = g.groupby(["league", "season"]).cumcount() + 1

    cols = ["league", "season", "position", "team", "MP", "W", "D", "L",
            "GF", "GA", "GD", "Pts", "xG", "xGA", "xGD", "xPTS"]
    out = g[cols].reset_index(drop=True)
    for c in ["GF", "GA", "GD", "Pts"]:
        out[c] = out[c].astype(int)
    log.info("standings -> %s", out.shape)
    return out
