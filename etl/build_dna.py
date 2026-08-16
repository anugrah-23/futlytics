"""Build the Player DNA tables from cached WhoScored/Opta events.

Featured-club-only (that's all we scrape). Output (data/processed/):
  player_dna.parquet   tidy long: (player-season, param) + value + percentile,
                       tagged with concept + a normalised name key for joining
                       to the FBref-based Player Profile.

Percentiles are ranked within (season, position group) across the featured-club
player pool — a smaller universe than the Top-5, so they read as "vs other
players at big clubs", which the UI states explicitly.

Run:  python -m etl.build_dna --seasons 2425 2324
"""
from __future__ import annotations

import argparse
import logging
import unicodedata
from collections import defaultdict

import numpy as np
import pandas as pd

from etl.dna_events import (ATT_PEN_X, FINAL_THIRD_X, HALFSPACE_Y, load_events)
from etl.dna_metrics import PARAM_BY_KEY, PARAMS
from etl.io_utils import write_parquet_atomic
from etl.transform import MIN_MINUTES_DEFAULT, percentile_within_group

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("build_dna")

KEY = ["league", "season", "playerId"]
PROG_MIN = 10.0        # forward advance (0-100) for a pass/carry to be "progressive"
SWITCH_Y = 40.0        # lateral change for a "switch of play"
LONG_LEN = 30.0        # Opta pass Length threshold for long balls
SHORT_LEN = 15.0
BOX_Y = (21.1, 78.9)   # penalty-area width band on a 0-100 pitch
FEATURED_LEAGUES = ["ENG-Premier League", "ESP-La Liga", "GER-Bundesliga",
                    "FRA-Ligue 1", "ITA-Serie A"]


def _norm(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(name))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _hs(y: float) -> bool:
    return (HALFSPACE_Y[0][0] <= y <= HALFSPACE_Y[0][1]
            or HALFSPACE_Y[1][0] <= y <= HALFSPACE_Y[1][1])


# --- 1. sequence-derived stats (need event-to-event adjacency) ---------------

def _adjacency(events: pd.DataFrame) -> pd.DataFrame:
    """Per (league, season, playerId): carries, receptions, one-touch passes and
    post-recovery retention — derived by walking each match's ordered events
    (the ball's next same-team touch is the receiver / carrier)."""
    acc: dict[tuple, dict] = defaultdict(lambda: defaultdict(float))
    partners: dict[tuple, set] = defaultdict(set)
    cols = ["seq", "playerId", "team", "type", "outcome", "is_touch",
            "x", "y", "end_x", "end_y", "league", "season"]
    for _gid, g in events.groupby("game_id", sort=False):
        r = g[cols].sort_values("seq").to_records(index=False)
        n = len(r)
        for i in range(n):
            e = r[i]
            k = (e.league, e.season, int(e.playerId))
            if i > 0 and e.is_touch:                     # carry = consecutive touches
                p = r[i - 1]
                if int(p.playerId) == int(e.playerId) and p.is_touch:
                    d = float(np.hypot(e.x - p.x, e.y - p.y))
                    if 0 < d < 60:
                        a = acc[k]
                        a["carries"] += 1
                        a["carry_dist"] += d
                        if e.x - p.x >= PROG_MIN:
                            a["prog_carries"] += 1
                        if p.x < FINAL_THIRD_X <= e.x:
                            a["carries_final_third"] += 1
                        if p.x < ATT_PEN_X <= e.x and BOX_Y[0] <= e.y <= BOX_Y[1]:
                            a["carries_box"] += 1
            if e.type == "Pass" and e.outcome == 1:
                for j in range(i + 1, min(i + 6, n)):    # receiver = next same-team touch
                    q = r[j]
                    if q.is_touch and q.team == e.team and int(q.playerId) != int(e.playerId):
                        rk = (q.league, q.season, int(q.playerId))
                        acc[rk]["received"] += 1
                        if e.end_x - e.x >= PROG_MIN:
                            acc[rk]["prog_received"] += 1
                        partners[k].add(int(q.playerId))
                        break
                if i == 0 or int(r[i - 1].playerId) != int(e.playerId):
                    acc[k]["one_touch"] += 1
            if e.type == "BallRecovery":
                a = acc[k]
                a["rec_total"] += 1
                for j in range(i + 1, min(i + 4, n)):
                    q = r[j]
                    if q.team == e.team and q.is_touch:
                        a["rec_retained"] += 1 if q.outcome == 1 else 0
                        break
    rows = []
    for k, a in acc.items():
        a = dict(a)
        a["partners"] = float(len(partners.get(k, ())))
        a["league"], a["season"], a["playerId"] = k
        rows.append(a)
    return pd.DataFrame(rows).fillna(0.0)


