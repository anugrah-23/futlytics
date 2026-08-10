"""Team / Tactical Dashboard — the differentiator (Phase 3)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Team Dashboard", page_icon="📊", layout="wide")
st.title("📊 Team Dashboard")
st.info("Phase 3 — pass network, territory heatmap, pressing, defensive shape, shot map.")
