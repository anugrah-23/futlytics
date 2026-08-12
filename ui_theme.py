"""Shared UI theme — 'Editorial' direction, medium restyle anchored on
The Analyst / StatsBomb.

Warm-ink ground + Newsreader serif used for *everything* (headings, body, data
— one typeface, the wordmark's), colors in .streamlit/config.toml, plus
structural components Streamlit can't express on its own: a masthead, KPI
stat-tiles, section headers with eyebrows, and leaderboard cards with value
bars. Call apply() once per page after st.set_page_config(); use the render
helpers where you want the components.
"""
from __future__ import annotations

from urllib.parse import quote

import streamlit as st

# Google Fonts is reachable locally and on Streamlit Cloud (unlike the artifact
# sandbox), so an @import is the simplest cross-env delivery. One family only —
# Newsreader — used across the whole app.
_FONTS = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600;6..72,700&display=swap');"
)

# --- palette (mirrors .streamlit/config.toml; extra tones for the components) --
BG = "#14130d"; BG2 = "#100f09"
SURFACE = "#1c1a12"; SURFACE2 = "#232014"
LINE = "rgba(255,248,225,.10)"; LINE2 = "rgba(255,248,225,.055)"
INK = "#ede7d8"; MUTED = "#a89e88"; FAINT = "#6f685a"
ACCENT = "#5ac59a"; ACCENT_HI = "#2ee6a6"
AMBER = "#f2c14e"; CORAL = "#e8617d"; COOL = "#7db2c9"   # cool = "expected"/xG

# Percentile grammar (kept identical to viz/ so chips match the charts).
P_HI, P_MID, P_LO = "#2ee6a6", "#f2c14e", "#e8617d"

# App page routes for the masthead nav (Streamlit strips the number prefix).
_NAV = [
    ("Overview", "/"),
    ("Player Profile", "/Player_Profile"),
    ("Team Dashboard", "/Team_Dashboard"),
    ("Compare", "/Compare"),
]

