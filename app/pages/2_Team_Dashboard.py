"""Team / Tactical Dashboard — the differentiator (Phase 3).

Shot map, shot territory, pressing & xG style, and pass network. Shot / xG /
pressing views come from Understat (reliable HTTP); the pass network comes from
pre-built WhoScored event data (offline batch — the app never scrapes live).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import data_access as da  # noqa: E402
from viz.pitch import shot_map, shot_heatmap, pass_network  # noqa: E402

st.set_page_config(page_title="Team Dashboard", page_icon="📊", layout="wide")

LEAGUE_LABELS = {
    "ENG-Premier League": "Premier League", "ESP-La Liga": "La Liga",
    "ITA-Serie A": "Serie A", "GER-Bundesliga": "Bundesliga", "FRA-Ligue 1": "Ligue 1",
}


@st.cache_data(show_spinner=False)
def _load():
    return (da.load("standings"), da.load("team_match"),
            da.load("shots"), da.load("pass_networks"))


standings, team_match, shots, pnets = _load()

st.title("📊 Team Dashboard")

if standings.empty:
    st.info("No team data yet. Build it with:\n\n```\npython -m etl.build_players --seasons 2425\n"
            "python -m etl.shots --seasons 2425\n```", icon="🗂️")
    st.stop()

# --- Filters -----------------------------------------------------------------
seasons = sorted(standings["season"].unique(), reverse=True)
leagues = [l for l in LEAGUE_LABELS if l in set(standings["league"])]
nav = st.session_state.pop("nav_team", None)

with st.sidebar:
    st.header("Filters")
    season = st.selectbox("Season", seasons, format_func=lambda s: f"20{s[:2]}/{s[2:]}",
                          key="flt_season")
    league = st.selectbox("League", leagues, format_func=lambda l: LEAGUE_LABELS.get(l, l),
                          key="flt_league_single")

tbl = standings[(standings["season"] == season) & (standings["league"] == league)]
team_opts = tbl.sort_values("position")["team"].tolist()
default_team = nav[2] if nav and nav[2] in team_opts else (team_opts[0] if team_opts else None)
if not team_opts:
    st.warning("No teams for this selection.")
    st.stop()
team = st.selectbox("Team", team_opts, index=team_opts.index(default_team))

trow = tbl[tbl["team"] == team].iloc[0]

# --- Header ------------------------------------------------------------------
c = st.columns(6)
c[0].metric("Position", f"{int(trow['position'])}")
c[1].metric("Record", f"{int(trow['W'])}-{int(trow['D'])}-{int(trow['L'])}")
c[2].metric("Points", f"{int(trow['Pts'])}", f"xPTS {trow['xPTS']:.0f}")
c[3].metric("Goals", f"{int(trow['GF'])}-{int(trow['GA'])}")
c[4].metric("xG", f"{trow['xG']:.0f}", f"xGA {trow['xGA']:.0f}")
c[5].metric("xGD", f"{trow['xGD']:+.1f}")
st.caption(f"{LEAGUE_LABELS.get(league, league)} · 20{season[:2]}/{season[2:]}")
st.divider()

# Shots for/against for this team.
sh = shots[(shots["league"] == league) & (shots["season"] == season)] if not shots.empty else shots
if not sh.empty:
    games = sh[sh["team"] == team]["game_id"].unique()
    shots_for = sh[(sh["team"] == team) & (sh["game_id"].isin(games))]
    shots_against = sh[(sh["game_id"].isin(games)) & (sh["team"] != team)]
else:
    shots_for = shots_against = pd.DataFrame()

tabs = st.tabs(["Overview", "Shot Map", "Shot Territory", "Pressing & Style", "Pass Network"])

# --- Overview ----------------------------------------------------------------
with tabs[0]:
    st.subheader("Expected-goals performance")
    st.caption("Over/under-performance vs the xG model — finishing and results luck.")
    o = st.columns(2)
    o[0].metric("Goals − xG", f"{trow['GF'] - trow['xG']:+.1f}",
                help="Positive = scoring more than chances suggest")
    o[1].metric("Points − xPTS", f"{trow['Pts'] - trow['xPTS']:+.1f}",
                help="Positive = out-performing the xG table")
    if not team_match.empty:
        tm = team_match[(team_match["league"] == league) & (team_match["season"] == season)
                        & (team_match["team"] == team)].sort_values("date")
        if not tm.empty:
            st.markdown("**Cumulative xG for vs against**")
            cum = pd.DataFrame({
                "xG for": tm["xgf"].cumsum().to_numpy(),
                "xG against": tm["xga"].cumsum().to_numpy(),
            }, index=range(1, len(tm) + 1))
            st.line_chart(cum, height=260)

# --- Shot Map ----------------------------------------------------------------
with tabs[1]:
    if shots_for.empty:
        st.info("Shot data not built yet — run `python -m etl.shots --seasons 2425`.")
    else:
        a, b = st.columns(2)
        with a:
            st.pyplot(shot_map(shots_for, against=False,
                               title=f"Shots for — {int(shots_for['is_goal'].sum())} goals"))
            st.caption(f"{len(shots_for)} shots · {shots_for['xg'].sum():.1f} xG · "
                       "★ = goal, size ∝ xG")
        with b:
            st.pyplot(shot_map(shots_against, against=True,
                               title=f"Shots against — {int(shots_against['is_goal'].sum())} goals"))
            st.caption(f"{len(shots_against)} shots · {shots_against['xg'].sum():.1f} xG conceded")

# --- Shot Territory ----------------------------------------------------------
with tabs[2]:
    if shots_for.empty:
        st.info("Shot data not built yet.")
    else:
        a, b = st.columns(2)
        a.pyplot(shot_heatmap(shots_for, against=False, title="Shot territory — for"))
        b.pyplot(shot_heatmap(shots_against, against=True, title="Shot territory — against"))
        st.caption("Kernel-density of shot locations — where this team creates vs concedes chances.")

# --- Pressing & Style --------------------------------------------------------
with tabs[3]:
    if team_match.empty:
        st.info("Team-match data not built yet.")
    else:
        tm = team_match[(team_match["league"] == league) & (team_match["season"] == season)]
        team_tm = tm[tm["team"] == team].sort_values("date")
        ppda = team_tm["ppda"].mean()
        league_ppda = tm.groupby("team")["ppda"].mean()
        rank = int((league_ppda < ppda).sum()) + 1  # lower PPDA = more pressing
        p = st.columns(3)
        p[0].metric("PPDA", f"{ppda:.1f}", help="Passes allowed per defensive action — LOWER = more intense pressing")
        p[1].metric("Pressing rank", f"{rank} / {len(league_ppda)}")
        p[2].metric("Deep completions / game", f"{team_tm['deep'].mean():.1f}",
                    help="Opponent passes completed near own goal — lower = better containment")
        st.markdown("**PPDA by match** (lower = pressing higher up)")
        st.line_chart(team_tm.set_index("date")[["ppda"]], height=240)
        st.caption("PPDA & deep completions from Understat. Lower PPDA = a more aggressive press.")

# --- Pass Network ------------------------------------------------------------
with tabs[4]:
    have = (not pnets.empty and "team" in pnets.columns
            and team in set(pnets["team"]))
    if not have:
        st.info(
            "**Pass network needs WhoScored event data** (Selenium-scraped offline, "
            "not fetched live by the app). Build it with:\n\n"
            "```\npython -m etl.pass_networks --match <whoscored_game_id>\n```\n\n"
            "Pre-built networks for this team will appear here automatically.",
            icon="🕸️",
        )
    else:
        pn = pnets[pnets["team"] == team]
        match_lbl = pn["match"].iloc[0] if "match" in pn.columns else ""
        nodes = pn[pn["kind"] == "node"].copy()
        edges = pn[pn["kind"] == "edge"].copy()
        st.pyplot(pass_network(nodes, edges, title=f"Pass network — {match_lbl}"))
        st.caption("Node = average pass position, size ∝ involvement; edge width ∝ pass volume "
                   "between teammates. Source: WhoScored/Opta events.")

st.divider()
st.caption("Shot & pressing data: Understat. Pass network: WhoScored/Opta (offline). "
           "Pass networks & defensive shape expand as more matches are scraped.")
