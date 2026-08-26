"""Compare — put 2-3 players (or 2-3 teams) side by side (Phase 4).

Players: overlaid percentile radars per concept + a per-90 / percentile
difference table. Teams: overlaid radar of league-relative team strengths +
a table-level stat difference. Everything reads pre-built parquets via
data_access; no scraping here.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import data_access as da  # noqa: E402
import ui_theme  # noqa: E402
from viz.radar import radar_overlay, PALETTE  # noqa: E402
from etl.metrics import (  # noqa: E402
    OUTFIELD_METRICS, GK_METRICS, OUTFIELD_CONCEPTS, GK_CONCEPTS,
)

st.set_page_config(page_title="Compare", layout="wide",
                   initial_sidebar_state="collapsed")
ui_theme.apply()
ui_theme.masthead(active="Compare")

LEAGUE_LABELS = {
    "ENG-Premier League": "Premier League", "ESP-La Liga": "La Liga",
    "ITA-Serie A": "Serie A", "GER-Bundesliga": "Bundesliga", "FRA-Ligue 1": "Ligue 1",
}

# Label order per concept, taken from the metric registry so radar axes are stable.
CONCEPT_LABELS: dict[str, list[str]] = {}
for _m in OUTFIELD_METRICS + GK_METRICS:
    CONCEPT_LABELS.setdefault(_m.concept, []).append(_m.label)


@st.cache_data(show_spinner=False)
def _load():
    return (da.load("players"), da.load("player_metrics"),
            da.load("standings"), da.load("team_match"))


players, metrics, standings, team_match = _load()

if players.empty:
    st.info("No dataset yet. Build it with:\n\n```\npython -m etl.build_players --seasons 2425\n```")
    st.stop()

ui_theme.context_header("Side by side", "Compare")
mode = st.radio("Compare", ["Players", "Teams"], horizontal=True, label_visibility="collapsed")


def _chip(name: str, color: str) -> str:
    return (f"<span style='display:inline-block;width:11px;height:11px;border-radius:50%;"
            f"background:{color};margin-right:6px;vertical-align:middle'></span>{name}")


# =============================================================================
# PLAYERS
# =============================================================================
if mode == "Players":
    # Metrics-driven (see Player Profile): only seasons with FBref percentile
    # profiles, so Understat-only leaderboard seasons don't yield empty radars.
    seasons = sorted(metrics["season"].astype(str).unique(), reverse=True)
    leagues = [l for l in LEAGUE_LABELS if l in set(players["league"])]

    fc1, fc2 = st.columns([1, 2])
    season = fc1.selectbox("Season", seasons, format_func=lambda s: f"20{s[:2]}/{s[2:]}",
                           key="flt_season")
    picked_leagues = fc2.multiselect("League(s)", leagues, default=leagues,
                                     format_func=lambda l: LEAGUE_LABELS.get(l, l),
                                     key="flt_leagues")

    pool = players[(players["season"] == season) & (players["league"].isin(picked_leagues))]
    if pool.empty:
        st.warning("No players for that league/season selection.")
        st.stop()

    pool = pool.sort_values("player")
    labels = {
        f"{r.player} — {r.team} ({r.pos})": (r.league, r.season, r.team, r.player)
        for r in pool.itertuples()
    }
    chosen = st.multiselect("Pick 2-3 players", list(labels.keys()),
                            max_selections=3, placeholder="Type names…")
    if len(chosen) < 2:
        st.caption("Select at least two players to compare.")
        st.stop()

    # Resolve rows for each chosen player.
    people = []
    for lbl in chosen:
        lg, sn, tm, pl = labels[lbl]
        prow = pool[(pool["league"] == lg) & (pool["team"] == tm)
                    & (pool["player"] == pl)].iloc[0]
        pm = metrics[(metrics["league"] == lg) & (metrics["season"] == sn)
                     & (metrics["team"] == tm) & (metrics["player"] == pl)]
        people.append({"row": prow, "pm": pm, "name": pl, "team": tm,
                       "gk": prow["pos_group"] == "GK"})

    # Header band — one column per player.
    cols = st.columns(len(people))
    for i, (col, p) in enumerate(zip(cols, people)):
        r = p["row"]
        col.markdown(_chip(p["name"], PALETTE[i % len(PALETTE)]), unsafe_allow_html=True)
        col.metric("Team", p["team"])
        col.caption(f"{r['pos']} · Age {'—' if pd.isna(r['age']) else int(r['age'])} · "
                    f"{'—' if pd.isna(r['minutes']) else int(r['minutes'])} min")
        if bool(r["limited_sample"]):
            col.caption("Limited sample (<450 min)")

    st.caption(f"20{season[:2]}/{season[2:]} · percentiles vs positional peers in the selection.")
    st.divider()

    n_gk = sum(p["gk"] for p in people)
    if 0 < n_gk < len(people):
        st.warning("Mixing goalkeepers with outfield players — their metrics aren't "
                   "comparable, so radars are hidden. See the raw table below.")
        radar_ok = False
        concepts = []
    else:
        radar_ok = True
        concepts = GK_CONCEPTS if n_gk == len(people) else OUTFIELD_CONCEPTS

    def _pct_map(pm: pd.DataFrame) -> dict[str, float]:
        return dict(zip(pm["label"], pm["percentile"]))

    def _val_map(pm: pd.DataFrame) -> dict[str, tuple[float, str]]:
        return {lb: (v, u) for lb, v, u in zip(pm["label"], pm["value"], pm["unit"])}

    pct_maps = [_pct_map(p["pm"]) for p in people]
    val_maps = [_val_map(p["pm"]) for p in people]

    def _fmt(unit: str, value: float) -> str:
        if pd.isna(value):
            return "—"
        return f"{value:.1f}%" if unit == "%" else f"{value:.2f}"

    for concept in (concepts if radar_ok else CONCEPT_LABELS.keys()):
        clabels = CONCEPT_LABELS.get(concept, [])
        # Any player carry this concept at all?
        if not any(concept in set(p["pm"]["concept"]) for p in people):
            continue
        st.subheader(concept)
        left, right = st.columns([1, 1])

        # Radar over labels where every player has a comparable percentile.
        with left:
            comparable = [l for l in clabels
                          if all(l in m and not pd.isna(m[l]) for m in pct_maps)]
            if radar_ok and len(comparable) >= 3:
                series = [{"name": p["name"],
                           "values": [pct_maps[i][l] for l in comparable]}
                          for i, p in enumerate(people)]
                st.plotly_chart(radar_overlay(series, comparable, title=concept),
                                theme=None, width="stretch")
            else:
                st.caption("Radar hidden (need ≥3 shared metrics with valid percentiles).")

        # Difference table — value + percentile per player, per metric.
        with right:
            rows = []
            for l in clabels:
                if not any(l in m for m in val_maps):
                    continue
                row = {"Metric": l}
                for i, p in enumerate(people):
                    v, u = val_maps[i].get(l, (np.nan, ""))
                    pct = pct_maps[i].get(l, np.nan)
                    row[p["name"]] = (f"{_fmt(u, v)}"
                                      + ("" if pd.isna(pct) else f"  ({pct:.0f})"))
                rows.append(row)
            if rows:
                ui_theme.data_table(pd.DataFrame(rows))
                st.caption("Cell = per-90 / value  (percentile).")
        st.divider()

    st.caption(f"Data last updated: {da.last_updated('players')}")

# =============================================================================
# TEAMS
# =============================================================================
else:
    if standings.empty:
        st.info("No standings yet — run `python -m etl.build_players --seasons 2425`.")
        st.stop()

    seasons = sorted(standings["season"].unique(), reverse=True)
    leagues = [l for l in LEAGUE_LABELS if l in set(standings["league"])]

    fc1, fc2 = st.columns(2)
    season = fc1.selectbox("Season", seasons, format_func=lambda s: f"20{s[:2]}/{s[2:]}",
                           key="flt_season")
    league = fc2.selectbox("League", leagues,
                           format_func=lambda l: LEAGUE_LABELS.get(l, l),
                           key="flt_league_single")

    tbl = standings[(standings["season"] == season) & (standings["league"] == league)].copy()
    if tbl.empty:
        st.warning("No teams for this selection.")
        st.stop()

    team_opts = tbl.sort_values("position")["team"].tolist()
    chosen = st.multiselect("Pick 2-3 teams", team_opts, max_selections=3,
                            placeholder="Type team names…")
    if len(chosen) < 2:
        st.caption("Select at least two teams to compare.")
        st.stop()

    # Mean PPDA per team (pressing) from team_match, joined onto the table.
    if not team_match.empty:
        tm = team_match[(team_match["league"] == league) & (team_match["season"] == season)]
        ppda = tm.groupby("team")["ppda"].mean()
        tbl["PPDA"] = tbl["team"].map(ppda)
    else:
        tbl["PPDA"] = np.nan

    # Radar axes: league-relative percentile (0-100) so strengths are comparable.
    # (metric column, axis label, invert=lower-is-better)
    RADAR = [
        ("GF", "Attack (GF)", False),
        ("xG", "xG", False),
        ("GA", "Defence (GA)", True),
        ("xGA", "xG against", True),
        ("Pts", "Points", False),
        ("PPDA", "Pressing", True),
    ]
    for col, _lbl, invert in RADAR:
        pct = tbl[col].rank(pct=True) * 100.0
        if invert:
            pct = 100.0 - pct
        tbl[f"_pct_{col}"] = pct

    trows = {t: tbl[tbl["team"] == t].iloc[0] for t in chosen}

    # Header band.
    cols = st.columns(len(chosen))
    for i, (col, t) in enumerate(zip(cols, chosen)):
        r = trows[t]
        col.markdown(_chip(t, PALETTE[i % len(PALETTE)]), unsafe_allow_html=True)
        col.metric("Position", f"{int(r['position'])}")
        col.caption(f"{int(r['W'])}-{int(r['D'])}-{int(r['L'])} · {int(r['Pts'])} pts")
    st.caption(f"{LEAGUE_LABELS.get(league, league)} · 20{season[:2]}/{season[2:]} · "
               "radar = rank within this league (100 = best).")
    st.divider()

    left, right = st.columns([1, 1])
    with left:
        axes = [lbl for _c, lbl, _i in RADAR]
        series = [{"name": t,
                   "values": [trows[t][f"_pct_{c}"] for c, _l, _i in RADAR]}
                  for t in chosen]
        # Guard against an all-NaN axis (e.g. PPDA missing) collapsing the fill.
        if any(any(pd.isna(v) for v in s["values"]) for s in series):
            for s in series:
                s["values"] = [0.0 if pd.isna(v) else v for v in s["values"]]
        st.plotly_chart(radar_overlay(series, axes, title="Team strengths"),
                        theme=None, width="stretch")

    with right:
        STATS = [("Pts", "Points", 0), ("GF", "Goals for", 0), ("GA", "Goals against", 0),
                 ("GD", "Goal diff", 0), ("xG", "xG", 1), ("xGA", "xGA", 1),
                 ("xGD", "xGD", 1), ("xPTS", "xPTS", 1), ("PPDA", "PPDA (press)", 1)]
        rows = []
        for col, lbl, dp in STATS:
            row = {"Metric": lbl}
            for t in chosen:
                v = trows[t][col]
                row[t] = "—" if pd.isna(v) else (f"{v:.{dp}f}" if dp else f"{int(v)}")
            rows.append(row)
        ui_theme.data_table(pd.DataFrame(rows))
        st.caption("Real table stats alongside their xG shadow. Lower PPDA = more pressing.")

    st.caption(f"Data last updated: {da.last_updated('standings')}")

st.divider()
st.page_link("Home.py", label="← League Overview")
st.page_link("pages/1_Player_Profile.py", label="Player Profile")
st.page_link("pages/2_Team_Dashboard.py", label="Team Dashboard")
