"""League Overview — landing page (Streamlit entrypoint app/Home.py).

Standings (with xG shadow table) + leaderboards. Clicking a leaderboard row
navigates to that player's profile; clicking a standings row opens the team
dashboard. Filter state (league/season) persists via st.session_state.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import data_access as da  # noqa: E402

st.set_page_config(page_title="Football Analytics", page_icon="⚽", layout="wide")

LEAGUE_LABELS = {
    "ENG-Premier League": "Premier League",
    "ESP-La Liga": "La Liga",
    "ITA-Serie A": "Serie A",
    "GER-Bundesliga": "Bundesliga",
    "FRA-Ligue 1": "Ligue 1",
}


@st.cache_data(show_spinner=False)
def _load():
    return da.load("players"), da.load("standings")


players, standings = _load()

st.title("⚽ Football Analytics")
st.caption("Top-5 European league player & tactical analytics")

if players.empty:
    st.info("No dataset yet. Build it with:\n\n```\npython -m etl.build_players --seasons 2425\n```",
            icon="🗂️")
    st.stop()

# --- Filters (persist across pages) ------------------------------------------
seasons = sorted(players["season"].unique(), reverse=True)
league_keys = [l for l in LEAGUE_LABELS if l in set(players["league"])]

with st.sidebar:
    st.header("Filters")
    season = st.selectbox("Season", seasons, format_func=lambda s: f"20{s[:2]}/{s[2:]}",
                          key="flt_season")
    league = st.selectbox("League", league_keys,
                          format_func=lambda l: LEAGUE_LABELS.get(l, l),
                          key="flt_league_single")

st.subheader(f"{LEAGUE_LABELS.get(league, league)} · 20{season[:2]}/{season[2:]}")
st.caption(f"Data last updated: {da.last_updated('players')}")

pl = players[(players["season"] == season) & (players["league"] == league)]


def _goto_player(row: pd.Series) -> None:
    st.session_state["nav_player"] = (row["league"], row["season"], row["team"], row["player"])
    st.switch_page("pages/1_Player_Profile.py")


# --- Standings ---------------------------------------------------------------
st.markdown("### Standings")
tbl = standings[(standings["season"] == season) & (standings["league"] == league)]
if tbl.empty:
    st.caption("No standings available for this selection.")
else:
    show = tbl.drop(columns=["league", "season"]).reset_index(drop=True)
    ev = st.dataframe(
        show, hide_index=True, width="stretch",
        on_select="rerun", selection_mode="single-row", key="standings",
        column_config={
            "position": st.column_config.NumberColumn("#", width="small"),
            "xG": st.column_config.NumberColumn("xG", help="Expected goals for"),
            "xGA": st.column_config.NumberColumn("xGA", help="Expected goals against"),
            "xGD": st.column_config.NumberColumn("xGD", help="Expected goal difference"),
            "xPTS": st.column_config.NumberColumn("xPTS", help="Expected points"),
        },
    )
    if ev.selection.rows:
        team = show.iloc[ev.selection.rows[0]]["team"]
        st.session_state["nav_team"] = (league, season, team)
        st.switch_page("pages/2_Team_Dashboard.py")
    st.caption("Real table alongside its expected-goals shadow (xG/xGA/xGD/xPTS). "
               "Click a row for the team dashboard. Sort by clicking any column.")

# --- Leaderboards ------------------------------------------------------------
st.markdown("### Leaderboards")
st.caption("Season totals. Click a player to open their profile.")

BOARDS = [
    ("Top scorers", "goals", "Goals"),
    ("Expected goals (xG)", "xg", "xG"),
    ("Top assists", "assists", "Assists"),
    ("Expected assists (xA)", "xa", "xA"),
    ("Key passes", "key_passes", "Key passes"),
    ("Shots", "shots", "Shots"),
]

cols = st.columns(3)
for i, (title, metric, label) in enumerate(BOARDS):
    if metric not in pl.columns:
        continue
    board = (pl.dropna(subset=[metric])
             .sort_values(metric, ascending=False)
             .head(10)[["player", "team", metric, "league", "season"]]
             .reset_index(drop=True))
    with cols[i % 3]:
        st.markdown(f"**{title}**")
        disp = board[["player", "team", metric]].rename(
            columns={"player": "Player", "team": "Team", metric: label})
        disp[label] = disp[label].round(1) if metric in ("xg", "xa") else disp[label].astype(int)
        ev = st.dataframe(disp, hide_index=True, width="stretch",
                          on_select="rerun", selection_mode="single-row", key=f"lb_{metric}")
        if ev.selection.rows:
            _goto_player(board.iloc[ev.selection.rows[0]])

st.divider()
st.page_link("pages/1_Player_Profile.py", label="Player Profile — percentile scouting report", icon="👤")
st.caption("Player metrics: FBref (goals, shots, discipline) + Understat (xG, xA, key passes). "
           "Standings xG from Understat.")
