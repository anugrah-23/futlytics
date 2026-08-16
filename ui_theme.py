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

import html as _html
from urllib.parse import quote

import streamlit as st

# Google Fonts is reachable locally and on Streamlit Cloud (unlike the artifact
# sandbox), so an @import is the simplest cross-env delivery. One family only —
# Newsreader — used across the whole app.
_FONTS = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600;6..72,700&display=swap');"
)

# --- palettes -----------------------------------------------------------------
# Two moods sharing one editorial grammar: warm-ink (dark, the default, mirrors
# .streamlit/config.toml) and warm-paper (light). apply() injects whichever the
# ?theme= URL param selects, overriding the static config.toml at runtime so the
# whole surface — chrome, custom components and charts — switches together.
_DARK = dict(
    BG="#14130d", BG2="#100f09", SURFACE="#1c1a12", SURFACE2="#232014",
    LINE="rgba(255,248,225,.10)", LINE2="rgba(255,248,225,.055)",
    INK="#ede7d8", MUTED="#a89e88", FAINT="#6f685a",
    ACCENT="#5ac59a", ACCENT_HI="#2ee6a6",
    AMBER="#f2c14e", CORAL="#e8617d", COOL="#7db2c9",   # cool = "expected"/xG
    # Percentile grammar (kept identical to viz/ so chips match the charts).
    P_HI="#2ee6a6", P_MID="#f2c14e", P_LO="#e8617d",
    CHIP_HI="#8ff2cf", CHIP_MID="#f2d492", CHIP_LO="#f0a3b3",
    NAV_ACTIVE_TXT="#100f09",
)
_LIGHT = dict(
    BG="#f6f2e7", BG2="#efe9d9", SURFACE="#fdfbf4", SURFACE2="#f2ecdd",
    LINE="rgba(38,35,26,.14)", LINE2="rgba(38,35,26,.075)",
    INK="#2a2619", MUTED="#6f6857", FAINT="#9a9284",
    ACCENT="#2f9d73", ACCENT_HI="#1f9e75",
    AMBER="#b6851a", CORAL="#cf4f6b", COOL="#3f7f97",
    P_HI="#1f9e75", P_MID="#b6851a", P_LO="#cf4f6b",
    CHIP_HI="#0f6b4a", CHIP_MID="#7a5a10", CHIP_LO="#9e3049",
    NAV_ACTIVE_TXT="#fdfbf4",
)
_PALETTES = {"dark": _DARK, "light": _LIGHT}

# Back-compat module-level constants (dark values) for any importer.
globals().update(_DARK)

# App page routes for the masthead nav (Streamlit strips the number prefix).
_NAV = [
    ("Overview", "/"),
    ("Player Profile", "/Player_Profile"),
    ("Team Dashboard", "/Team_Dashboard"),
    ("Compare", "/Compare"),
]


def current_mode() -> str:
    """Active theme ('dark'|'light'). Read from the ?theme= URL param (so it
    survives the masthead's full-reload navigation) with a session_state
    fallback for in-session page switches; defaults to dark."""
    q = None
    try:
        q = st.query_params.get("theme")
    except Exception:
        q = None
    if q in ("light", "dark"):
        st.session_state["_theme"] = q
        return q
    return st.session_state.get("_theme", "dark")


