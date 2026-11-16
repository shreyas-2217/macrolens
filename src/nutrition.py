"""Dish -> macro lookup.

This is the bridge between the CV half (a dish name) and the analysis half
(a row of nutrition numbers).

Values are *per standard serving* and are deliberately approximate. The UI
turns them into ranges (see _uncertainty) because a photo cannot tell you the
portion size -- and pretending otherwise would be dishonest.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NUTRITION_CSV = DATA_DIR / "nutrition_map.csv"

# Fallback used when a dish is not in the map. Rather than crash, we return an
# "unknown" row and let the UI ask the user -- the graceful way out.
UNKNOWN = {
    "kcal": None,
    "protein_g": None,
    "carbs_g": None,
    "fat_g": None,
    "portion": "unknown",
}

# How uncertain each macro is, in relative terms, because of portion size.
# A photo cannot measure grams, so every number is really a band.
_UNCERTAINTY = 0.20  # +/- 20%


@lru_cache(maxsize=1)
def _load_map() -> dict[str, dict]:
    """Read data/nutrition_map.csv into {dish_key: macros}."""
    table: dict[str, dict] = {}
    if not NUTRITION_CSV.exists():
        return table

    with NUTRITION_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = row["dish"].strip().lower()
            table[key] = {
                "kcal": _num(row.get("kcal")),
                "protein_g": _num(row.get("protein_g")),
                "carbs_g": _num(row.get("carbs_g")),
                "fat_g": _num(row.get("fat_g")),
                "portion": row.get("portion", "1 serving").strip() or "1 serving",
            }
    return table


def _num(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def lookup(dish_key: str, portion_multiplier: float = 1.0) -> dict:
    """Return macros for a dish, scaled by an optional portion multiplier.

    portion_multiplier lets the UI expose a slider: 0.5 = small plate,
    1.0 = standard, 1.5 = large. This is how we let the *user* fix the thing
    a photo genuinely cannot know.
    """
    base = _load_map().get(dish_key.strip().lower(), UNKNOWN)

    result = dict(base)
    for key in ("kcal", "protein_g", "carbs_g", "fat_g"):
        if result[key] is not None:
            result[key] = round(result[key] * portion_multiplier, 1)

    result["dish"] = dish_key
    result["portion_multiplier"] = portion_multiplier
    result["_known"] = base is not UNKNOWN and base.get("kcal") is not None
    return result


def uncertainty_band(value, rel: float = _UNCERTAINTY) -> tuple[float, float] | None:
    """Turn a point estimate into an honest (low, high) range."""
    if value is None:
        return None
    return (round(value * (1 - rel), 1), round(value * (1 + rel), 1))


def describe(dish_key: str, portion_multiplier: float = 1.0) -> dict:
    """Full lookup plus ready-to-render ranges and a plain-English note."""
    macros = lookup(dish_key, portion_multiplier)

    if not macros["_known"]:
        return {
            **macros,
            "ranges": {},
            "note": "Not in our nutrition table yet -- add it or log it manually.",
        }

    ranges = {
        "kcal": uncertainty_band(macros["kcal"]),
        "protein_g": uncertainty_band(macros["protein_g"]),
        "carbs_g": uncertainty_band(macros["carbs_g"]),
        "fat_g": uncertainty_band(macros["fat_g"]),
    }

    lo, hi = ranges["kcal"]
    return {
        **macros,
        "ranges": ranges,
        "note": (
            f"Approx {lo:.0f}-{hi:.0f} kcal per {macros['portion']}. "
            "Range reflects portion uncertainty -- adjust the slider to match your plate."
        ),
    }
