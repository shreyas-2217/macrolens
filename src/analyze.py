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


def goal_progress(daily_goal: float, days: int = 14):
    """How each recent day (and the average) sits against a daily calorie goal.

    Returns honest per-day bands: the log itself carries an uncertainty, so a
    day near the goal is reported as "in range" rather than pass/fail.
    """
    df = load_meals()
    if _empty(df):
        return {
            "goal": daily_goal,
            "avg_kcal": 0.0,
            "days_on_target": 0,
            "days_logged": 0,
            "per_day": [],
        }

    df["day"] = df["logged_at"].dt.date
    daily = (
        df.groupby("day", as_index=False)
        .agg(kcal=("kcal", "sum"))
        .sort_values("day")
    )
    cutoff = date.today() - timedelta(days=days)
    recent = daily[daily["day"] >= cutoff]

    # a day is "on target" if its total lands within +/-20% of the goal
    lo, hi = daily_goal * 0.8, daily_goal * 1.2
    on_target = int(((recent["kcal"] >= lo) & (recent["kcal"] <= hi)).sum())

    return {
        "goal": daily_goal,
        "band_low": round(lo),
        "band_high": round(hi),
        "avg_kcal": round(float(recent["kcal"].mean()), 1) if len(recent) else 0.0,
        "days_on_target": on_target,
        "days_logged": int(len(recent)),
        "per_day": [
            {
                "day": r["day"].isoformat(),
                "kcal": round(float(r["kcal"])),
                "on_target": bool(lo <= r["kcal"] <= hi),
            }
            for _, r in recent.iterrows()
        ],
    }


def weekday_split():
    """Average calories by day of week -- the classic 'weekends are heavier'."""
    df = load_meals()
    if _empty(df):
        return []
    df["day"] = df["logged_at"].dt.date
    daily = df.groupby("day", as_index=False).agg(kcal=("kcal", "sum"))
    daily["dow"] = [d.weekday() for d in daily["day"]]
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    agg = daily.groupby("dow", as_index=False).agg(avg_kcal=("kcal", "mean"), days=("kcal", "count"))
    out = []
    for i, name in enumerate(names):
        row = agg[agg["dow"] == i]
        out.append({
            "dow": name,
            "avg_kcal": round(float(row["avg_kcal"].iloc[0])) if len(row) else 0,
            "days": int(row["days"].iloc[0]) if len(row) else 0,
        })
    return out


def insights(daily_goal: float | None = None) -> list[dict]:
    """Plain-English findings computed from the log. Each has a title + detail.

    This is the part a human would otherwise eyeball; we compute it so the
    Patterns view can *tell* the user something instead of only drawing bars.
    """
    df = load_meals()
    if _empty(df) or len(df) < 5:
        return []

    findings: list[dict] = []
    df = df.copy()
    df["day"] = df["logged_at"].dt.date
    daily = df.groupby("day", as_index=False).agg(kcal=("kcal", "sum"), meals=("id", "count"))
    daily["dow"] = [d.weekday() for d in daily["day"]]

    # weekend vs weekday
    weekend = daily[daily["dow"] >= 5]["kcal"]
    weekday = daily[daily["dow"] < 5]["kcal"]
    if len(weekend) and len(weekday):
        wend, wday = float(weekend.mean()), float(weekday.mean())
        if wday > 0:
            delta = (wend - wday) / wday * 100
            if abs(delta) >= 8:
                direction = "higher" if delta > 0 else "lower"
                findings.append({
                    "kind": "weekend",
                    "title": f"Weekends run {abs(delta):.0f}% {direction}",
                    "detail": (
                        f"Sat–Sun average {wend:.0f} kcal vs {wday:.0f} kcal on weekdays. "
                        f"{'A tighter weekend plan would move the needle most.' if delta > 0 else 'Weekdays are your heavier days, not weekends.'}"
                    ),
                })

    # most-logged dish
    top = (
        df.groupby("display", as_index=False)
        .agg(count=("id", "count"), kcal=("kcal", "mean"))
        .sort_values("count", ascending=False)
    )
    if len(top):
        first = top.iloc[0]
        share = first["count"] / len(df) * 100
        findings.append({
            "kind": "top-dish",
            "title": f"{first['display']} is {share:.0f}% of your log",
            "detail": (
                f"Logged {int(first['count'])} times, about {first['kcal']:.0f} kcal a plate. "
                f"That's your most repeated choice."
            ),
        })

    # correction rate -- the app measuring its own honesty
    corr = int(df["corrected"].fillna(False).sum())
    if corr > 0:
        rate = corr / len(df) * 100
        findings.append({
            "kind": "corrections",
            "title": f"You overruled the model {rate:.0f}% of the time",
            "detail": (
                f"{corr} of {len(df)} meals were corrected. "
                "The higher this is, the more the model needed your help."
            ),
        })

    # confidence vs accuracy: are low-confidence meals the ones you fix?
    low = df[df["confidence"] < 0.5]
    if len(low) >= 2:
        low_fix = low["corrected"].fillna(False).mean() * 100
        findings.append({
            "kind": "confidence",
            "title": f"Under-50% guesses got fixed {low_fix:.0f}% of the time",
            "detail": (
                f"{len(low)} meals landed below 50% confidence. "
                "That is the app asking instead of guessing -- and it works."
            ),
        })

    # goal adherence
    if daily_goal:
        prog = goal_progress(daily_goal)
        if prog["days_logged"]:
            findings.append({
                "kind": "goal",
                "title": f"{prog['days_on_target']} of {prog['days_logged']} days near your goal",
                "detail": (
                    f"Your goal is {daily_goal:.0f} kcal; days within "
                    f"{prog['band_low']}–{prog['band_high']} count as on target. "
                    f"Recent average: {prog['avg_kcal']:.0f} kcal."
                ),
            })

    return findings


def export_rows():
    """Every logged meal as plain dicts, for CSV export."""
    df = load_meals()
    if _empty(df):
        return []
    return [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in row.items()}
            for row in df.to_dict(orient="records")]