def _build_css(p: dict) -> str:
    BG = p["BG"]; BG2 = p["BG2"]; SURFACE = p["SURFACE"]; SURFACE2 = p["SURFACE2"]
    LINE = p["LINE"]; LINE2 = p["LINE2"]
    INK = p["INK"]; MUTED = p["MUTED"]; FAINT = p["FAINT"]
    ACCENT = p["ACCENT"]; ACCENT_HI = p["ACCENT_HI"]
    AMBER = p["AMBER"]; CORAL = p["CORAL"]; COOL = p["COOL"]
    P_HI = p["P_HI"]; P_MID = p["P_MID"]; P_LO = p["P_LO"]
    CHIP_HI = p["CHIP_HI"]; CHIP_MID = p["CHIP_MID"]; CHIP_LO = p["CHIP_LO"]
    NAV_ACTIVE_TXT = p["NAV_ACTIVE_TXT"]
    return f"""
<style>
{_FONTS}

/* ---- runtime theme: override the static config.toml chrome so light/dark
       switches the whole Streamlit surface, not just our components ---- */
[data-testid="stAppViewContainer"], .stApp,
[data-testid="stAppViewContainer"] > .main {{ background:{BG} !important; }}
[data-testid="stHeader"] {{ background:{BG} !important; }}
[data-testid="stSidebar"] {{ background:{BG2} !important; }}
.stApp, .block-container {{ color:{INK}; }}
.block-container p, .block-container li,
[data-testid="stWidgetLabel"] label, [data-testid="stWidgetLabel"] p {{ color:{INK}; }}
/* ---- input widgets: selectbox / multiselect / text, closed + open ---- */
/* neutralise every inner surface first, then re-assert the control's ground */
[data-baseweb="select"] div, [data-baseweb="input"] div {{ background-color:transparent !important; }}
[data-baseweb="select"] > div:first-child,
[data-baseweb="input"] > div:first-child, [data-baseweb="base-input"] {{
    background:{SURFACE} !important; border-color:{LINE} !important;
}}
[data-baseweb="select"] div, [data-baseweb="select"] span, [data-baseweb="select"] input,
[data-baseweb="input"] input, [data-baseweb="base-input"] input {{ color:{INK} !important; }}
[data-baseweb="select"] svg {{ fill:{INK} !important; }}
/* open dropdown menu (rendered in a portal/popover) */
[data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"], [data-baseweb="menu"] ul,
ul[role="listbox"] {{ background:{SURFACE} !important; }}
[role="option"] {{ background:{SURFACE} !important; color:{INK} !important; }}
[role="option"]:hover, [role="option"][aria-selected="true"] {{ background:{SURFACE2} !important; }}
/* multiselect chips */
[data-baseweb="tag"] {{ background:{SURFACE2} !important; }}
[data-baseweb="tag"] span, [data-baseweb="tag"] div, [data-baseweb="tag"] svg {{ color:{INK} !important; fill:{INK} !important; }}
[data-testid="stDataFrame"], [data-testid="stTable"] {{ background:{SURFACE}; }}

/* ---- themed HTML tables (replace canvas st.dataframe in light mode) ---- */
.dtbl-wrap{{overflow-x:auto; margin:.25rem 0 .8rem; border:1px solid {LINE}; border-radius:10px;}}
.dtbl{{width:100%; border-collapse:collapse; font-size:.86rem; font-variant-numeric:tabular-nums;}}
.dtbl thead th{{background:{SURFACE2}; color:{MUTED}; font-weight:600; text-transform:uppercase;
    letter-spacing:.06em; font-size:.69rem; text-align:right; padding:8px 12px; border-bottom:1px solid {LINE};}}
.dtbl thead th:first-child{{text-align:left;}}
.dtbl tbody td{{color:{INK}; padding:7px 12px; border-top:1px solid {LINE2}; text-align:right; white-space:nowrap;}}
.dtbl tbody td:first-child{{text-align:left; font-weight:500;}}
.dtbl tbody tr:nth-child(even){{background:{SURFACE};}}
.dtbl tbody tr:hover{{background:{SURFACE2};}}

/* ---- interactive standings (clickable rows -> team dashboard) ---- */
.stand{{border:1px solid {LINE}; border-radius:10px; overflow:hidden; margin:.25rem 0 .8rem;}}
.stand .sthead, .stand a.strow{{align-items:center; gap:10px; padding:7px 12px;}}
.stand .sthead{{background:{SURFACE2}; color:{MUTED}; text-transform:uppercase;
    letter-spacing:.06em; font-size:.68rem; font-weight:600;}}
.stand a.strow{{color:{INK}; text-decoration:none; border-top:1px solid {LINE2};
    font-size:.86rem; font-variant-numeric:tabular-nums;}}
.stand a.strow:hover{{background:{SURFACE2};}}
.stand a.strow:hover .team{{color:{ACCENT_HI};}}
.stand .c{{text-align:right; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}}
.stand .c.team{{text-align:left; font-weight:500;}}
.stand .c.pos{{text-align:right; color:{FAINT};}}

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
.mast-nav a.active{{color:{NAV_ACTIVE_TXT}; background:{ACCENT}; font-weight:600;}}
.mast-nav a.theme-sw{{border:1px solid {LINE}; color:{INK}; margin-left:6px;}}
.mast-nav a.theme-sw:hover{{border-color:{ACCENT}; color:{ACCENT_HI}; background:transparent;}}

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
.pct-hi{{background:color-mix(in srgb,{P_HI} 15%,transparent); border-color:color-mix(in srgb,{P_HI} 32%,transparent); color:{CHIP_HI};}} .pct-hi b{{color:{P_HI};}}
.pct-mid{{background:color-mix(in srgb,{P_MID} 14%,transparent); border-color:color-mix(in srgb,{P_MID} 30%,transparent); color:{CHIP_MID};}} .pct-mid b{{color:{P_MID};}}
.pct-lo{{background:color-mix(in srgb,{P_LO} 13%,transparent); border-color:color-mix(in srgb,{P_LO} 28%,transparent); color:{CHIP_LO};}} .pct-lo b{{color:{P_LO};}}
</style>
"""