# --- 2. vectorised event aggregates ------------------------------------------

def _vectorized(ev: pd.DataFrame) -> pd.DataFrame:
    e = ev
    is_pass = e["type"] == "Pass"
    ok = e["outcome"] == 1
    cp = is_pass & ok                              # completed pass
    fwd = cp & (e["end_x"] > e["x"])
    inft = e["x"] >= FINAL_THIRD_X
    hs = e["x"].notna() & e["y"].map(_hs)
    box_end = (e["end_x"] >= ATT_PEN_X) & e["end_y"].between(*BOX_Y)
    long_p = is_pass & (e["length"] >= LONG_LEN)
    short_p = is_pass & (e["length"] < SHORT_LEN)

    df = e.assign(
        _touch=e["is_touch"].astype(float),
        _pass=is_pass.astype(float),
        _cp=cp.astype(float),
        _fwd=fwd.astype(float),
        _long=long_p.astype(float),
        _long_ok=(long_p & ok).astype(float),
        _short=short_p.astype(float),
        _through=(is_pass & e["is_throughball"]).astype(float),
        _switch=(cp & ((e["end_y"] - e["y"]).abs() >= SWITCH_Y)).astype(float),
        _prog_pass=(cp & ((e["end_x"] - e["x"]) >= PROG_MIN)).astype(float),
        _prog_dist=np.where(cp, np.maximum(0.0, e["end_x"] - e["x"]), 0.0),
        _pass_ft=(cp & (e["x"] < FINAL_THIRD_X) & (e["end_x"] >= FINAL_THIRD_X)).astype(float),
        _pass_box=(cp & (e["x"] < ATT_PEN_X) & box_end).astype(float),
        _keypass=e["is_keypass"].astype(float),
        _ft_touch=(e["is_touch"] & inft).astype(float),
        _ft_pass=(is_pass & inft).astype(float),
        _ft_cp=(cp & inft).astype(float),
        _hs_touch=(e["is_touch"] & hs).astype(float),
        _hs_pass=(is_pass & hs).astype(float),
        _hs_left=(e["is_touch"] & e["y"].between(*HALFSPACE_Y[0])).astype(float),
        _hs_right=(e["is_touch"] & e["y"].between(*HALFSPACE_Y[1])).astype(float),
        _take=(e["type"] == "TakeOn").astype(float),
        _take_ok=((e["type"] == "TakeOn") & ok).astype(float),
        _shot=e["is_shot"].astype(float),
        _goal=e["is_goal"].astype(float),
        _sot=(e["is_shot"] & (e["type"].isin(["Goal", "SavedShot"]))).astype(float),
        _sh_r=(e["is_shot"] & (e["foot"] == "right")).astype(float),
        _sh_l=(e["is_shot"] & (e["foot"] == "left")).astype(float),
        _sh_h=(e["is_shot"] & (e["foot"] == "head")).astype(float),
        _aerial=(e["type"] == "Aerial").astype(float),
        _aerial_w=((e["type"] == "Aerial") & ok).astype(float),
        _aerial_off=((e["type"] == "Aerial") & (e["x"] >= 50)).astype(float),
        _aerial_def=((e["type"] == "Aerial") & (e["x"] < 50)).astype(float),
        _foul_won=((e["type"] == "Foul") & ok).astype(float),
        _disp=(e["type"] == "Dispossessed").astype(float),
        _tackle=(e["type"] == "Tackle").astype(float),
        _tackle_w=((e["type"] == "Tackle") & ok).astype(float),
        _intercept=(e["type"] == "Interception").astype(float),
        _clear=(e["type"] == "Clearance").astype(float),
        _block=(e["type"] == "BlockedPass").astype(float),
        _recovery=(e["type"] == "BallRecovery").astype(float),
        _rec_high=((e["type"] == "BallRecovery") & (e["x"] >= 50)).astype(float),
        _rec_att=((e["type"] == "BallRecovery") & (e["x"] >= FINAL_THIRD_X)).astype(float),
        _pass_fail=(is_pass & ~ok).astype(float),
        _take_fail=((e["type"] == "TakeOn") & ~ok).astype(float),
    )
    agg = df.groupby(KEY)[[c for c in df.columns if c.startswith("_")]].sum()
    return agg.reset_index()


# --- 3. player identity (position group via mode, minutes, team) -------------