_CSS = f"""
<style>
{_FONTS}

/* one typeface everywhere — Newsreader (inheritance only, so icon fonts stay) */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{
    font-family:'Newsreader', Georgia, 'Times New Roman', serif;
}}
.stApp h1, .stApp h2, .stApp h3, .stApp h4,
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
    font-family:'Newsreader', Georgia, 'Times New Roman', serif !important;
    font-weight:600 !important; letter-spacing:-.008em; line-height:1.12; color:{INK};
}}
.block-container {{ padding-top:2.4rem; max-width:1180px; }}
[data-testid="stCaptionContainer"], .stCaption {{ color:{MUTED}; }}
hr, [data-testid="stDivider"] {{ border-color:{LINE}; }}
[data-testid="stDataFrame"] {{ margin:.25rem 0 .75rem; }}

/* ---- masthead ---- */
.mast-app{{
    display:flex; align-items:flex-end; justify-content:space-between; gap:22px;
    flex-wrap:wrap; padding:4px 0 18px; margin-bottom:6px;
    border-bottom:1px solid {LINE}; position:relative;
}}
.mast-app::after{{content:""; position:absolute; left:0; bottom:-1px; height:2px; width:240px;
    background:linear-gradient(90deg,{ACCENT},transparent);}}
.mast-brand b{{font-family:'Newsreader',serif; font-weight:600; font-size:1.5rem; display:block; line-height:1; color:{INK};}}
.mast-brand span{{color:{MUTED}; font-size:.8rem; margin-top:6px; display:block;}}
.mast-nav{{display:flex; gap:6px; flex-wrap:wrap;}}
.mast-nav a{{font-size:.85rem; color:{MUTED}; text-decoration:none; padding:7px 14px; border-radius:7px;}}
.mast-nav a:hover{{color:{INK}; background:{SURFACE};}}
.mast-nav a.active{{color:{BG2}; background:{ACCENT}; font-weight:600;}}

/* ---- context eyebrow + section headers ---- */
.eyebrow{{font-size:.71rem; font-weight:600; letter-spacing:.16em; text-transform:uppercase;
    color:{ACCENT}; margin:0 0 6px;}}
.sec-hd{{display:flex; align-items:baseline; justify-content:space-between; gap:16px; flex-wrap:wrap;
    padding-bottom:11px; margin:6px 0 18px; border-bottom:1px solid {LINE};}}
.sec-hd h2{{font-family:'Newsreader',serif; font-weight:600; font-size:1.5rem; margin:0; color:{INK};}}
.sec-note{{color:{MUTED}; font-size:.8rem; max-width:44ch; text-align:right;}}

/* ---- KPI tiles ---- */
.tiles{{display:grid; grid-template-columns:repeat(4,1fr); gap:13px; margin:4px 0 8px;}}
@media(max-width:820px){{.tiles{{grid-template-columns:repeat(2,1fr);}}}}
@media(max-width:460px){{.tiles{{grid-template-columns:1fr;}}}}
.tile{{background:{SURFACE}; border:1px solid {LINE}; border-radius:12px; padding:15px 17px; position:relative; overflow:hidden;}}
.tile::before{{content:""; position:absolute; left:0; top:14px; bottom:14px; width:3px; border-radius:3px; background:{ACCENT};}}
.tile.cool::before{{background:{COOL};}} .tile.amber::before{{background:{AMBER};}}
.tile .lab{{font-size:.68rem; letter-spacing:.13em; text-transform:uppercase; color:{MUTED}; margin:0 0 9px;}}
.tile .big{{font-family:'Newsreader',serif; font-size:1.42rem; line-height:1.05; margin:0; color:{INK};}}
.tile .sub{{font-size:.83rem; color:{MUTED}; margin:6px 0 0; font-variant-numeric:tabular-nums;}}
.tile .sub b{{color:{INK}; font-weight:600;}} .tile .sub b.up{{color:{ACCENT_HI};}}

/* ---- leaderboard cards with value bars ---- */
.leaders{{display:grid; grid-template-columns:repeat(3,1fr); gap:13px;}}
@media(max-width:820px){{.leaders{{grid-template-columns:1fr;}}}}
.board{{background:{SURFACE}; border:1px solid {LINE}; border-radius:12px; padding:15px 17px;}}
.board .bhd{{display:flex; align-items:baseline; justify-content:space-between; margin-bottom:4px;}}
.board .bhd h3{{font-family:'Newsreader',serif; font-weight:600; font-size:1.08rem; margin:0; color:{INK};}}
.board .bhd .unit{{font-size:.7rem; color:{MUTED}; text-transform:uppercase; letter-spacing:.1em;}}
.board ol{{list-style:none; margin:8px 0 0; padding:0; counter-reset:r;}}
.board li{{display:grid; grid-template-columns:16px 1fr auto; align-items:center; gap:10px;
    padding:8px 0; border-top:1px solid {LINE2};}}
.board li:first-child{{border-top:0;}}
.board li .rk{{color:{FAINT}; font-size:.78rem; font-variant-numeric:tabular-nums; text-align:right;}}
.board a.row{{display:contents; text-decoration:none; color:inherit;}}
.board a.row:hover .nm{{color:{ACCENT_HI};}}
.pl{{min-width:0;}}
.pl .nm{{font-weight:500; font-size:.88rem; color:{INK}; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}}
.pl .nm .tm{{color:{MUTED}; font-weight:400; font-size:.76rem;}}
.pl .track{{height:5px; border-radius:3px; background:{LINE}; margin-top:6px; overflow:hidden;}}
.pl .track i{{display:block; height:100%; background:{ACCENT}; border-radius:3px;}}
.board.cool .pl .track i{{background:{COOL};}} .board.amber .pl .track i{{background:{AMBER};}}
.val{{font-weight:700; font-variant-numeric:tabular-nums; color:{INK}; font-size:.92rem;}}

/* ---- percentile chips ---- */
.pct-chips{{display:flex; flex-wrap:wrap; gap:8px; margin:.25rem 0 .5rem;}}
.pct-chip{{display:inline-flex; align-items:baseline; gap:7px; padding:5px 12px; border-radius:999px; font-size:.82rem; border:1px solid transparent;}}
.pct-chip b{{font-weight:700; font-variant-numeric:tabular-nums;}}
.pct-hi{{background:color-mix(in srgb,{P_HI} 15%,transparent); border-color:color-mix(in srgb,{P_HI} 32%,transparent); color:#8ff2cf;}} .pct-hi b{{color:{P_HI};}}
.pct-mid{{background:color-mix(in srgb,{P_MID} 14%,transparent); border-color:color-mix(in srgb,{P_MID} 30%,transparent); color:#f2d492;}} .pct-mid b{{color:{P_MID};}}
.pct-lo{{background:color-mix(in srgb,{P_LO} 13%,transparent); border-color:color-mix(in srgb,{P_LO} 28%,transparent); color:#f0a3b3;}} .pct-lo b{{color:{P_LO};}}
</style>
"""


