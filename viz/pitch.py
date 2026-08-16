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
AMBER = "#f2c14e"       # secondary highlight (key passes etc.)
MUTED = "#7f8c86"
TITLE = "#e6efe9"       # plot title ink, flipped by use_theme()


def use_theme(light: bool) -> None:
    """Re-point the pitch palette at the light or dark mood. ui_theme.apply()
    calls this so pitch figures built afterwards match the page chrome."""
    global PITCH_BG, LINE, ACCENT, AGAINST, AMBER, TITLE
    if light:
        PITCH_BG, LINE, ACCENT = "#f3efe2", "#b9b09c", "#1f9e75"
        AGAINST, AMBER, TITLE = "#cf4f6b", "#b6851a", "#2a2619"
    else:
        PITCH_BG, LINE, ACCENT = "#0e1512", "#5a6b63", "#2ee6a6"
        AGAINST, AMBER, TITLE = "#e8617d", "#f2c14e", "#e6efe9"


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
    ax.set_title(title, color=TITLE, fontsize=12, pad=8)
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
    ax.set_title(title, color=TITLE, fontsize=12, pad=8)
    return fig


def average_pass_network(pn: pd.DataFrame, top_n: int = 11,
                         min_match_frac: float = 0.4, max_edges: int = 22
                         ) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Collapse a team's per-match pass networks into ONE season-average network.

    Nodes: each player's mean pitch position across matches, weighted by
    involvement (so a player's busier games count more), sized by mean
    involvement; the 11 most-featured players are kept.

    Edges: stored edge rows carry only coordinates (no player labels), so each
    endpoint is snapped to the nearest averaged node to recover the pair, then
    deduped within a match and averaged across matches. Only links that recur in
    at least ``min_match_frac`` of matches survive (denoises mis-snaps and
    one-off combinations) — the "averaging out" that a single-match overlay lacks.
    Prefers real labels when present (future data records them).

    Returns (nodes, edges, n_matches) ready for :func:`pass_network`.
    """
    empty = pd.DataFrame()
    nodes = pn[pn["kind"] == "node"].dropna(subset=["label", "x", "y"]).copy()
    if nodes.empty:
        return empty, empty, 0
    key = "game_id" if ("game_id" in pn.columns and pn["game_id"].notna().any()) else "match"
    n_matches = int(pn[key].nunique())

    def _wavg(v, w):
        v = np.asarray(v, float); w = np.asarray(w, float)
        return float(np.average(v, weights=w)) if w.sum() > 0 else float(v.mean())

    rows = [{"label": lab, "x": _wavg(g["x"], g["involvement"]),
             "y": _wavg(g["y"], g["involvement"]),
             "involvement": float(g["involvement"].mean()), "apps": int(g[key].nunique())}
            for lab, g in nodes.groupby("label")]
    nd = (pd.DataFrame(rows).sort_values(["apps", "involvement"], ascending=False)
          .head(top_n).reset_index(drop=True))
    keep = list(nd["label"])
    pos = nd.set_index("label")[["x", "y"]]

    ed = pd.DataFrame(columns=["x", "y", "x_end", "y_end", "count"])
    edges = pn[pn["kind"] == "edge"].dropna(subset=["x", "y", "x_end", "y_end", "count"]).copy()
    if not edges.empty:
        if "label" in edges.columns and "label_end" in edges.columns \
                and edges["label"].notna().all() and edges["label_end"].notna().all():
            e = edges[edges["label"].isin(keep) & edges["label_end"].isin(keep)].copy()
            a = e[["label", "label_end"]].min(axis=1)
            b = e[["label", "label_end"]].max(axis=1)
        else:
            kx = pos["x"].to_numpy(); ky = pos["y"].to_numpy(); klab = np.array(keep)

            def _near(px, py):
                d = (kx - px) ** 2 + (ky - py) ** 2
                i = int(d.argmin())
                return klab[i], float(d[i])

            aa, bb, ok = [], [], []
            for r in edges.itertuples():
                la, da = _near(r.x, r.y)
                lb, db = _near(r.x_end, r.y_end)
                aa.append(la); bb.append(lb)
                ok.append(da <= 400 and db <= 400 and la != lb)  # drop far snaps (>20 units)
            e = edges.assign(_a=aa, _b=bb)[ok]
            a = e[["_a", "_b"]].min(axis=1); b = e[["_a", "_b"]].max(axis=1)
        e = e.assign(a=a, b=b)
        # one value per (match, pair) so intra-match mis-snaps can't inflate volume
        if key in e.columns:
            e = e.groupby([key, "a", "b"], as_index=False)["count"].max()
        grp = (e.groupby(["a", "b"]).agg(count=("count", "mean"), pm=("count", "size"))
               .reset_index())
        thr = max(2, round(n_matches * min_match_frac)) if n_matches >= 4 else 1
        grp = grp[grp["pm"] >= thr].sort_values("count", ascending=False).head(max_edges)
        if not grp.empty:
            ed = pd.DataFrame({
                "x": grp["a"].map(pos["x"]).to_numpy(),
                "y": grp["a"].map(pos["y"]).to_numpy(),
                "x_end": grp["b"].map(pos["x"]).to_numpy(),
                "y_end": grp["b"].map(pos["y"]).to_numpy(),
                "count": grp["count"].to_numpy(),
            })
    return nd[["label", "x", "y", "involvement"]], ed, n_matches


def passing_map(passes: pd.DataFrame, title: str = "", color: str = ACCENT,
                show_incomplete: bool = True) -> plt.Figure:
    """Full-pitch passing map for one player: every pass drawn as an arrow from
    origin to destination. Completed passes in ``color``; incomplete (if shown)
    muted coral. Attacking left -> right (x toward 100), matching all pitch views.
    """
    pitch = base_pitch()
    fig, ax = pitch.draw(figsize=(7.5, 5))
    fig.set_facecolor(PITCH_BG)
    if not passes.empty:
        comp = passes[passes["outcome"] == 1]
        inc = passes[passes["outcome"] == 0]
        if show_incomplete and not inc.empty:
            pitch.arrows(inc["x"], inc["y"], inc["end_x"], inc["end_y"], ax=ax,
                         width=1.0, headwidth=4, headlength=4,
                         color=AGAINST, alpha=0.30, zorder=1)
        if not comp.empty:
            pitch.arrows(comp["x"], comp["y"], comp["end_x"], comp["end_y"], ax=ax,
                         width=1.3, headwidth=4.5, headlength=4.5,
                         color=color, alpha=0.55, zorder=2)
            pitch.scatter(comp["x"], comp["y"], s=8, ax=ax, color=color,
                          alpha=0.5, zorder=3)
    ax.set_title(title, color=TITLE, fontsize=12, pad=8)
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
            ax.text(n.x, n.y - 3.2, str(n.label), color=TITLE, fontsize=7,
                    ha="center", va="top", zorder=3)
    ax.set_title(title, color=TITLE, fontsize=12, pad=8)
    return fig