def apply() -> None:
    """Inject the shared theme CSS for the active mode and mirror it into the
    chart palettes. Call once per page after st.set_page_config()."""
    mode = current_mode()
    st.markdown(_build_css(_PALETTES[mode]), unsafe_allow_html=True)
    # Keep matplotlib/plotly charts in step with the chrome (built after apply()).
    try:
        from viz import radar, pitch
        radar.use_theme(mode == "light")
        pitch.use_theme(mode == "light")
    except Exception:
        pass


def masthead(active: str = "Overview") -> None:
    """Serif wordmark + tagline + page nav band, with a light/dark switch."""
    mode = current_mode()
    nav = "".join(
        f'<a class="{"active" if label == active else ""}" href="{href}?theme={mode}" '
        f'target="_self">{label}</a>'
        for label, href in _NAV
    )
    other = "dark" if mode == "light" else "light"
    sw_label = "☾ Dark" if mode == "light" else "☀ Light"
    # Query-only href flips ?theme on the current page (relative to current path),
    # so the switch works identically on every page.
    nav += (f'<a class="theme-sw" href="?theme={other}" target="_self" '
            f'title="Switch to {other} mode">{sw_label}</a>')
    st.markdown(
        '<div class="mast-app">'
        '<div class="mast-brand"><b>Futlytics</b>'
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
    correctly even across a full reload (data is in the URL, not just state).
    Also carries the active theme so the switch survives the reload."""
    return ("?lbp=" + quote(f"{league}|{season}|{team}|{player}")
            + f"&theme={current_mode()}")


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


def data_table(df) -> None:
    """Render a (already display-formatted) DataFrame as a themed HTML table.

    Used in place of st.dataframe for read-only tables so they follow the
    light/dark theme — the canvas-based st.dataframe grid ignores runtime CSS
    and stays dark in light mode. First column left-aligned, rest right."""
    cols = list(df.columns)
    head = "".join(f"<th>{_html.escape(str(c))}</th>" for c in cols)
    body = []
    for _, r in df.iterrows():
        cells = "".join(f"<td>{_html.escape('' if v is None else str(v))}</td>" for v in r)
        body.append(f"<tr>{cells}</tr>")
    st.markdown(
        f'<div class="dtbl-wrap"><table class="dtbl"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>',
        unsafe_allow_html=True,
    )


def standings_table(df, league: str, season: str, team_col: str = "team",
                    pos_col: str = "position") -> None:
    """Render league standings as a themed grid whose rows link to the team
    dashboard (?tbp=), replacing the canvas st.dataframe. df is display-ready."""
    cols = list(df.columns)
    ncols = len(cols)
    # position narrow, team flexible, the rest even.
    widths = []
    for c in cols:
        widths.append("34px" if c == pos_col else ("minmax(120px,1.5fr)" if c == team_col else "1fr"))
    tmpl = f"grid-template-columns:{' '.join(widths)};display:grid;"

    def _cls(c: str) -> str:
        return "c team" if c == team_col else ("c pos" if c == pos_col else "c")

    head = "".join(f'<span class="{_cls(c)}">{_html.escape(str(c))}</span>' for c in cols)
    rows = [f'<div class="sthead" style="{tmpl}">{head}</div>']
    mode = current_mode()
    for _, r in df.iterrows():
        team = str(r[team_col])
        href = "?tbp=" + quote(f"{league}|{season}|{team}") + f"&theme={mode}"
        cells = "".join(
            f'<span class="{_cls(c)}">{_html.escape("" if r[c] is None else str(r[c]))}</span>'
            for c in cols
        )
        rows.append(f'<a class="strow" style="{tmpl}" href="{href}" target="_self">{cells}</a>')
    st.markdown(f'<div class="stand">{"".join(rows)}</div>', unsafe_allow_html=True)


def consume_team_click() -> None:
    """If a standings row set ?tbp=..., navigate to that Team Dashboard.
    Call early in Home, before rendering (mirrors consume_leaderboard_click)."""
    key = st.query_params.get("tbp")
    if not key:
        return
    parts = key.split("|")
    if len(parts) == 3:
        st.session_state["nav_team"] = tuple(parts)
        st.query_params.clear()
        st.switch_page("pages/2_Team_Dashboard.py")


def pct_class(p: float) -> str:
    if p >= 66:
        return "pct-hi"
    if p >= 33:
        return "pct-mid"
    return "pct-lo"
