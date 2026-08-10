"""Player Profile — Playerprint-equivalent percentile scouting view (Phase 1).

Percentile pizza chart per concept group + a per-90 stat table underneath,
computed against positional peers within the selected league(s) and season.
Low-minutes players are flagged and their charts degraded to plain tables.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import data_access as da  # noqa: E402
from viz.radar import pizza  # noqa: E402
from etl.metrics import OUTFIELD_CONCEPTS, GK_CONCEPTS  # noqa: E402

st.set_page_config(page_title="Player Profile", page_icon="👤", layout="wide")

LEAGUE_LABELS = {
    "ENG-Premier League": "Premier League",
    "ESP-La Liga": "La Liga",
    "ITA-Serie A": "Serie A",
    "GER-Bundesliga": "Bundesliga",
    "FRA-Ligue 1": "Ligue 1",
}


@st.cache_data(show_spinner=False)
def _load():
    return da.load("players"), da.load("player_metrics")


players, metrics = _load()

st.title("👤 Player Profile")

if players.empty or metrics.empty:
    st.info("No player data yet. Build it with:\n\n```\npython -m etl.build_players --seasons 2425\n```",
            icon="🗂️")
    st.stop()

# --- Filter bar (persists across pages via session_state) --------------------
seasons = sorted(players["season"].unique(), reverse=True)
leagues = list(LEAGUE_LABELS.keys())

with st.sidebar:
    st.header("Filters")
    season = st.selectbox("Season", seasons,
                          format_func=lambda s: f"20{s[:2]}/{s[2:]}",
                          key="flt_season")
    picked_leagues = st.multiselect("League(s)", leagues,
                                    default=leagues,
                                    format_func=lambda l: LEAGUE_LABELS.get(l, l),
                                    key="flt_leagues")
    st.caption("Percentiles are computed within the selected league(s) & season, "
               "against players in the same position group.")

pool = players[(players["season"] == season) & (players["league"].isin(picked_leagues))]
if pool.empty:
    st.warning("No players for that league/season selection.")
    st.stop()

# --- Player search / select --------------------------------------------------
pool = pool.sort_values("player")
labels = {
    f"{r.player} — {r.team} ({r.pos})": (r.league, r.season, r.team, r.player)
    for r in pool.itertuples()
}
choice = st.selectbox("Search player", list(labels.keys()),
                      index=None, placeholder="Type a name…")
if not choice:
    st.caption("Pick a player to see their percentile scouting report.")
    st.stop()

lg, sn, tm, pl = labels[choice]
prow = pool[(pool["league"] == lg) & (pool["team"] == tm) & (pool["player"] == pl)].iloc[0]
pm = metrics[(metrics["league"] == lg) & (metrics["season"] == sn)
             & (metrics["team"] == tm) & (metrics["player"] == pl)]

is_gk = prow["pos_group"] == "GK"
concepts = GK_CONCEPTS if is_gk else OUTFIELD_CONCEPTS

# --- Header band -------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Player", prow["player"])
c2.metric("Team", prow["team"])
c3.metric("Position", prow["pos"])
c4.metric("Age", "—" if pd.isna(prow["age"]) else int(prow["age"]))
c5.metric("Minutes", "—" if pd.isna(prow["minutes"]) else int(prow["minutes"]))
st.caption(f"{LEAGUE_LABELS.get(lg, lg)} · 20{sn[:2]}/{sn[2:]} · {prow['nation']}")

limited = bool(prow["limited_sample"])
if limited:
    st.warning(
        "⚠️ **Limited sample** — under 450 minutes played. Percentiles are "
        "unreliable at this sample size, so the charts are hidden and only raw "
        "per-90 values are shown.",
        icon="⚠️",
    )

st.markdown(
    "**How to read this:** each wedge is a percentile (0–100) vs positional peers — "
    "a fuller, greener wedge means the player ranks higher. Numbers are per-90 unless "
    "marked % or /90."
)
st.divider()


def _fmt(unit: str, value: float) -> str:
    if pd.isna(value):
        return "—"
    if unit == "%":
        return f"{value:.1f}%"
    return f"{value:.2f}"


# --- Concept sections --------------------------------------------------------
for concept in concepts:
    block = pm[pm["concept"] == concept].copy()
    if block.empty:
        continue
    st.subheader(concept)
    left, right = st.columns([1, 1])

    with right:
        tbl = block[["label", "value", "unit", "percentile"]].rename(
            columns={"label": "Metric", "value": "Per-90 / value",
                     "unit": "Unit", "percentile": "Pctl"}
        )
        tbl["Per-90 / value"] = [
            _fmt(u, v) for u, v in zip(block["unit"], block["value"])
        ]
        tbl["Pctl"] = tbl["Pctl"].map(lambda p: "—" if pd.isna(p) else f"{p:.0f}")
        st.dataframe(tbl[["Metric", "Per-90 / value", "Pctl"]],
                     hide_index=True, width="stretch")

    with left:
        charted = block.dropna(subset=["percentile"])
        if limited or charted.empty:
            st.caption("Percentile chart hidden (limited sample or unavailable).")
        else:
            fig = pizza(charted["label"].tolist(),
                        charted["percentile"].tolist(),
                        title=concept)
            st.plotly_chart(fig, width="stretch")
    st.divider()

st.caption(f"Data last updated: {da.last_updated('players')} · "
           "xG & aerial duels unavailable from source (FBref).")
