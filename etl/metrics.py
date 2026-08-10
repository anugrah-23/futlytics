"""Concept -> metric registry: single source of truth for the Player Profile.

Metrics reference a flat column in the merged player frame (FBref columns keep
their data-stat name; Understat columns are prefixed ``us_``). Only
source-populated metrics are listed — FBref's advanced tables are blank at
source right now, so passing/carrying/pressing depth is intentionally absent
and xG/xA come from Understat.

kind:  count -> per-90 normalized before ranking
       rate  -> already a %/ratio, used as-is
       per90 -> already per-90 (e.g. GK GA/90), used as-is
       derived -> computed in build_players
invert=True flips the percentile so "more filled = better" always holds.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    concept: str
    col: str          # column in the merged frame (or "" for derived)
    kind: str = "count"
    invert: bool = False


OUTFIELD_METRICS: list[Metric] = [
    # Finishing — output vs expected
    Metric("goals", "Goals", "Finishing", "goals", "count"),
    Metric("np_goals", "Non-pen goals", "Finishing", "goals_pens", "count"),
    Metric("xg", "xG", "Finishing", "us_xg", "count"),
    Metric("npxg", "npxG", "Finishing", "us_np_xg", "count"),
    Metric("npxg_perf", "Non-pen goals − npxG", "Finishing", "", "derived"),
    Metric("shots", "Shots", "Finishing", "shots", "count"),
    Metric("sot_pct", "Shots on target %", "Finishing", "shots_on_target_pct", "rate"),
    Metric("g_per_sh", "Goals / shot", "Finishing", "goals_per_shot", "rate"),

    # Creativity — chance creation
    Metric("assists", "Assists", "Creativity", "assists", "count"),
    Metric("xa", "xA", "Creativity", "us_xa", "count"),
    Metric("key_passes", "Key passes", "Creativity", "us_key_passes", "count"),
    Metric("xg_chain", "xG chain", "Creativity", "us_xg_chain", "count"),
    Metric("xg_buildup", "xG buildup", "Creativity", "us_xg_buildup", "count"),
    Metric("crosses", "Crosses", "Creativity", "crosses", "count"),

    # Defending & discipline (light — FBref only serves these two def metrics)
    Metric("tackles_won", "Tackles won", "Defending & discipline", "tackles_won", "count"),
    Metric("interceptions", "Interceptions", "Defending & discipline", "interceptions", "count"),
    Metric("fouled", "Fouls drawn", "Defending & discipline", "fouled", "count"),
    Metric("fouls", "Fouls committed", "Defending & discipline", "fouls", "count", invert=True),
    Metric("offsides", "Offsides", "Defending & discipline", "offsides", "count", invert=True),
    Metric("yellows", "Yellow cards", "Defending & discipline", "cards_yellow", "count", invert=True),
]

GK_METRICS: list[Metric] = [
    Metric("gk_save_pct", "Save %", "Shot-stopping", "gk_save_pct", "rate"),
    Metric("gk_ga90", "Goals against /90", "Shot-stopping", "gk_goals_against_per90", "per90", invert=True),
    Metric("gk_sota", "Shots on target faced", "Shot-stopping", "gk_shots_on_target_against", "count"),
    Metric("gk_cs_pct", "Clean sheet %", "Reliability", "gk_clean_sheets_pct", "rate"),
    Metric("gk_saves", "Saves", "Reliability", "gk_saves", "count"),
    Metric("gk_pk_save_pct", "Penalty save %", "Reliability", "gk_pens_save_pct", "rate"),
]

OUTFIELD_CONCEPTS = ["Finishing", "Creativity", "Defending & discipline"]
GK_CONCEPTS = ["Shot-stopping", "Reliability"]
