"""Runtime patch for a soccerdata Understat bug.

For some matches understat.com returns ``data['rosters']['h'|'a']`` as a LIST
of player objects instead of the usual ``{player_id: player}`` dict, so
soccerdata's ``next(iter(roster.values()))`` (team-id lookup) and
``team_roster.values()`` (player map) raise ``'list' object has no attribute
'values'`` and the whole league-season fetch dies. This bites Bundesliga in
particular. We reimplement ``Understat._read_match`` to normalize both team
rosters to dicts first; everything downstream then works unchanged.

Idempotent: call ``apply_patch()`` before any Understat read.
"""
from __future__ import annotations

import json
import logging
import time

from soccerdata.understat import UNDERSTAT_URL, Understat

log = logging.getLogger("understat_patch")


def _as_dict(team_roster: object) -> dict:
    """A team's roster as a {key: player} dict, whether it arrived as dict or list."""
    if isinstance(team_roster, dict):
        return team_roster
    if isinstance(team_roster, list):
        return {str(p.get("id", i)): p for i, p in enumerate(team_roster)}
    return {}


def _first_team_id(roster: dict) -> object:
    """team_id from the first player, or -1 if the roster is empty/odd.
    (team_id isn't in our output; this only needs to not crash and to stay
    consistent so the shot parser's name->id map resolves.)"""
    for player in roster.values():
        tid = player.get("team_id")
        if tid is not None:
            return tid
    return -1


def _patched_read_match(self, url: str, match_id: int, tries: int = 5) -> dict | None:
    """Fetch one match, normalizing list-rosters. Retries the SINGLE match on a
    dropped connection (understat.com intermittently forcibly closes the tls
    connection) so one drop skips at most this match instead of aborting the
    whole season fetch; returns None if it still won't load after ``tries``."""
    self._ensure_cookies()
    api_url = UNDERSTAT_URL + f"/getMatchData/{match_id}"
    filepath = self.data_dir / f"match_{match_id}.json"
    last: Exception | None = None
    for i in range(tries):
        try:
            reader = self._request_api(api_url, filepath)
            data = json.load(reader)

            home_team_name = self._extract_team_name(data["tmpl"]["home"])
            away_team_name = self._extract_team_name(data["tmpl"]["away"])
            raw = data["rosters"] if isinstance(data.get("rosters"), dict) else {}
            rosters = {"h": _as_dict(raw.get("h", {})), "a": _as_dict(raw.get("a", {}))}
            match_info = {"h": _first_team_id(rosters["h"]), "a": _first_team_id(rosters["a"]),
                          "team_h": home_team_name, "team_a": away_team_name}
            return {"match_info": match_info, "rostersData": rosters,
                    "shotsData": data["shots"]}
        except Exception as exc:  # tls "forcibly closed", HTTP 5xx, parse hiccups
            last = exc
            time.sleep(min(2.0 * (i + 1), 15.0))
    log.warning("match %s skipped after %d tries: %s", match_id, tries, last)
    return None


_applied = False


def apply_patch() -> None:
    """Rebind Understat._read_match to the roster-normalizing version (once)."""
    global _applied
    if not _applied:
        Understat._read_match = _patched_read_match
        _applied = True
