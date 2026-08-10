"""Shared mplsoccer pitch-plot builders for the team dashboard.

All pitch visuals share one style (orientation, line color, background) so the
eye doesn't re-orient between sections (design doc §3.3).
"""
from __future__ import annotations

from mplsoccer import Pitch

PITCH_BG = "#0e1512"
LINE = "#5a6b63"
ACCENT = "#2ee6a6"


def base_pitch() -> Pitch:
    """The single canonical pitch style used everywhere."""
    return Pitch(
        pitch_type="opta",           # WhoScored/Opta 0-100 coordinates
        pitch_color=PITCH_BG,
        line_color=LINE,
        linewidth=1,
    )
