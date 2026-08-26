"""Player Profile — Playerprint-equivalent percentile scouting view (Phase 1).

Percentile pizza chart per concept group + a per-90 stat table underneath,
computed against positional peers within the selected league(s) and season.
Low-minutes players are flagged and their charts degraded to plain tables.
"""
from __future__ import annotations

import re
import sys
import unicodedata as _ud
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import data_access as da  # noqa: E402
import ui_theme  # noqa: E402
from viz.radar import pizza, dna_fingerprint  # noqa: E402
import viz.pitch as _vp  # noqa: E402  (theme-aware colors)
from viz.pitch import passing_map  # noqa: E402
from etl.metrics import OUTFIELD_CONCEPTS, GK_CONCEPTS  # noqa: E402
from etl.dna_metrics import CONCEPTS as DNA_CONCEPTS, CATEGORIES as DNA_CATEGORIES, CONCEPT_PARAMS  # noqa: E402

st.set_page_config(page_title="Player Profile", layout="wide",
                   initial_sidebar_state="collapsed")
ui_theme.apply()
ui_theme.masthead(active="Player Profile")

LEAGUE_LABELS = {
    "ENG-Premier League": "Premier League",
    "ESP-La Liga": "La Liga",
    "ITA-Serie A": "Serie A",
    "GER-Bundesliga": "Bundesliga",
    "FRA-Ligue 1": "Ligue 1",
}


@st.cache_data(show_spinner=False)
def _load():
    return (da.load("players"), da.load("player_metrics"),
            da.load("player_dna"), da.load("player_passes"))


players, metrics, dna_all, passes_all = _load()

if players.empty or metrics.empty:
    st.info("No player data yet. Build it with:\n\n```\npython -m etl.build_players --seasons 2425\n```")
    st.stop()


def _dna_norm(s: str) -> str:
    nfkd = _ud.normalize("NFKD", str(s))
    return "".join(c for c in nfkd if not _ud.combining(c)).lower().strip()


# --- Filters (top bar; state persists across pages) --------------------------
# Season list = seasons with FBref percentile profiles (player_metrics) PLUS any
# season that only has event-derived Player DNA. A just-started season (FBref
# still CAPTCHA-gated) shows here off its DNA alone; for such a season the player
# pool is narrowed to players who actually have DNA, so the search isn't full of
# hollow entries. Well-formed codes only, newest-first (default = latest season).
_metric_seasons = set(metrics["season"].astype(str))
_dna_seasons = set(dna_all["season"].astype(str)) if not dna_all.empty else set()
seasons = sorted((s for s in (_metric_seasons | _dna_seasons) if re.fullmatch(r"\d{4}", s)),
                 reverse=True)
leagues = list(LEAGUE_LABELS.keys())

fc1, fc2 = st.columns([1, 2])
season = fc1.selectbox("Season", seasons,
                       format_func=lambda s: f"20{s[:2]}/{s[2:]}",
                       key="flt_season")
picked_leagues = fc2.multiselect("League(s)", leagues, default=leagues,
                                 format_func=lambda l: LEAGUE_LABELS.get(l, l),
                                 key="flt_leagues")

pool = players[(players["season"] == season) & (players["league"].isin(picked_leagues))]
if season not in _metric_seasons and not dna_all.empty:
    # DNA-only season (e.g. the live season before FBref lands): keep only the
    # featured-club players who have event-derived analytics to show.
    _ds = dna_all[dna_all["season"].astype(str) == season]
    _dkeys = set(zip(_ds["league"].astype(str), _ds["nkey"].astype(str)))
    pool = pool[[(lg, _dna_norm(p)) in _dkeys
                 for lg, p in zip(pool["league"].astype(str), pool["player"])]]
if pool.empty:
    st.warning("No players for that league/season selection.")
    st.stop()

# --- Player search / select --------------------------------------------------
pool = pool.sort_values("player")
labels = {
    f"{r.player} — {r.team} ({r.pos})": (r.league, r.season, r.team, r.player)
    for r in pool.itertuples()
}
# Preselect a player arrived-at via a League Overview leaderboard click.
default_idx = None
if "nav_player" in st.session_state:
    target = st.session_state.pop("nav_player")
    for i, tup in enumerate(labels.values()):
        if tup == tuple(target):
            default_idx = i
            break

choice = st.selectbox("Search player", list(labels.keys()),
                      index=default_idx, placeholder="Type a name…")
