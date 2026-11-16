"""Smoke tests that do NOT require torch / the model.

Run:
    python eval/smoke_test.py

Verifies the nutrition map loads, ranges compute, and the DuckDB log
round-trips -- so you can catch plumbing bugs before loading a model.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import analyze, log  # noqa: E402
from src.nutrition import describe, lookup, uncertainty_band  # noqa: E402


def check(label, condition):
    condition = bool(condition)
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}")
    return condition


def main() -> int:
    ok = True

    # Nutrition map
    pizza = lookup("pizza")
    ok &= check("pizza is known", pizza["_known"])
    ok &= check("pizza has calories", pizza["kcal"] and pizza["kcal"] > 0)

    unknown = lookup("not_a_real_dish_xyz")
    ok &= check("unknown dish is handled", unknown["_known"] is False)

    band = uncertainty_band(500)
    ok &= check("range is a (low, high) pair", band[0] < band[1])

    d = describe("pizza", 1.0)
    ok &= check("describe() returns ranges", "kcal" in d["ranges"] and bool(d["note"]))

    scaled = lookup("pizza", 2.0)
    ok &= check("portion scales calories", abs(scaled["kcal"] - 2 * pizza["kcal"]) < 0.2)

    # Log round-trip (uses a temp DB-safe reset)
    log.reset()
    log.log_meal("pizza", "Pizza", 0.9, 1.0, lookup("pizza"))
    s = analyze.summary()
    ok &= check("one meal logged", s["meals"] == 1)
    ok &= check("avg confidence tracked", s["avg_confidence"] > 0)

    log.reset()
    ok &= check("reset clears the log", analyze.summary()["meals"] == 0)

    print("\nAll good." if ok else "\nSomething failed.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