def _meta(meta: pd.DataFrame) -> pd.DataFrame:
    good = meta[meta["pos_group"] != "Unknown"]
    mode_pos = (good.groupby(KEY[:2] + ["playerId"])["pos_group"]
                .agg(lambda s: s.value_counts().index[0]))
    mode_team = (meta.groupby(KEY[:2] + ["playerId"])["team"]
                 .agg(lambda s: s.value_counts().index[0]))
    name = (meta.groupby(KEY[:2] + ["playerId"])["player"]
            .agg(lambda s: s.value_counts().index[0]))
    mins = meta.groupby(KEY[:2] + ["playerId"])["minutes"].sum()
    apps = meta.groupby(KEY[:2] + ["playerId"])["game_id"].nunique()
    out = pd.DataFrame({"player": name, "team": mode_team,
                        "pos_group": mode_pos, "minutes": mins, "apps": apps})
    out["pos_group"] = out["pos_group"].fillna("Unknown")
    return out.reset_index()


# --- 4. assemble parameter values --------------------------------------------

def _safe(n, d):
    d = d.replace(0, np.nan)
    return (n / d)


def _params(wide: pd.DataFrame) -> pd.DataFrame:
    p90 = 90.0 / wide["minutes"].replace(0, np.nan)
    g = wide  # shorthand; underscore cols from _vectorized, plain from _adjacency

    def per90(col):
        return g.get(col, 0.0) * p90

    out = pd.DataFrame(index=wide.index)
    # Passing Profile
    out["pass_vol"] = per90("_pass")
    out["pass_pct"] = _safe(g["_cp"], g["_pass"]) * 100
    out["long_pct"] = _safe(g["_long_ok"], g["_long"]) * 100
    out["fwd_pass_pct"] = _safe(g["_fwd"], g["_cp"]) * 100
    out["through_balls"] = per90("_through")
    out["switches"] = per90("_switch")
    # Progression
    out["prog_passes"] = per90("_prog_pass")
    out["prog_pass_dist"] = g["_prog_dist"] * p90
    out["passes_final_third"] = per90("_pass_ft")
    out["prog_carries"] = g.get("prog_carries", 0.0) * p90
    out["carries_final_third"] = g.get("carries_final_third", 0.0) * p90
    # Carrying Profile
    out["carries"] = g.get("carries", 0.0) * p90
    out["carry_dist"] = g.get("carry_dist", 0.0) * p90
    out["take_ons"] = per90("_take")
    out["take_on_pct"] = _safe(g["_take_ok"], g["_take"]) * 100
    out["carries_box"] = g.get("carries_box", 0.0) * p90
    # Shooting & Footedness
    out["shots"] = per90("_shot")
    out["goals"] = per90("_goal")
    out["sot_pct"] = _safe(g["_sot"], g["_shot"]) * 100
    foot_tot = g["_sh_r"] + g["_sh_l"] + g["_sh_h"]
    out["foot_right_pct"] = _safe(g["_sh_r"], foot_tot) * 100
    out["foot_left_pct"] = _safe(g["_sh_l"], foot_tot) * 100
    out["foot_head_pct"] = _safe(g["_sh_h"], foot_tot) * 100
    lr = g["_sh_r"] + g["_sh_l"]
    out["two_footed"] = _safe(np.minimum(g["_sh_r"], g["_sh_l"]),
                              np.maximum(g["_sh_r"], g["_sh_l"])) * 100
    # Aerial Duels
    out["aerials"] = per90("_aerial")
    out["aerials_won"] = per90("_aerial_w")
    out["aerial_pct"] = _safe(g["_aerial_w"], g["_aerial"]) * 100
    out["off_aerials"] = per90("_aerial_off")
    out["def_aerials"] = per90("_aerial_def")
    # Hold-Up Play
    out["att_touches"] = per90("_ft_touch")
    out["fouls_won"] = per90("_foul_won")
    out["dispossessed"] = per90("_disp")
    lost = g["_disp"] + g["_pass_fail"] + g["_take_fail"]
    out["retention_pct"] = (1 - _safe(lost, g["_touch"])) * 100
    out["ft_pass_pct"] = _safe(g["_ft_cp"], g["_ft_pass"]) * 100
    # Decision Making
    out["turnovers"] = lost * p90
    out["pass_success_dm"] = out["pass_pct"]
    out["take_on_success_dm"] = out["take_on_pct"]
    out["shot_conv"] = _safe(g["_goal"], g["_shot"]) * 100
    # Final Third
    out["ft_touches"] = per90("_ft_touch")
    out["ft_passes"] = per90("_ft_pass")
    out["passes_box"] = per90("_pass_box")
    out["key_passes"] = per90("_keypass")
    # Half-Spaces
    out["hs_touches"] = per90("_hs_touch")
    out["hs_passes"] = per90("_hs_pass")
    out["hs_receptions"] = g.get("received", 0.0) * 0  # placeholder, set below
    out["hs_left_pct"] = _safe(g["_hs_left"], g["_hs_touch"]) * 100
    out["hs_right_pct"] = _safe(g["_hs_right"], g["_hs_touch"]) * 100
    # Tempo Control
    out["touches"] = per90("_touch")
    out["pass_per_touch"] = _safe(g["_pass"], g["_touch"])
    out["one_touch_pct"] = _safe(g.get("one_touch", 0.0), g["_cp"]) * 100
    out["short_share"] = _safe(g["_short"], g["_pass"]) * 100
    # Defending Profile
    out["tackles"] = per90("_tackle")
    out["tackle_pct"] = _safe(g["_tackle_w"], g["_tackle"]) * 100
    out["interceptions"] = per90("_intercept")
    out["clearances"] = per90("_clear")
    out["blocks"] = per90("_block")
    # Post-Recovery
    out["recoveries"] = per90("_recovery")
    out["high_recoveries"] = per90("_rec_high")
    out["post_rec_ret"] = _safe(g.get("rec_retained", 0.0), g.get("rec_total", 0.0)) * 100
    out["counterpress"] = per90("_rec_att")
    # Link-Up & Synergy
    out["received"] = g.get("received", 0.0) * p90
    out["prog_received"] = g.get("prog_received", 0.0) * p90
    out["partners"] = _safe(g.get("partners", 0.0), g["apps"])
    out["pass_share"] = g["_cp"]  # normalised to team below
    # hs_receptions: half-space share of receptions ~ approximate via hs touch share
    out["hs_receptions"] = out["received"] * _safe(g["_hs_touch"], g["_touch"])
    return out


