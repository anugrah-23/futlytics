"""Tests for build_players helpers: comma-safe numerics and name folding
(both are load-bearing — a comma bug NaN'd every player's minutes once)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.build_players import _norm, _num  # noqa: E402


def test_num_strips_thousands_separator():
    s = pd.Series(["3,371", "450", "1,000", ""])
    out = _num(s)
    assert out.tolist()[:3] == [3371.0, 450.0, 1000.0]
    assert np.isnan(out.iloc[3])


def test_num_handles_none():
    assert _num(None).empty


def test_norm_folds_accents_and_case():
    assert _norm("Jhon Durán") == "jhon duran"
    assert _norm("Rodri") == "rodri"
    assert _norm("  N'Golo Kanté ") == "n'golo kante"


def test_norm_non_string():
    assert _norm(np.nan) == ""
    assert _norm(None) == ""
