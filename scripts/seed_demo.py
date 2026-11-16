"""Seed the log with demo meals so the dashboard has something to show.

    python -m scripts.seed_demo

Real usage replaces this: you log through the app. This exists so a fresh
clone can demo the analysis half without photographing ten meals first.
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import log  # noqa: E402
from src.nutrition import lookup  # noqa: E402

random.seed(7)

MENU = [
    "pizza",
    "sushi",
    "caesar_salad",
    "ramen",
    "hamburger",
    "greek_salad",
    "chicken_curry",
    "pancakes",
    "omelette",
    "spaghetti_bolognese",
    "grilled_salmon",
    "tacos",
]


def seed(count: int = 40, reset: bool = True) -> int:
    """Write `count` plausible meals across the last two weeks.

    `reset=False` is what the server uses on a fresh deploy: it tops up an empty
    log so the live URL shows a working dashboard instead of an empty state.
    """
    if reset:
        log.reset()
    now = datetime.now(timezone.utc)

    for _ in range(count):
        dish = random.choice(MENU)
        portion = random.choice([0.75, 1.0, 1.0, 1.25, 1.5])
        day_offset = random.randint(0, 13)
        logged_at = now - timedelta(days=day_offset, hours=random.randint(0, 12))

        macros = lookup(dish, portion)
        log.log_meal(
            dish=dish,
            display=dish.replace("_", " ").title(),
            confidence=random.uniform(0.55, 0.98),
            portion_multiplier=portion,
            macros=macros,
            corrected=random.random() < 0.1,
            logged_at=logged_at,
        )
    return count


def main(count: int = 40) -> None:
    seed(count, reset=True)

    from src import analyze

    print("Seeded", count, "demo meals.")
    print(analyze.summary())


if __name__ == "__main__":
    main()
