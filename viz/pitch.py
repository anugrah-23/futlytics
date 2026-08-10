"""Shared mplsoccer pitch-plot builders for the Team Dashboard.

All pitch visuals share one style (orientation, line color, background) so the
eye doesn't re-orient between sections (design doc §3.3). Coordinates are Opta
0-100 (Understat/WhoScored scaled to match).
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mplsoccer import Pitch, VerticalPitch

PITCH_BG = "#0e1512"
LINE = "#5a6b63"
ACCENT = "#2ee6a6"      # "for" / positive
AGAINST = "#e8617d"     # "against" / opponent
MUTED = "#7f8c86"


def base_pitch() -> Pitch:
    """The single canonical full-pitch style used everywhere."""
    return Pitch(pitch_type="opta", pitch_color=PITCH_BG, line_color=LINE, linewidth=1)


def _vpitch(half: bool = True) -> VerticalPitch:
    return VerticalPitch(pitch_type="opta", half=half, pitch_color=PITCH_BG,
                         line_color=LINE, linewidth=1, pad_top=6)


def shot_map(shots: pd.DataFrame, against: bool = False, title: str = "") -> plt.Figure:
    """Half-pitch shot map: marker area ∝ xG, goals highlighted."""
    color = AGAINST if against else ACCENT
    pitch = _vpitch(half=True)
    fig, ax = pitch.draw(figsize=(5, 5.2))
    fig.set_facecolor(PITCH_BG)
    if not shots.empty:
        xg = shots["xg"].fillna(0).to_numpy()
        goals = shots["is_goal"].to_numpy()
        sizes = 120 * xg + 20
        # non-goals: hollow; goals: filled + edge
        pitch.scatter(shots.loc[~shots["is_goal"], "x"], shots.loc[~shots["is_goal"], "y"],
                      s=sizes[~goals], ax=ax, facecolor="none", edgecolor=color,
                      linewidth=1.2, alpha=0.7, zorder=2)
        pitch.scatter(shots.loc[shots["is_goal"], "x"], shots.loc[shots["is_goal"], "y"],
                      s=sizes[goals], ax=ax, facecolor=color, edgecolor="white",
                      linewidth=0.8, alpha=0.95, zorder=3, marker="*")
    ax.set_title(title, color="#e6efe9", fontsize=12, pad=8)
    return fig


def shot_heatmap(shots: pd.DataFrame, against: bool = False, title: str = "") -> plt.Figure:
    """Half-pitch KDE of shot locations — 'territory' of shots for/against."""
    cmap = "mako" if against else "viridis"
    pitch = _vpitch(half=True)
    fig, ax = pitch.draw(figsize=(5, 5.2))
    fig.set_facecolor(PITCH_BG)
    if len(shots) >= 5:
        pitch.kdeplot(shots["x"], shots["y"], ax=ax, fill=True, levels=60,
                      thresh=0.05, cmap=cmap, alpha=0.85, zorder=1)
    ax.set_title(title, color="#e6efe9", fontsize=12, pad=8)
    return fig


def pass_network(nodes: pd.DataFrame, edges: pd.DataFrame, title: str = "") -> plt.Figure:
    """Full-pitch pass network: node position = avg action location, node size ∝
    involvement, edge width ∝ pass volume between a pair (min threshold applied)."""
    pitch = base_pitch()
    fig, ax = pitch.draw(figsize=(7.5, 5))
    fig.set_facecolor(PITCH_BG)
    if not edges.empty:
        maxc = edges["count"].max()
        for e in edges.itertuples():
            pitch.lines(e.x, e.y, e.x_end, e.y_end, ax=ax, lw=0.5 + 4 * e.count / maxc,
                        color=ACCENT, alpha=0.25 + 0.5 * e.count / maxc, zorder=1)
    if not nodes.empty:
        s = 120 + 600 * (nodes["involvement"] / nodes["involvement"].max())
        pitch.scatter(nodes["x"], nodes["y"], s=s, ax=ax, color=ACCENT,
                      edgecolor=PITCH_BG, linewidth=1.5, zorder=2)
        for n in nodes.itertuples():
            ax.text(n.x, n.y - 3.2, str(n.label), color="#e6efe9", fontsize=7,
                    ha="center", va="top", zorder=3)
    ax.set_title(title, color="#e6efe9", fontsize=12, pad=8)
    return fig