if not choice:
    st.caption("Pick a player to see their percentile scouting report.")
    st.stop()

lg, sn, tm, pl = labels[choice]
prow = pool[(pool["league"] == lg) & (pool["team"] == tm) & (pool["player"] == pl)].iloc[0]
pm = metrics[(metrics["league"] == lg) & (metrics["season"] == sn)
             & (metrics["team"] == tm) & (metrics["player"] == pl)]

is_gk = prow["pos_group"] == "GK"
concepts = GK_CONCEPTS if is_gk else OUTFIELD_CONCEPTS

# --- Player header -----------------------------------------------------------
ui_theme.context_header(
    f"{LEAGUE_LABELS.get(lg, lg)} · 20{sn[:2]}/{sn[2:]} · {prow['nation']}",
    prow["player"])
ui_theme.kpi_row([
    {"label": "Team", "big": prow["team"]},
    {"label": "Position", "big": prow["pos"]},
    {"label": "Age", "big": "—" if pd.isna(prow["age"]) else int(prow["age"]), "tone": "cool"},
    {"label": "Minutes", "big": "—" if pd.isna(prow["minutes"]) else int(prow["minutes"]),
     "tone": "amber"},
])

limited = bool(prow["limited_sample"])
if limited:
    st.warning("**Limited sample** — under 450 minutes played. Percentiles are "
               "unreliable at this sample size, so the charts are hidden and only raw "
               "per-90 values are shown.")
else:
    strengths = (pm.dropna(subset=["percentile"])
                 .sort_values("percentile", ascending=False).head(6))
    if not strengths.empty:
        st.markdown('<p class="eyebrow" style="margin-top:14px">Strengths · percentile vs peers</p>',
                    unsafe_allow_html=True)
        ui_theme.chip_strip(list(zip(strengths["label"], strengths["percentile"])))

# --- Player DNA (event-derived from Opta/WhoScored; featured clubs only) ------
def _fmt_dna(unit: str, v: float) -> str:
    if pd.isna(v):
        return "—"
    return f"{v:.1f}%" if unit == "%" else f"{v:.2f}"


dna = dna_all.iloc[0:0]
if not dna_all.empty:
    dna = dna_all[(dna_all["league"] == lg) & (dna_all["season"] == sn)
                  & (dna_all["nkey"] == _dna_norm(pl))]
    if dna["playerId"].nunique() > 1:  # same normalized name -> take most-played
        best = dna.groupby("playerId")["minutes"].first().idxmax()
        dna = dna[dna["playerId"] == best]

