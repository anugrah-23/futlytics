"""Transform raw FBref stats into per-90 and percentile tables.

These are the numbers the product's credibility rests on (tech spec §8),
so the logic here is deliberately small, explicit, and unit-tested.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Minimum minutes to receive percentile ranks; below this a player is flagged
# "limited sample" and shown raw stats only (PRD §7.2, design doc §5).
MIN_MINUTES_DEFAULT = 450  # ~5 full matches

# Coarse position groups: percentiles are computed *within* a group so a
# centre-back isn't ranked against a striker on shots.
POSITION_GROUPS = {
    "GK": "Goalkeeper",
    "DF": "Defender",
    "MF": "Midfielder",
    "FW": "Forward",
}


def primary_position_group(pos: str | float) -> str:
    """Map an FBref position string (e.g. 'DF,MF') to one coarse group."""
    if not isinstance(pos, str) or not pos:
        return "Unknown"
    first = pos.split(",")[0].strip().upper()
    # FBref uses two-letter codes; take the leading DF/MF/FW/GK token.
    for code, _label in POSITION_GROUPS.items():
        if first.startswith(code):
            return code
    return "Unknown"


def per90(counting_stat: pd.Series, minutes: pd.Series) -> pd.Series:
    """Normalize a counting stat to per-90. Zero minutes -> NaN (not inf)."""
    mins = minutes.replace(0, np.nan)
    return counting_stat / (mins / 90.0)


def percentile_within_group(
    values: pd.Series,
    groups: pd.Series,
    minutes: pd.Series,
    min_minutes: int = MIN_MINUTES_DEFAULT,
) -> pd.Series:
    """Percentile rank (0-100) of each value within its position group.

    Only players at/above min_minutes are ranked *and* used as the comparison
    pool, so low-sample players neither get a misleading rank nor distort peers.
    """
    eligible = minutes >= min_minutes
    out = pd.Series(np.nan, index=values.index, dtype="float64")
    for grp, idx in groups[eligible].groupby(groups[eligible]).groups.items():
        pool = values.loc[idx].dropna()
        if len(pool) < 2:
            continue
        # rank(pct=True) gives 0-1 within the eligible pool; scale to 0-100.
        ranks = pool.rank(pct=True) * 100.0
        out.loc[ranks.index] = ranks.values
    return out


def is_limited_sample(minutes: pd.Series, min_minutes: int = MIN_MINUTES_DEFAULT) -> pd.Series:
    return minutes < min_minutes
