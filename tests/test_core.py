"""Unit tests for the non-model layers.

Run:  python -m pytest -q   (or:  python tests/test_core.py)
These never import torch, so they run anywhere in a second.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Point the log at a throwaway file *before* importing it, so tests never
# touch the real data/logs.duckdb.
_TEST_DB = Path(tempfile.gettempdir()) / "macrolens_test_logs.duckdb"
os.environ["MACROLENS_DB"] = str(_TEST_DB)

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


def test_update_and_delete_meal():
    log.reset()
    log.log_meal("pizza", "Pizza", 0.9, 1.0, lookup("pizza"))
    meal = log.get_meal(1)
    assert meal["dish"] == "pizza"
    log.update_meal(1, 2.0, lookup("pizza", 2.0))
    assert log.get_meal(1)["portion"] == 2.0
    assert log.get_meal(1)["kcal"] == lookup("pizza", 2.0)["kcal"]
    log.delete_meal(1)
    assert log.get_meal(1) is None
    assert analyze.summary()["meals"] == 0


def test_settings_round_trip():
    log.set_setting("daily_goal", 2100)
    assert log.get_setting("daily_goal") == "2100"
    assert log.get_setting("missing", "fallback") == "fallback"


def test_goal_progress_bands():
    log.reset()
    from datetime import datetime, timezone

    from src.nutrition import lookup

    # three meals today summing well past the goal
    for dish in ("pizza", "sushi", "ramen"):
        log.log_meal(dish, dish.title(), 0.9, 1.0, lookup(dish),
                     logged_at=datetime.now(timezone.utc))
    prog = analyze.goal_progress(2000)
    assert prog["days_logged"] == 1
    assert prog["band_low"] == 1600 and prog["band_high"] == 2400
    assert len(prog["per_day"]) == 1
    log.reset()


def test_insights_need_enough_rows():
    log.reset()
    from src.nutrition import lookup

    log.log_meal("pizza", "Pizza", 0.9, 1.0, lookup("pizza"))
    assert analyze.insights() == []      # too few rows -> no findings
    log.reset()


def test_weekday_split_shape():
    log.reset()
    from src.nutrition import lookup

    for _ in range(6):
        log.log_meal("pizza", "Pizza", 0.9, 1.0, lookup("pizza"))
    wd = analyze.weekday_split()
    assert len(wd) == 7
    assert [d["dow"] for d in wd] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    log.reset()


def test_export_rows_is_serialisable():
    log.reset()
    from src.nutrition import lookup

    log.log_meal("pizza", "Pizza", 0.9, 1.0, lookup("pizza"))
    import json

    rows = analyze.export_rows()
    assert len(rows) == 1
    json.dumps(rows)  # must not raise (dates coerced to strings)
    log.reset()


def test_summary_empty_is_safe():
    log.reset()
    s = analyze.summary()
    assert s["meals"] == 0
    assert s["avg_kcal"] == 0.0


def test_folder_eval_iterates(tmp_path=None):
    """The --folder evaluator reads eval_set/<dish>/*.jpg without the model."""
    import tempfile
    from pathlib import Path as _P

    from PIL import Image

    from eval.evaluate import _iter_folder

    with tempfile.TemporaryDirectory() as tmp:
        root = _P(tmp)
        for dish in ("pizza", "sushi"):
            d = root / dish
            d.mkdir()
            Image.new("RGB", (32, 32), (200, 120, 60)).save(d / "a.jpg")
            Image.new("RGB", (32, 32), (60, 120, 200)).save(d / "b.png")

        rows = list(_iter_folder(root))
        assert len(rows) == 4, rows
        truths = {t for _, t in rows}
        assert truths == {"pizza", "sushi"}, truths
        img, truth = rows[0]
        assert img.mode == "RGB"


def test_ignore_non_images_in_folder():
    import tempfile
    from pathlib import Path as _P

    from eval.evaluate import _iter_folder

    with tempfile.TemporaryDirectory() as tmp:
        root = _P(tmp)
        d = root / "ramen"
        d.mkdir()
        (d / "notes.txt").write_text("not an image")
        assert list(_iter_folder(root)) == []


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
