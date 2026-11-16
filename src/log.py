"""Persistence for logged meals, backed by DuckDB.

Each time you classify a meal in the app, we append one row. Over time this
becomes the dataset the dashboard analyses -- the "analysis half" of the
project literally cannot exist without this table.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "logs.duckdb"


def _connect():
    import duckdb

    DATA_DIR.mkdir(parents=True, exist_ok=True)
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


def reset() -> None:
    con = _connect()
    con.execute("DROP TABLE IF EXISTS meals")
    con.close()
    init_db()


if __name__ == "__main__":
    init_db()
    print(f"Initialised {DB_PATH}")
