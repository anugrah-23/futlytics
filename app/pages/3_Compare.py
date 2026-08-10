"""Compare — 2-3 players or 2 teams side by side (Phase 4)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Compare", page_icon="⚖️", layout="wide")
st.title("⚖️ Compare")
st.info("Phase 4 — overlaid percentile radars + stat-difference table.")
