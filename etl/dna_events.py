"""Raw WhoScored/Opta event parsing for the Player DNA feature.

The pass-network scrape already caches the full Opta event stream per featured
match under ``data/raw/soccerdata_cache/events/<league>_<season>/<game_id>.json``.
FBref's advanced tables are blank at source, so this raw feed is the *only*
place progression / carrying / passing-profile / aerial / defending detail lives
— but only for the featured clubs we scrape, so Player DNA is featured-club-only.

This module turns those JSONs into two tidy frames the DNA builder aggregates:
  events  — one row per on-ball event, with Opta qualifiers flattened to columns
            (pass end-coords, length, foot, cross/through-ball/long-ball flags…).
  meta    — one row per player-match: position group and minutes played.

Coordinate convention (WhoScored): x,y in 0-100, each team attacking toward
x=100, so higher x is always more advanced for that event's team — the same
convention viz/pass network code already relies on.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from etl.config import SOCCERDATA_CACHE

log = logging.getLogger("dna_events")

EVENTS_DIR = Path(SOCCERDATA_CACHE) / "events"

# Pitch bands (0-100). Final third starts at 2/3; half-spaces are the two
# inside channels either side of the central corridor.
FINAL_THIRD_X = 66.7
ATT_PEN_X = 83.0            # ~18-yard box edge on a 0-100 scale
HALFSPACE_Y = [(21.1, 36.8), (63.2, 78.9)]
CENTRAL_Y = (36.8, 63.2)

# WhoScored position codes -> the coarse groups the rest of the app ranks within
# (GK / DF / MF / FW), so DNA percentiles pool like-for-like.
_POS_PREFIX = [
    ("GK", "GK"),
    ("DM", "MF"), ("AM", "MF"), ("WB", "DF"),
    ("D", "DF"), ("M", "MF"), ("F", "FW"), ("A", "FW"),
]


def pos_group(code: str | float) -> str:
    if not isinstance(code, str) or not code:
        return "Unknown"
    c = code.strip().upper()
    for prefix, grp in _POS_PREFIX:
        if c.startswith(prefix):
            return grp
    return "Unknown"


SHOT_TYPES = {"Goal", "MissedShots", "SavedShot", "ShotOnPost"}


def _quals(ev: dict) -> dict[str, object]:
    """Flatten an event's qualifier list to {displayName: value}."""
    out: dict[str, object] = {}
    for q in ev.get("qualifiers", []):
        name = q.get("type", {}).get("displayName")
        if name is not None:
            out[name] = q.get("value")
    return out


def _fnum(v: object) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _foot(q: dict) -> str:
    if "RightFoot" in q:
        return "right"
    if "LeftFoot" in q:
        return "left"
    if "Head" in q or "HeadPass" in q:
        return "head"
    return "other"


def load_match(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse one cached match JSON into (events, meta) frames."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    game_id = int(Path(path).stem)
    names = {int(k): v for k, v in d.get("playerIdNameDictionary", {}).items()}
    team_of = {d["home"]["teamId"]: d["home"]["name"],
               d["away"]["teamId"]: d["away"]["name"]}
    match_len = float(d.get("expandedMaxMinute") or d.get("maxExpandedMinute") or 95)

    # --- per-player meta (position, minutes) ---
    meta_rows = []
    for side in ("home", "away"):
        team = d[side]["name"]
        for p in d[side].get("players", []):
            first = bool(p.get("isFirstEleven"))
            sub_in = p.get("subbedInExpandedMinute")
            sub_out = p.get("subbedOutExpandedMinute")
            if first:
                start = 0.0
            elif sub_in is not None:
                start = float(sub_in)
            else:
                continue  # unused sub — never took the field
            end = float(sub_out) if sub_out is not None else match_len
            minutes = max(0.0, end - start)
            pos = p.get("position", "")
            meta_rows.append({
                "game_id": game_id, "playerId": int(p["playerId"]),
                "player": p.get("name", names.get(int(p["playerId"]), "")),
                "team": team, "position": pos, "pos_group": pos_group(pos),
                "minutes": minutes,
            })
    meta = pd.DataFrame(meta_rows)

    # --- events (touches only; carry direction, qualifiers flattened) ---
    # Opta emits events in chronological order; keep a per-match sequence so the
    # DNA builder can derive carries / post-recovery links from adjacency.
    ev_rows = []
    for seq, e in enumerate(d.get("events", [])):
        pid = e.get("playerId")
        if pid is None:
            continue
        typ = e.get("type", {}).get("displayName", "")
        q = _quals(e)
        x, y = _fnum(e.get("x")), _fnum(e.get("y"))
        ev_rows.append({
            "game_id": game_id,
            "seq": seq,
            "teamId": e.get("teamId"),
            "team": team_of.get(e.get("teamId"), ""),
            "playerId": int(pid),
            "player": names.get(int(pid), ""),
            "type": typ,
            "outcome": 1 if e.get("outcomeType", {}).get("displayName") == "Successful" else 0,
            "is_touch": bool(e.get("isTouch")),
            "minute": e.get("expandedMinute", e.get("minute")),
            "x": x, "y": y,
            "end_x": _fnum(q.get("PassEndX")),
            "end_y": _fnum(q.get("PassEndY")),
            "length": _fnum(q.get("Length")),
            "angle": _fnum(q.get("Angle")),
            "foot": _foot(q),
            "is_cross": "Cross" in q,
            "is_throughball": "Throughball" in q or "ThroughBall" in q,
            "is_longball": "Longball" in q,
            "is_chipped": "Chipped" in q,
            "is_keypass": "KeyPass" in q,
            "is_headpass": "HeadPass" in q,
            "is_assist": "IntentionalGoalAssist" in q or "GoalAssist" in q,
            "is_shotassist": "ShotAssist" in q or "KeyPass" in q,
            "is_goal": typ == "Goal",
            "is_shot": typ in SHOT_TYPES,
            "gm_y": _fnum(q.get("GoalMouthY")),
            "gm_z": _fnum(q.get("GoalMouthZ")),
        })
    events = pd.DataFrame(ev_rows)
    return events, meta


def iter_matches(league: str, season: str):
    d = EVENTS_DIR / f"{league}_{season}"
    if not d.is_dir():
        return
    for fp in sorted(d.glob("*.json")):
        yield fp


def load_events(leagues: list[str], seasons: list[str]
                ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """All cached featured-match events + meta for the given league-seasons,
    tagged with league/season."""
    ev_frames, meta_frames = [], []
    for lg in leagues:
        for sn in seasons:
            n = 0
            for fp in iter_matches(lg, sn):
                try:
                    ev, meta = load_match(fp)
                except Exception as exc:
                    log.warning("skip %s: %s", fp.name, exc)
                    continue
                if ev.empty:
                    continue
                for f in (ev, meta):
                    f["league"], f["season"] = lg, sn
                ev_frames.append(ev)
                meta_frames.append(meta)
                n += 1
            if n:
                log.info("loaded %s %s: %d matches", lg, sn, n)
    if not ev_frames:
        return pd.DataFrame(), pd.DataFrame()
    return (pd.concat(ev_frames, ignore_index=True),
            pd.concat(meta_frames, ignore_index=True))