def apply() -> None:
    """Inject the shared theme CSS. Idempotent per page render."""
    st.markdown(_CSS, unsafe_allow_html=True)


def masthead(active: str = "Overview") -> None:
    """Serif wordmark + tagline + page nav band."""
    nav = "".join(
        f'<a class="{"active" if label == active else ""}" href="{href}" '
        f'target="_self">{label}</a>'
        for label, href in _NAV
    )
    st.markdown(
        '<div class="mast-app">'
        '<div class="mast-brand"><b>Football Analytics</b>'
        '<span>Top-5 European leagues — player &amp; tactical analytics</span></div>'
        f'<nav class="mast-nav">{nav}</nav>'
        '</div>',
        unsafe_allow_html=True,
    )


def section_header(eyebrow: str, title: str, note: str = "") -> None:
    note_html = f'<p class="sec-note">{note}</p>' if note else ""
    st.markdown(
        f'<div class="sec-hd"><div><p class="eyebrow">{eyebrow}</p>'
        f'<h2>{title}</h2></div>{note_html}</div>',
        unsafe_allow_html=True,
    )


def context_header(eyebrow: str, title: str) -> None:
    """Page-level eyebrow + serif headline (the block under the masthead)."""
    st.markdown(
        f'<p class="eyebrow">{eyebrow}</p>'
        f'<h1 style="font-size:clamp(1.8rem,4vw,2.6rem);margin:0;">{title}</h1>',
        unsafe_allow_html=True,
    )


def chip_strip(items: list[tuple[str, float]]) -> None:
    """Percentile chips in the shared color grammar. items: [(label, pct)]."""
    items = [(lab, p) for lab, p in items if p is not None and p == p]  # drop NaN
    if not items:
        return
    chips = "".join(
        f'<span class="pct-chip {pct_class(float(p))}">{lab} <b>{float(p):.0f}</b></span>'
        for lab, p in items
    )
    st.markdown(f'<div class="pct-chips">{chips}</div>', unsafe_allow_html=True)


def kpi_row(tiles: list[dict]) -> None:
    """tiles: list of {label, big, sub (html ok), tone in '', 'cool', 'amber'}."""
    cells = "".join(
        f'<div class="tile {t.get("tone", "")}">'
        f'<p class="lab">{t["label"]}</p>'
        f'<p class="big">{t["big"]}</p>'
        f'<p class="sub">{t.get("sub", "")}</p></div>'
        for t in tiles
    )
    st.markdown(f'<div class="tiles">{cells}</div>', unsafe_allow_html=True)


def _player_href(league: str, season: str, team: str, player: str) -> str:
    """Query-param link that carries the player identity, so a click navigates
    correctly even across a full reload (data is in the URL, not just state)."""
    return "?lbp=" + quote(f"{league}|{season}|{team}|{player}")


def leaders_grid(boards: list[dict]) -> None:
    """boards: list of {title, unit, tone, rows}. Each row:
    {nm, tm, val, frac (0-1 bar), league, season, team, player}."""
    cards = []
    for b in boards:
        items = []
        for r in b["rows"]:
            href = _player_href(r["league"], r["season"], r["team"], r["player"])
            items.append(
                f'<li><span class="rk">{len(items)+1}</span>'
                f'<a class="row" href="{href}" target="_self">'
                f'<span class="pl"><div class="nm">{r["nm"]}'
                f'<span class="tm"> · {r["tm"]}</span></div>'
                f'<div class="track"><i style="width:{r["frac"]*100:.0f}%"></i></div></span>'
                f'<span class="val">{r["val"]}</span></a></li>'
            )
        cards.append(
            f'<div class="board {b.get("tone", "")}">'
            f'<div class="bhd"><h3>{b["title"]}</h3><span class="unit">{b["unit"]}</span></div>'
            f'<ol>{"".join(items)}</ol></div>'
        )
    st.markdown(f'<div class="leaders">{"".join(cards)}</div>', unsafe_allow_html=True)


def consume_leaderboard_click() -> None:
    """If a leaderboard link set ?lbp=..., navigate to that Player Profile.
    Call early in Home, before rendering."""
    key = st.query_params.get("lbp")
    if not key:
        return
    parts = key.split("|")
    if len(parts) == 4:
        st.session_state["nav_player"] = tuple(parts)
        st.query_params.clear()
        st.switch_page("pages/1_Player_Profile.py")


def pct_class(p: float) -> str:
    if p >= 66:
        return "pct-hi"
    if p >= 33:
        return "pct-mid"
    return "pct-lo"