def build(seasons: list[str], leagues: list[str] | None = None) -> pd.DataFrame:
    leagues = leagues or FEATURED_LEAGUES
    ev, meta = load_events(leagues, seasons)
    if ev.empty:
        log.warning("no cached events for %s %s", leagues, seasons)
        return pd.DataFrame()

    log.info("aggregating %d events / %d player-matches", len(ev), len(meta))
    vec = _vectorized(ev)
    adj = _adjacency(ev)
    m = _meta(meta)

    wide = (m.merge(vec, on=KEY, how="left")
            .merge(adj, on=KEY, how="left"))
    wide = wide.fillna(0.0)

    # team pass share: player's completed passes vs an average team-mate's, over
    # the same league-season (a centrality proxy; ~100 = average involvement).
    team_cp = wide.groupby(["league", "season", "team"])["_cp"].transform("sum")
    team_players = wide.groupby(["league", "season", "team"])["_cp"].transform("size")
    avg_share = team_cp / team_players.replace(0, np.nan)

    vals = _params(wide)
    vals["pass_share"] = (wide["_cp"] / avg_share.replace(0, np.nan)) * 100

    ident = wide[["league", "season", "playerId", "player", "team",
                  "pos_group", "minutes", "apps"]].copy()
    ident["nkey"] = ident["player"].map(_norm)

    # --- percentile each param within (season, pos_group) --------------------
    pos_key = ident["season"].astype(str) + "|" + ident["pos_group"].astype(str)
    long_rows = []
    for prm in PARAMS:
        value = pd.to_numeric(vals[prm.key], errors="coerce")
        pct = percentile_within_group(value, pos_key, ident["minutes"],
                                      MIN_MINUTES_DEFAULT)
        if prm.invert:
            pct = 100.0 - pct
        blk = ident.copy()
        blk["concept"] = prm.concept
        blk["param_key"] = prm.key
        blk["label"] = prm.label
        blk["unit"] = prm.unit
        blk["value"] = value.to_numpy()
        blk["percentile"] = pct.to_numpy()
        long_rows.append(blk)
    out = pd.concat(long_rows, ignore_index=True)
    log.info("player_dna -> %s (%d players)", out.shape, ident["playerId"].nunique())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", default=["2425"])
    ap.add_argument("--leagues", nargs="+", default=None)
    args = ap.parse_args()
    df = build(args.seasons, args.leagues)
    if df.empty:
        log.error("no DNA built"); return 1
    write_parquet_atomic(df, "player_dna")
    log.info("wrote player_dna (%d rows)", len(df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
