"""Reconcile team names across data sources.

Standings come from Understat ("Manchester United", "Atletico Madrid") while
pass networks come from WhoScored ("Man Utd", "Atletico"). The Team Dashboard
picks a team from the standings and needs the matching pass-network rows, so we
canonicalise both names to a common key and match on that.
"""
from __future__ import annotations

import re
import unicodedata

# Whole-name aliases (folded, matched before tokenising) for abbreviations that
# must not bleed onto a similarly-named different club (e.g. "PSG" -> Paris
# Saint-Germain, which must NOT catch "Paris FC").
_NAME_ALIAS = {"psg": "paris saint germain"}
# Token-level aliases that differ between the two conventions.
_ALIAS = {"utd": "united", "man": "manchester"}
# Corporate/filler tokens one source keeps and the other drops. Removed only
# when other tokens remain, so a name never collapses to nothing.
_DROP = {
    "fc", "cf", "afc", "ac", "as", "ss", "ssc", "sc", "rc", "rcd", "cd", "ca",
    "ud", "de", "club", "us", "ogc", "ol", "losc", "aj", "sm", "sv", "fsv",
    "vfl", "vfb", "tsg", "bsc", "borussia", "deportivo", "real",
}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def canonical_key(name: str) -> str:
    """Order-independent, source-agnostic key for a club name."""
    folded = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", _fold(name))).strip()
    folded = _NAME_ALIAS.get(folded, folded)
    toks = [_ALIAS.get(t, t) for t in folded.split()]
    core = [t for t in toks if t not in _DROP]
    return "".join(sorted(core)) or "".join(sorted(toks))


def resolve_aliases(target: str, candidates) -> set[str]:
    """Subset of ``candidates`` (e.g. pass-network team names) that refer to the
    same club as ``target`` (a standings name). Exact key match first, then a
    conservative substring match (>=4 chars, unambiguous)."""
    tk = canonical_key(target)
    cand = list(dict.fromkeys(str(c) for c in candidates))
    exact = {c for c in cand if canonical_key(c) == tk}
    if exact:
        return exact
    # Prefix (not substring) match on the sorted key: catches a dropped suffix
    # word — "Newcastle" vs "Newcastle United", "Atletico" vs "Atletico Madrid"
    # — while rejecting a mid-string coincidence like "paris" inside
    # "germainparissaint" (Paris FC vs Paris Saint-Germain). Only when unambiguous.
    if len(tk) >= 4:
        pre = {c for c in cand
               if (ck := canonical_key(c)) and len(ck) >= 4
               and (ck.startswith(tk) or tk.startswith(ck))}
        if len(pre) == 1:
            return pre
    return set()
