"""Persistence for logged meals, backed by DuckDB.

Each time you classify a meal in the app, we append one row. Over time this
becomes the dataset the dashboard analyses -- the "analysis half" of the
project literally cannot exist without this table.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
# MACROLENS_DB lets tests point at a throwaway file instead of the real log.
DB_PATH = Path(os.environ["MACROLENS_DB"]) if os.environ.get("MACROLENS_DB") else DATA_DIR / "logs.duckdb"


def _connect():
    import duckdb

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def init_db() -> None:
    con = _connect()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS meals (
            id            INTEGER,
            logged_at     TIMESTAMP,
            dish          VARCHAR,
            display       VARCHAR,
            confidence    DOUBLE,
            portion       DOUBLE,
            kcal          DOUBLE,
            protein_g     DOUBLE,
            carbs_g       DOUBLE,
            fat_g         DOUBLE,
            corrected     BOOLEAN DEFAULT FALSE
        )
        """
    )
    con.close()


def log_meal(
    dish: str,
    display: str,
    confidence: float,
    portion_multiplier: float,
    macros: dict,
    corrected: bool = False,
    logged_at: datetime | None = None,
) -> None:
    """Append one meal row. macros is the output of nutrition.lookup()."""
    import duckdb

    con = _connect()
    init_db()
    next_id = con.execute(
        "SELECT COALESCE(MAX(id), 0) + 1 FROM meals"
    ).fetchone()[0]

    con.execute(
        """
        INSERT INTO meals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            next_id,
            logged_at or datetime.now(timezone.utc),
            dish,
            display,
            float(confidence),
            float(portion_multiplier),
            macros.get("kcal"),
            macros.get("protein_g"),
            macros.get("carbs_g"),
            macros.get("fat_g"),
            bool(corrected),
        ],
    )
    con.close()
    return next_id


def delete_meal(meal_id: int) -> None:
    con = _connect()
    con.execute("DELETE FROM meals WHERE id = ?", [meal_id])
    con.close()


def update_meal(meal_id: int, portion_multiplier: float, macros: dict) -> None:
    """Re-set one meal's portion and recompute its stored macros."""
    con = _connect()
    con.execute(
        """
        UPDATE meals
           SET portion = ?, kcal = ?, protein_g = ?, carbs_g = ?, fat_g = ?
         WHERE id = ?
        """,
        [
            float(portion_multiplier),
            macros.get("kcal"),
            macros.get("protein_g"),
            macros.get("carbs_g"),
            macros.get("fat_g"),
            int(meal_id),
        ],
    )
    con.close()


def get_meal(meal_id: int):
    """Return one meal row as a dict, or None."""
    con = _connect()
    init_db()
    try:
        row = con.execute(
            "SELECT * FROM meals WHERE id = ?", [int(meal_id)]
        ).fetchone()
        cols = [c[0] for c in con.description]
    finally:
        con.close()
    if row is None:
        return None
    return dict(zip(cols, row))


# ---------------------------------------------------------------- settings
def _init_settings() -> None:
    con = _connect()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key   VARCHAR PRIMARY KEY,
            value VARCHAR
        )
        """
    )
    con.close()


def set_setting(key: str, value) -> None:
    con = _connect()
    _init_settings()
    con.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        [key, str(value)],
    )
    con.close()


def get_setting(key: str, default=None):
    con = _connect()
    _init_settings()
    try:
        row = con.execute(
            "SELECT value FROM settings WHERE key = ?", [key]
        ).fetchone()
    finally:
        con.close()
    return row[0] if row else default


def reset() -> None:
    con = _connect()
    con.execute("DROP TABLE IF EXISTS meals")
    con.close()
    init_db()


if __name__ == "__main__":
    init_db()
    print(f"Initialised {DB_PATH}")
