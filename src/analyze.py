"""Analysis queries over the logged meals.

This is the "data analysis" half of the project: turn a table of classified
meals into the numbers the dashboard shows. All SQL lives here so the app
stays thin and these queries are testable.
"""

from __future__ import annotations

from datetime import date, timedelta

from src.log import DB_PATH, _connect, init_db


def load_meals():
    """Return every logged meal as a pandas DataFrame (empty-safe)."""
    init_db()
    con = _connect()
    try:
        df = con.execute("SELECT * FROM meals ORDER BY logged_at").df()
    finally:
        con.close()
    return df


def _empty(df) -> bool:
    return df is None or df.empty


def daily_totals(days: int = 14):
    """Calories per day for the last `days` days."""
    df = load_meals()
    if _empty(df):
        return df
    df["day"] = df["logged_at"].dt.date
    cutoff = date.today() - timedelta(days=days)
    recent = df[df["day"] >= cutoff]
    return (
        recent.groupby("day", as_index=False)
        .agg(kcal=("kcal", "sum"), meals=("id", "count"))
        .sort_values("day")
    )


def macro_split():
    """Total grams per macro across all logged meals."""
    df = load_meals()
    if _empty(df):
        return {"protein_g": 0, "carbs_g": 0, "fat_g": 0}
    return {
        "protein_g": float(df["protein_g"].fillna(0).sum()),
        "carbs_g": float(df["carbs_g"].fillna(0).sum()),
        "fat_g": float(df["fat_g"].fillna(0).sum()),
    }


def top_dishes(n: int = 5):
    """Most frequently logged dishes."""
    df = load_meals()
    if _empty(df):
        return df
    return (
        df.groupby("display", as_index=False)
        .agg(count=("id", "count"), avg_kcal=("kcal", "mean"))
        .sort_values("count", ascending=False)
        .head(n)
    )


def summary():
    """Headline stats for the dashboard cards."""
    df = load_meals()
    if _empty(df):
        return {
            "meals": 0,
            "avg_kcal": 0.0,
            "avg_confidence": 0.0,
            "corrections": 0,
            "unknown_dishes": 0,
        }
    return {
        "meals": int(len(df)),
        "avg_kcal": round(float(df["kcal"].fillna(0).mean()), 1),
        "avg_confidence": round(float(df["confidence"].mean()), 3),
        "corrections": int(df["corrected"].fillna(False).sum()),
        "unknown_dishes": int(df["kcal"].isna().sum()),
    }
