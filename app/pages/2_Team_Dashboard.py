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
import ui_theme  # noqa: E402
from teamnames import resolve_aliases  # noqa: E402
from viz.pitch import shot_map, shot_heatmap, pass_network, average_pass_network  # noqa: E402

st.set_page_config(page_title="Team Dashboard", layout="wide",
                   initial_sidebar_state="collapsed")
ui_theme.apply()
ui_theme.masthead(active="Team Dashboard")

LEAGUE_LABELS = {
    "ENG-Premier League": "Premier League", "ESP-La Liga": "La Liga",
    "ITA-Serie A": "Serie A", "GER-Bundesliga": "Bundesliga", "FRA-Ligue 1": "Ligue 1",
}

# Pass networks come from WhoScored, which names some clubs differently from the
# Understat-derived standings/selector ("Man Utd" vs "Manchester United",
# "Atletico" vs "Atletico Madrid", "PSG" vs "Paris Saint Germain"). Reconcile via
# the shared canonical-key matcher (teamnames.resolve_aliases).


@st.cache_data(show_spinner=False)
def _load():
    return (da.load("standings"), da.load("team_match"),
            da.load("shots"), da.load("pass_networks"))


standings, team_match, shots, pnets = _load()

if standings.empty:
    st.info("No team data yet. Build it with:\n\n```\npython -m etl.build_players --seasons 2425\n"
            "python -m etl.shots --seasons 2425\n```")
    st.stop()

# --- Filters (top bar) -------------------------------------------------------
seasons = sorted(standings["season"].unique(), reverse=True)
leagues = [l for l in LEAGUE_LABELS if l in set(standings["league"])]
nav = st.session_state.pop("nav_team", None)

fc1, fc2, fc3 = st.columns(3)
league = fc1.selectbox("League", leagues, format_func=lambda l: LEAGUE_LABELS.get(l, l),
                       key="flt_league_single")
season = fc2.selectbox("Season", seasons, format_func=lambda s: f"20{s[:2]}/{s[2:]}",
                       key="flt_season")

tbl = standings[(standings["season"] == season) & (standings["league"] == league)]
team_opts = tbl.sort_values("position")["team"].tolist()
if not team_opts:
    st.warning("No teams for this selection.")
    st.stop()
default_team = nav[2] if nav and nav[2] in team_opts else team_opts[0]
team = fc3.selectbox("Team", team_opts, index=team_opts.index(default_team))

trow = tbl[tbl["team"] == team].iloc[0]

# --- Team header -------------------------------------------------------------
ui_theme.context_header(
    f"{LEAGUE_LABELS.get(league, league)} · 20{season[:2]}/{season[2:]}", team)
ui_theme.kpi_row([
    {"label": "Position", "big": f"{int(trow['position'])}",
     "sub": f"{int(trow['W'])}-{int(trow['D'])}-{int(trow['L'])} record"},
    {"label": "Points", "big": f"{int(trow['Pts'])}", "tone": "amber",
     "sub": f"xPTS {trow['xPTS']:.0f}"},
    {"label": "Goals", "big": f"{int(trow['GF'])}–{int(trow['GA'])}",
     "sub": "for–against"},
    {"label": "xG · xGA", "big": f"{trow['xG']:.0f}", "tone": "cool",
     "sub": f"xGA {trow['xGA']:.0f} · xGD {trow['xGD']:+.1f}"},
])
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
    cols_ok = not pnets.empty and {"league", "season", "team", "kind"} <= set(pnets.columns)
    scope = (pnets[(pnets["league"] == league) & (pnets["season"] == season)]
             if cols_ok else pnets.iloc[0:0])
    pn_teams = resolve_aliases(team, set(scope["team"].astype(str))) if not scope.empty else set()
    pn = scope[scope["team"].astype(str).isin(pn_teams)] if pn_teams else scope.iloc[0:0]
    if pn.empty:
        st.info(
            "**No pass networks for this team & season yet.** They come from WhoScored "
            "event data (Selenium-scraped offline — the app never scrapes live), built by "
            "a resumable batch:\n\n"
            "```\npython -m etl.pass_networks --featured\n```\n\n"
            "Featured teams fill in season by season as the scrape progresses."
        )
    else:
        AVG = "Season average"
        match_opts = (pn[pn["kind"] == "node"][["game_id", "match"]]
                      .drop_duplicates().sort_values("match"))
        choice = st.selectbox(f"Match ({len(match_opts)} available)",
                              [AVG] + match_opts["match"].tolist(), key="pn_match_sel")

        if choice == AVG:
            nodes, edges, nmatch = average_pass_network(pn)
            st.pyplot(pass_network(
                nodes, edges,
                title=f"Average pass network — {team} · {nmatch} match{'es' if nmatch != 1 else ''}"))
            st.caption(
                f"Averaged across {nmatch} match{'es' if nmatch != 1 else ''} this season. Node = mean "
                "pass position (weighted by involvement), size ∝ involvement; edge = a passing link "
                "recurring in ≥40% of matches, width ∝ mean volume. Source: WhoScored/Opta events.")
        else:
            gid = match_opts.loc[match_opts["match"] == choice, "game_id"].iloc[0]
            one = pn[pn["game_id"] == gid]
            nodes = one[one["kind"] == "node"].copy()
            edges = one[one["kind"] == "edge"].copy()
            st.pyplot(pass_network(nodes, edges, title=f"Pass network — {choice}"))
            st.caption(
                "Single match. Node = average pass position, size ∝ involvement; edge width ∝ "
                "pass volume between teammates (min 3 passes). Source: WhoScored/Opta events.")

st.divider()
st.caption("Shot & pressing data: Understat. Pass network: WhoScored/Opta (offline). "
           "Pass networks & defensive shape expand as more matches are scraped.")