if not dna.empty and dna["percentile"].notna().any():
    ui_theme.section_header(
        "Fingerprint · event data", "Player DNA",
        "Derived from Opta/WhoScored event data — available for featured clubs. "
        "Ranked vs other featured-club players in the same position.")
    pmap = {k: v for k, v in zip(dna["param_key"], dna["percentile"])}
    cats, scores = [], []
    for cat, keys in DNA_CATEGORIES.items():
        vals = [pmap[k] for k in keys if k in pmap and pd.notna(pmap[k])]
        if vals:
            cats.append(cat)
            scores.append(sum(vals) / len(vals))
    fp_l, fp_r = st.columns([3, 2])
    if not limited and len(cats) >= 3:
        with fp_l:
            st.plotly_chart(dna_fingerprint(cats, scores, title="DNA fingerprint"),
                            theme=None, width="stretch")
        with fp_r:
            st.markdown('<p class="eyebrow" style="margin-top:8px">Category index · '
                        'percentile</p>', unsafe_allow_html=True)
            ui_theme.chip_strip(sorted(zip(cats, scores), key=lambda t: -t[1]))
    else:
        st.caption("Fingerprint hidden (limited sample). Per-concept values below.")

    # Passing map (season) — every pass by this player, filterable by type.
    pmap_rows = passes_all.iloc[0:0]
    if not passes_all.empty:
        pmap_rows = passes_all[(passes_all["league"] == lg) & (passes_all["season"] == sn)
                               & (passes_all["nkey"] == _dna_norm(pl))]
    if not pmap_rows.empty:
        st.markdown('<p class="eyebrow" style="margin-top:18px">Passing map · season</p>',
                    unsafe_allow_html=True)
        VIEWS = {"All passes": None, "Progressive": "prog",
                 "Into final third": "final_third", "Key passes & assists": "key",
                 "Crosses": "cross"}
        mc1, mc2 = st.columns([1, 3])
        view = mc1.radio("Show", list(VIEWS.keys()), key="pmap_view")
        show_inc = mc1.checkbox("Include incomplete", value=(view == "All passes"))
        col = VIEWS[view]
        if col is None:
            sub, color = pmap_rows, _vp.ACCENT
        elif col == "key":
            sub = pmap_rows[(pmap_rows["keypass"] == 1) | (pmap_rows["assist"] == 1)]
            color = _vp.AMBER
        else:
            sub, color = pmap_rows[pmap_rows[col] == 1], _vp.ACCENT
        with mc2:
            st.pyplot(passing_map(sub, title=f"{pl} — {view.lower()}",
                                  color=color, show_incomplete=show_inc))
            tot = len(sub)
            comp = int((sub["outcome"] == 1).sum())
            pct = f"{100 * comp / tot:.0f}%" if tot else "—"
            st.caption(f"{tot} passes · {pct} completed · attacking left → right. "
                       "Green = completed, red = incomplete. Source: WhoScored/Opta events.")

    st.markdown('<p class="eyebrow" style="margin-top:18px">Concepts · parameters</p>',
                unsafe_allow_html=True)
    for i, concept in enumerate(DNA_CONCEPTS):
        block = dna[dna["concept"] == concept].copy()
        if block.empty:
            continue
        charted = block.dropna(subset=["percentile"])
        with st.expander(concept, expanded=(i == 0)):
            cl, cr = st.columns([1, 1])
            with cr:
                tb = pd.DataFrame({
                    "Parameter": block["label"],
                    "Value": [_fmt_dna(u, v) for u, v in zip(block["unit"], block["value"])],
                    "Pctl": [("—" if pd.isna(p) else f"{p:.0f}") for p in block["percentile"]],
                })
                ui_theme.data_table(tb)
            with cl:
                if limited or charted.empty:
                    st.caption("Percentile chart hidden (limited sample).")
                else:
                    st.plotly_chart(
                        pizza(charted["label"].tolist(),
                              charted["percentile"].tolist(), title=concept),
                        theme=None, width="stretch")
    st.divider()

# --- Scouting profile (season aggregates: FBref + Understat) ------------------
ui_theme.section_header("Season aggregates", "Scouting Profile",
                        "Finishing, creativity & discipline from FBref + Understat.")
if pm.empty:
    # DNA-only season: FBref hasn't published this season yet (CAPTCHA-gated).
    st.info("The FBref percentile scouting profile for this season isn't available "
            "yet — FBref is still publishing 2026/27. The event-derived **Player "
            "DNA** and **passing map** above are the live analytics for now; the "
            "full percentile profile fills in automatically once FBref catches up.")
else:
    st.caption("Each wedge is a percentile (0–100) vs positional peers — a fuller, greener wedge "
               "ranks higher. Numbers are per-90 unless marked % or /90.")
st.divider()


def _fmt(unit: str, value: float) -> str:
    if pd.isna(value):
        return "—"
    if unit == "%":
        return f"{value:.1f}%"
    return f"{value:.2f}"


# --- Concept sections --------------------------------------------------------
for concept in concepts:
    block = pm[pm["concept"] == concept].copy()
    if block.empty:
        continue
    st.subheader(concept)
    left, right = st.columns([1, 1])

    with right:
        tbl = block[["label", "value", "unit", "percentile"]].rename(
            columns={"label": "Metric", "value": "Per-90 / value",
                     "unit": "Unit", "percentile": "Pctl"}
        )
        tbl["Per-90 / value"] = [
            _fmt(u, v) for u, v in zip(block["unit"], block["value"])
        ]
        tbl["Pctl"] = tbl["Pctl"].map(lambda p: "—" if pd.isna(p) else f"{p:.0f}")
        ui_theme.data_table(tbl[["Metric", "Per-90 / value", "Pctl"]])

    with left:
        charted = block.dropna(subset=["percentile"])
        if limited or charted.empty:
            st.caption("Percentile chart hidden (limited sample or unavailable).")
        else:
            fig = pizza(charted["label"].tolist(),
                        charted["percentile"].tolist(),
                        title=concept)
            st.plotly_chart(fig, theme=None, width="stretch")
    st.divider()

st.caption(f"Data last updated: {da.last_updated('players')} · "
           "xG & aerial duels unavailable from source (FBref).")
