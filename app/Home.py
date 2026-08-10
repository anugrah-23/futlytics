"""League Overview / landing page. Streamlit entrypoint (app/Home.py)."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable (data_access, viz, etl) when Streamlit
# runs this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

import data_access as da  # noqa: E402

st.set_page_config(page_title="Football Analytics", page_icon="⚽", layout="wide")

st.title("⚽ Football Analytics")
st.caption("Top-5 European league player & tactical analytics")

if not da.has_data():
    st.info(
        "No dataset yet. Build it with:\n\n"
        "```\npython -m etl.build_players --seasons 2425\n```",
        icon="🗂️",
    )
    st.stop()

players = da.load("players")
st.success(f"Data last updated: {da.last_updated('players')}")

col1, col2, col3 = st.columns(3)
col1.metric("Players", f"{len(players):,}")
col2.metric("Leagues", players["league"].nunique() if not players.empty else 0)
col3.metric("Seasons", players["season"].nunique() if not players.empty else 0)

st.divider()
st.subheader("Start here")
st.page_link("pages/1_Player_Profile.py", label="Player Profile — percentile scouting report", icon="👤")
st.page_link("pages/2_Team_Dashboard.py", label="Team Dashboard — tactical views (Phase 3)", icon="📊")
st.page_link("pages/3_Compare.py", label="Compare — players side by side (Phase 4)", icon="⚖️")

st.divider()
st.caption(
    "Player metrics combine FBref (goals, shots, discipline, defending, GK) with "
    "Understat (xG, xA, key passes). League tables & leaderboards arrive in Phase 2. "
    "xG/aerials unavailable from FBref directly — Understat fills the xG/xA gap."
)
