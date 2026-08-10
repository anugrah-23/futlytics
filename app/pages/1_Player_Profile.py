"""Player Profile — Playerprint-equivalent percentile scouting view (Phase 1)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Player Profile", page_icon="👤", layout="wide")
st.title("👤 Player Profile")
st.info("Phase 1 — percentile pizza charts per concept group. Coming next.")
