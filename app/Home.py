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
        "No dataset yet. Run the ETL to populate `data/processed/`:\n\n"
        "```\npython -m etl.poc_pull --write\n```",
        icon="🗂️",
    )
    st.stop()

st.success(f"Data last updated: {da.last_updated()}")

df = da.load("poc_player_stats")
if not df.empty:
    st.subheader("Proof-of-concept sample")
    st.dataframe(df.head(50), use_container_width=True)
