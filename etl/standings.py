"""League standings computed from Understat team match data.

Understat gives per-match goals + xG + expected points, so we build a table
that carries both the real table (Pts) and its expected-goals shadow
(xG, xGA, xGD, xPTS) — the analytics angle a plain points table misses.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import soccerdata as sd

from etl.config import LEAGUES, SEASONS, SOCCERDATA_CACHE

log = logging.getLogger(__name__)


def _side(df: pd.DataFrame, side: str) -> pd.DataFrame:
    """Extract one team-perspective (home/away) from the match table."""
    opp = "away" if side == "home" else "home"
    return pd.DataFrame({
        "league": df["league"],
        "season": df["season"],
        "team": df[f"{side}_team"],
        "gf": pd.to_numeric(df[f"{side}_goals"], errors="coerce"),
        "ga": pd.to_numeric(df[f"{opp}_goals"], errors="coerce"),
        "xgf": pd.to_numeric(df[f"{side}_xg"], errors="coerce"),
        "xga": pd.to_numeric(df[f"{opp}_xg"], errors="coerce"),
        "pts": pd.to_numeric(df[f"{side}_points"], errors="coerce"),
        "xpts": pd.to_numeric(df[f"{side}_expected_points"], errors="coerce"),
    })


def build_standings(seasons: list[str] | None = None) -> pd.DataFrame:
    us = sd.Understat(
        leagues=list(LEAGUES.keys()),
        seasons=seasons or SEASONS,
        data_dir=Path(SOCCERDATA_CACHE),
    )
    m = us.read_team_match_stats().reset_index()
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
