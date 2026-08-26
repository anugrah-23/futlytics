"""Build Player Profile tables from FBref (basics) + Understat (xG/xA).

Output (data/processed/):
  players.parquet          one row per player-season: identity, minutes, flags
  player_metrics.parquet   tidy long: (player-season, metric) + value + pctl

Run:  python -m etl.build_players --seasons 2425 2324
"""
from __future__ import annotations

import argparse
import logging
import unicodedata

import numpy as np
import pandas as pd

from etl import fbref_source as fb
from etl import understat_source as us
from etl.io_utils import write_parquet_atomic
from etl.metrics import GK_METRICS, OUTFIELD_METRICS, Metric
from etl.transform import (
    MIN_MINUTES_DEFAULT,
    is_limited_sample,
    percentile_within_group,
    primary_position_group,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("build_players")

INDEX = ["league", "season", "team", "player"]


def _num(s: pd.Series) -> pd.Series:
    # FBref formats large counts with thousands separators ("3,371"); strip them.
    if s is None:
        return pd.Series(dtype="float64")
    # astype(str) (not "string") -> plain float64/np.nan, not nullable pd.NA.
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False), errors="coerce"
    )


def _norm(name: str) -> str:
    """Accent-fold + lowercase a player name for cross-source matching."""
    if not isinstance(name, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _merge_fbref(seasons: list[str]) -> pd.DataFrame:
    """Merge the FBref outfield stat tables into one flat frame on INDEX."""
    std = fb.fetch("standard", seasons)
    base = std.drop_duplicates(subset=INDEX).set_index(INDEX)
    for st, cols in [
        ("shooting", ["shots", "shots_on_target_pct", "goals_per_shot"]),
        ("defense", ["tackles_won", "interceptions"]),
        ("misc", ["fouls", "fouled", "offsides", "crosses", "own_goals"]),
    ]:
        extra = fb.fetch(st, seasons).drop_duplicates(subset=INDEX).set_index(INDEX)
        base = base.join(extra[cols], how="left")
    return base.reset_index()


def _attach_understat(players: pd.DataFrame, seasons: list[str]) -> pd.DataFrame:
    """Left-join Understat metrics onto FBref players via normalized name."""
    u = us.fetch(seasons)
    u["jkey"] = list(zip(u["league"], u["season"], u["player"].map(_norm)))
    ucols = [c for c in u.columns if c not in INDEX + ["jkey"]]
    u = u.drop_duplicates("jkey").set_index("jkey")[ucols].add_prefix("us_")

    players = players.copy()
    players["jkey"] = list(
        zip(players["league"], players["season"], players["player"].map(_norm))
    )
    merged = players.join(u, on="jkey").drop(columns="jkey")
    matched = merged["us_xg"].notna().sum() if "us_xg" in merged else 0
    log.info("Understat matched %d / %d outfield players", int(matched), len(players))
    return merged


def _compute(metrics: list[Metric], frame: pd.DataFrame, is_gk: bool) -> pd.DataFrame:
    nineties = _num(frame["minutes_90s"])
    minutes = _num(frame["minutes_col"]).fillna(0)
    # Rank within season *and* position group: a 2020/21 forward must be
    # compared to that season's forwards, never pooled across seasons.
    pos_group = frame["season"].astype(str) + "|" + frame["pos_group"].astype(str)

    rows: list[pd.DataFrame] = []
    for m in metrics:
        if m.kind == "derived" and m.key == "npxg_perf":
            raw = _num(frame["goals_pens"]) - _num(frame.get("us_np_xg"))
            value = raw / nineties.replace(0, np.nan)
            unit = "per90"
        elif m.kind == "count":
            value = _num(frame[m.col]) / nineties.replace(0, np.nan)
            unit = "per90"
        elif m.kind == "rate":
            value = _num(frame[m.col])
            unit = "%"
        else:  # per90 already
            value = _num(frame[m.col])
            unit = "per90"

        pct = percentile_within_group(value, pos_group, minutes, MIN_MINUTES_DEFAULT)
        if m.invert:
            pct = 100.0 - pct

        block = frame[INDEX].copy()
        block["concept"] = m.concept
        block["metric_key"] = m.key
        block["label"] = m.label
        block["unit"] = unit
        block["value"] = value.to_numpy()
        block["percentile"] = pct.to_numpy()
        block["is_gk"] = is_gk
        rows.append(block)
    return pd.concat(rows, ignore_index=True)


# Raw season totals carried on the players table for League Overview leaderboards
# (player_metrics stores per-90 + percentile; leaderboards want season totals).
_RAW_TOTALS = {
    "goals": "goals", "assists": "assists", "np_goals": "goals_pens",
    "xg": "us_xg", "xa": "us_xa", "key_passes": "us_key_passes", "shots": "shots",
}


def _identity(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[INDEX].copy()
    out["pos"] = frame.get("position", "")
    out["nation"] = frame.get("nationality", "")
    out["age"] = _num(frame.get("age"))
    out["minutes"] = _num(frame["minutes_col"])
    out["pos_group"] = frame["pos_group"]
    out["limited_sample"] = is_limited_sample(out["minutes"].fillna(0))
    for out_col, src in _RAW_TOTALS.items():
        out[out_col] = _num(frame[src]).to_numpy() if src in frame.columns else np.nan
    return out


def build(seasons: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    # --- Outfield ---
    of = _merge_fbref(seasons)
    of["minutes_col"] = _num(of["minutes"])
    of["pos_group"] = of["position"].map(primary_position_group)
    of = of[of["pos_group"] != "GK"].reset_index(drop=True)
    of = _attach_understat(of, seasons)
    of_metrics = _compute(OUTFIELD_METRICS, of, is_gk=False)
    of_ident = _identity(of)

    # --- Goalkeepers ---
    gk = fb.fetch("keeper", seasons)
    gk = gk.drop_duplicates(subset=INDEX).reset_index(drop=True)
    gk["minutes_col"] = _num(gk["gk_minutes"])
    gk["pos_group"] = "GK"
    gk_metrics = _compute(GK_METRICS, gk, is_gk=True)
    gk_ident = _identity(gk)

    players = pd.concat([of_ident, gk_ident], ignore_index=True)
    players = players.drop_duplicates(subset=INDEX).reset_index(drop=True)
    metrics = pd.concat([of_metrics, gk_metrics], ignore_index=True)
    return players, metrics


def build_understat_only(seasons: list[str]) -> pd.DataFrame:
    """Players table for the League-Overview leaderboards from Understat ALONE.

    FBref (positions, minutes, the percentile scouting profile) is CAPTCHA-gated
    for the live season, but Understat already carries every leaderboard metric
    (goals, xG, assists, xA, key passes, shots). This yields a players.parquet
    slice good enough to light up the Home leaderboards + Golden Boot tile while
    FBref catches up; it deliberately produces NO player_metrics, so the Player
    Profile (which keys its season list off player_metrics) stays clean until the
    full FBref build lands and _merge_season replaces these rows.
    """
    u = us.fetch(seasons)
    if u is None or u.empty:
        return pd.DataFrame()
    out = u[INDEX].copy()
    out["pos"] = ""
    out["nation"] = ""
    out["age"] = np.nan
    out["minutes"] = np.nan          # unknown without FBref
    out["pos_group"] = ""
    out["limited_sample"] = True     # no minutes to qualify a sample
    for col in _RAW_TOTALS:          # goals/assists/np_goals/xg/xa/key_passes/shots
        out[col] = pd.to_numeric(u[col], errors="coerce") if col in u.columns else np.nan
    log.info("Understat-only players -> %s (%d rows, %d seasons)",
             out.shape, len(out), out["season"].nunique())
    return out


def build_all(seasons: list[str]) -> dict[str, pd.DataFrame]:
    """Players + metrics (FBref/Understat), standings & team_match (Understat)."""
    from etl.standings import build_standings, build_team_match
    players, metrics = build(seasons)
    return {
        "players": players,
        "player_metrics": metrics,
        "standings": build_standings(seasons),
        "team_match": build_team_match(seasons),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", default=["2425"])
    args = ap.parse_args()

    tables = build_all(args.seasons)
    for name, df in tables.items():
        write_parquet_atomic(df, name)
    log.info("wrote %s", ", ".join(f"{n} ({len(d)})" for n, d in tables.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
