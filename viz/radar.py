"""Shared percentile radar / pizza chart builders (plotly).

One consistent visual grammar across player and team pages (design doc §1):
slices colored by percentile intensity on the single accent hue.
"""
from __future__ import annotations

import plotly.graph_objects as go

ACCENT = "#2ee6a6"        # "high percentile" accent (matches .streamlit theme)
LOW = "#3a4a44"           # low-percentile muted fill
BG = "#0e1512"


def _pct_to_color(pct: float) -> str:
    """Blend LOW->ACCENT by percentile so color pairs with the numeric label."""
    p = max(0.0, min(100.0, pct)) / 100.0
    lo = tuple(int(LOW[i:i + 2], 16) for i in (1, 3, 5))
    hi = tuple(int(ACCENT[i:i + 2], 16) for i in (1, 3, 5))
    rgb = tuple(round(lo[i] + (hi[i] - lo[i]) * p) for i in range(3))
    return f"rgb{rgb}"


def pizza(labels: list[str], percentiles: list[float], title: str = "") -> go.Figure:
    """Percentile pizza: one wedge per metric, colored by percentile intensity."""
    fig = go.Figure()
    fig.add_trace(
        go.Barpolar(
            r=percentiles,
            theta=labels,
            marker_color=[_pct_to_color(p) for p in percentiles],
            marker_line_color=BG,
            marker_line_width=2,
            hovertemplate="%{theta}: %{r:.0f}th pct<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor=BG,
        polar=dict(
            bgcolor=BG,
            radialaxis=dict(range=[0, 100], showticklabels=True, tickvals=[25, 50, 75, 100]),
            angularaxis=dict(direction="clockwise"),
        ),
        showlegend=False,
        margin=dict(l=60, r=60, t=60, b=40),
    )
    return fig
