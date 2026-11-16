"""Unit tests for the non-model layers.

Run:  python -m pytest -q   (or:  python tests/test_core.py)
These never import torch, so they run anywhere in a second.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import analyze, log  # noqa: E402
from src.nutrition import (  # noqa: E402
    UNKNOWN,
    describe,
    lookup,
    uncertainty_band,
)


def test_known_dish():
    assert lookup("pizza")["_known"] is True
    assert lookup("pizza")["kcal"] > 0


def test_unknown_dish_is_safe():
    assert lookup("definitely_not_a_dish")["_known"] is False
    assert lookup("definitely_not_a_dish")["kcal"] is None


def test_band_is_ordered():
    lo, hi = uncertainty_band(500)
    assert lo < 500 < hi


def test_portion_scales_linearly():
    base = lookup("sushi", 1.0)["kcal"]
    doubled = lookup("sushi", 2.0)["kcal"]
    assert abs(doubled - base * 2) < 0.5


def test_describe_has_note():
    d = describe("ramen", 1.0)
    assert d["note"]
    assert set(d["ranges"]) == {"kcal", "protein_g", "carbs_g", "fat_g"}


def test_describe_unknown_has_no_ranges():
    d = describe("definitely_not_a_dish", 1.0)
    assert d["ranges"] == {}


def test_log_round_trip():
    log.reset()
    log.log_meal("pizza", "Pizza", 0.9, 1.0, lookup("pizza"))
    assert analyze.summary()["meals"] == 1
    df = analyze.load_meals()
    assert df.iloc[0]["dish"] == "pizza"
    log.reset()
    assert analyze.summary()["meals"] == 0


def test_summary_empty_is_safe():
    log.reset()
    s = analyze.summary()
    assert s["meals"] == 0
    assert s["avg_kcal"] == 0.0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"[PASS] {t.__name__}")
        except AssertionError:
            failed += 1
            print(f"[FAIL] {t.__name__}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
