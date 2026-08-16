"""League Overview — landing page (Streamlit entrypoint app/Home.py).

Masthead + top-bar filters, KPI stat-tiles, the standings grid (interactive:
click a row for the team dashboard), and styled leaderboard cards (click a
name for the player profile, via a query-param link). Filter state persists
across pages via st.session_state.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import data_access as da  # noqa: E402
import ui_theme  # noqa: E402

st.set_page_config(page_title="Futlytics", layout="wide",
                   initial_sidebar_state="collapsed")
ui_theme.apply()
ui_theme.consume_leaderboard_click()  # may switch_page + stop if ?lbp= is set
ui_theme.consume_team_click()          # may switch_page + stop if ?tbp= is set

LEAGUE_LABELS = {
    "ENG-Premier League": "Premier League",
    "ESP-La Liga": "La Liga",
    "ITA-Serie A": "Serie A",
    "GER-Bundesliga": "Bundesliga",
    "FRA-Ligue 1": "Ligue 1",
}

BOARDS = [
    ("Top scorers", "goals", "Goals", ""),
    ("Expected goals", "xg", "xG", "cool"),
    ("Top assists", "assists", "Assists", "amber"),
    ("Expected assists", "xa", "xA", "cool"),
    ("Key passes", "key_passes", "Key passes", "amber"),
    ("Shots", "shots", "Shots", ""),
]


@st.cache_data(show_spinner=False)
def _load():
    return da.load("players"), da.load("standings")


players, standings = _load()

ui_theme.masthead(active="Overview")

if players.empty:
    st.info("No dataset yet. Build it with:\n\n```\npython -m etl.build_players --seasons 2425\n```")
    st.stop()

# --- Filters (top bar; state persists across pages) --------------------------
seasons = sorted(players["season"].unique(), reverse=True)
league_keys = [l for l in LEAGUE_LABELS if l in set(players["league"])]

fc1, fc2, _sp = st.columns([1, 1, 2])
league = fc1.selectbox("League", league_keys,
                       format_func=lambda l: LEAGUE_LABELS.get(l, l),
                       key="flt_league_single")
season = fc2.selectbox("Season", seasons, format_func=lambda s: f"20{s[:2]}/{s[2:]}",
                       key="flt_season")

# --- Context header ----------------------------------------------------------
st.markdown(
    f'<p class="eyebrow">{LEAGUE_LABELS.get(league, league)} · 20{season[:2]}/{season[2:]}</p>'
    '<h1 style="font-size:clamp(2rem,4.4vw,2.8rem);margin:0;">League Overview</h1>',
    unsafe_allow_html=True,
)
st.caption(f"Data updated {da.last_updated('players')}")

pl = players[(players["season"] == season) & (players["league"] == league)]
tbl = standings[(standings["season"] == season) & (standings["league"] == league)]

# --- KPI tiles ---------------------------------------------------------------
tiles: list[dict] = []
if not tbl.empty:
    champ = tbl.sort_values("position").iloc[0]
    tiles.append({"label": "Champions", "big": champ["team"],
                  "sub": f'<b>{int(champ["Pts"])}</b> pts · <b>{int(champ["GD"]):+d}</b> GD'})
if not pl.empty and "goals" in pl.columns and pl["goals"].notna().any():
    gb = pl.sort_values("goals", ascending=False).iloc[0]
    xg_txt = f' · {gb["xg"]:.1f} xG' if pd.notna(gb.get("xg")) else ""
    tiles.append({"label": "Golden Boot", "big": gb["player"], "tone": "amber",
                  "sub": f'<b>{int(gb["goals"])}</b> goals{xg_txt}'})
if not tbl.empty and "xG" in tbl.columns:
    bx = tbl.sort_values("xG", ascending=False).iloc[0]
    tiles.append({"label": "Best attack · xG", "big": bx["team"], "tone": "cool",
                  "sub": f'<b>{bx["xG"]:.1f}</b> xG · {int(bx["Pts"])} pts'})
if not tbl.empty and {"Pts", "xPTS"} <= set(tbl.columns):
    op = tbl.assign(_d=tbl["Pts"] - tbl["xPTS"]).sort_values("_d", ascending=False).iloc[0]
    tiles.append({"label": "Over-performer", "big": op["team"],
                  "sub": f'<b class="up">{op["Pts"] - op["xPTS"]:+.1f}</b> pts vs xPTS'})
if tiles:
    ui_theme.kpi_row(tiles)

# --- Standings (interactive grid) --------------------------------------------
ui_theme.section_header(
    "The table", "Standings",
    note="Real table beside its expected-goals shadow. Click a row for the team dashboard.")
if tbl.empty:
    st.caption("No standings available for this selection.")
else:
    show = tbl.drop(columns=["league", "season"]).reset_index(drop=True)
    for c in ("xG", "xGA", "xGD", "xPTS"):  # tidy the expected-goals decimals
        if c in show.columns:
            show[c] = show[c].map(lambda v: "" if pd.isna(v) else f"{float(v):.1f}")
    show = show.rename(columns={"position": "#"})
    ui_theme.standings_table(show, league, season, team_col="team", pos_col="#")

# --- Leaderboards (styled cards; click a name -> player profile) -------------
ui_theme.section_header(
    "Leaders", "Season leaderboards",
    note="Bar length is relative to the leader. Click any name to open the player.")

boards_data: list[dict] = []
for title, metric, label, tone in BOARDS:
    if metric not in pl.columns:
        continue
    b = pl.dropna(subset=[metric]).sort_values(metric, ascending=False).head(8)
    if b.empty:
        continue
    mx = float(b[metric].max()) or 1.0
    rows = []
    for _, r in b.iterrows():
        val = round(float(r[metric]), 1) if metric in ("xg", "xa") else int(r[metric])
        rows.append({
            "nm": r["player"], "tm": r["team"], "val": val,
            "frac": max(0.0, float(r[metric]) / mx),
            "league": r["league"], "season": r["season"],
            "team": r["team"], "player": r["player"],
        })
    boards_data.append({"title": title, "unit": label, "tone": tone, "rows": rows})

if boards_data:
    ui_theme.leaders_grid(boards_data)

st.caption("Player metrics: FBref (goals, shots, discipline) + Understat (xG, xA, key passes). "
           "Standings & xG shadow from Understat.")
