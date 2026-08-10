"""Unit tests for per-90 and percentile logic — the numbers everything rests on."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.transform import (  # noqa: E402
    per90,
    percentile_within_group,
    primary_position_group,
    is_limited_sample,
)


def test_per90_basic():
    goals = pd.Series([10.0, 5.0, 0.0])
    minutes = pd.Series([900.0, 450.0, 900.0])  # 10 and 5 full matches
    result = per90(goals, minutes)
    assert result.tolist() == pytest.approx([1.0, 1.0, 0.0])


def test_per90_zero_minutes_is_nan_not_inf():
    result = per90(pd.Series([3.0]), pd.Series([0.0]))
    assert np.isnan(result.iloc[0])


def test_primary_position_group():
    assert primary_position_group("DF,MF") == "DF"
    assert primary_position_group("FW") == "FW"
    assert primary_position_group("GK") == "GK"
    assert primary_position_group("") == "Unknown"
    assert primary_position_group(np.nan) == "Unknown"


def test_percentile_top_and_bottom():
    # One position group, all above min minutes.
    values = pd.Series([1.0, 2.0, 3.0, 4.0])
    groups = pd.Series(["FW", "FW", "FW", "FW"])
    minutes = pd.Series([900.0, 900.0, 900.0, 900.0])
    pct = percentile_within_group(values, groups, minutes, min_minutes=450)
    assert pct.iloc[3] == pytest.approx(100.0)   # highest value -> 100th
    assert pct.iloc[0] == pytest.approx(25.0)    # lowest of 4 -> 25th


def test_percentile_excludes_low_minutes():
    values = pd.Series([1.0, 2.0, 99.0])
    groups = pd.Series(["FW", "FW", "FW"])
    minutes = pd.Series([900.0, 900.0, 90.0])  # third is a 1-appearance spike
    pct = percentile_within_group(values, groups, minutes, min_minutes=450)
    assert np.isnan(pct.iloc[2])                 # low-sample gets no rank
    assert pct.iloc[1] == pytest.approx(100.0)   # ranked only among the eligible


def test_percentile_separates_position_groups():
    values = pd.Series([10.0, 1.0, 10.0, 1.0])
    groups = pd.Series(["FW", "FW", "DF", "DF"])
    minutes = pd.Series([900.0] * 4)
    pct = percentile_within_group(values, groups, minutes, min_minutes=450)
    # A DF with value 10 tops the DF pool, not measured against FWs.
    assert pct.iloc[2] == pytest.approx(100.0)
    assert pct.iloc[3] == pytest.approx(50.0)


def test_is_limited_sample():
    minutes = pd.Series([449.0, 450.0, 1000.0])
    flags = is_limited_sample(minutes, min_minutes=450)
    assert flags.tolist() == [True, False, False]
