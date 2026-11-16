"""MacroLens web API.

A small FastAPI service that wraps the existing ``src/`` pipeline and serves
the hand-built frontend in ``web/``. One process, one deploy -- no Streamlit.

    uvicorn server.app:app --reload --port 8000
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import analyze, log  # noqa: E402
from src.nutrition import describe  # noqa: E402

WEB_DIR = ROOT / "web"
SAMPLES_DIR = ROOT / "samples"
NUTRITION_CSV = ROOT / "data" / "nutrition_map.csv"
RESULTS_JSON = ROOT / "eval" / "results.json"

CONFIDENCE_THRESHOLD = 0.40

_status = {"model_ready": False, "model_error": None}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.init_db()

    # A fresh deploy starts with an empty log, which makes the live URL look
    # broken. Seed demo meals once so Patterns has something real to show.
    # Set MACROLENS_DEMO=0 to disable.
    if os.environ.get("MACROLENS_DEMO", "1") != "0":
        try:
            if analyze.summary()["meals"] == 0:
                from scripts.seed_demo import seed

                seed(40, reset=False)
        except Exception as exc:  # noqa: BLE001
            print(f"[startup] demo seed skipped: {type(exc).__name__}: {exc}")

    # Warm the model once so the first analysis is quick.
    try:
        from src.classify import load_classifier

        load_classifier()
        _status["model_ready"] = True
    except Exception as exc:  # noqa: BLE001
        _status["model_error"] = f"{type(exc).__name__}: {exc}"
    yield


app = FastAPI(title="MacroLens", version="1.0.0", lifespan=lifespan)


# --------------------------------------------------------------------------- models
class EstimateIn(BaseModel):
    dish: str
    portion: float = 1.0


class LogIn(BaseModel):
    dish: str
    display: str
    confidence: float
    portion: float = 1.0
    corrected: bool = False


class UpdateMealIn(BaseModel):
    portion: float


class SettingsIn(BaseModel):
    daily_goal: float | None = None
    theme: str | None = None


class CompareIn(BaseModel):
    dish_a: str
    dish_b: str
    portion_a: float = 1.0
    portion_b: float = 1.0


# -------------------------------------------------------------------- serialisation
def _clean(value):
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def _records(df) -> list[dict]:
    if df is None or df.empty:
        return []
    return [{k: _clean(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def _macros(info: dict) -> dict:
    return {
        "known": bool(info.get("_known")),
        "portion": info.get("portion", ""),
        "multiplier": info.get("portion_multiplier", 1.0),
        "values": {k: info.get(k) for k in ("kcal", "protein_g", "carbs_g", "fat_g")},
        "ranges": info.get("ranges", {}),
        "note": info.get("note", ""),
    }


def _dish_list() -> list[str]:
    if not NUTRITION_CSV.exists():
        return []
    lines = NUTRITION_CSV.read_text(encoding="utf-8").splitlines()[1:]
    return sorted({ln.split(",")[0].strip() for ln in lines if ln.strip()})


# ------------------------------------------------------------------ read endpoints
@app.get("/api/health")
def health():
    return {
        "ok": True,
        "model_ready": _status["model_ready"],
        "model_error": _status["model_error"],
        "threshold": CONFIDENCE_THRESHOLD,
    }


@app.get("/api/dishes")
def dishes():
    return {"dishes": _dish_list()}


@app.get("/api/samples")
def samples():
    if not SAMPLES_DIR.exists():
        return {"samples": []}
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    return {"samples": sorted(p.name for p in SAMPLES_DIR.iterdir() if p.suffix.lower() in exts)}


@app.get("/api/patterns")
def patterns(days: int = 14):
    goal_raw = log.get_setting("daily_goal")
    goal = float(goal_raw) if goal_raw else None
    return {
        "summary": analyze.summary(),
        "daily": _records(analyze.daily_totals(days)),
        "macroSplit": analyze.macro_split(),
        "topDishes": _records(analyze.top_dishes(6)),
        "meals": _records(analyze.load_meals()),
        "weekday": analyze.weekday_split(),
        "insights": analyze.insights(goal),
        "goal": goal,
        "goalProgress": analyze.goal_progress(goal) if goal else None,
    }


@app.get("/api/settings")
def get_settings():
    goal_raw = log.get_setting("daily_goal")
    return {
        "daily_goal": float(goal_raw) if goal_raw else None,
        "theme": log.get_setting("theme", "light"),
    }


@app.put("/api/settings")
def put_settings(body: SettingsIn):
    if body.daily_goal is not None:
        log.set_setting("daily_goal", body.daily_goal)
    if body.theme:
        log.set_setting("theme", body.theme)
    return get_settings()


@app.get("/api/export.csv")
def export_csv():
    fields = ["id", "logged_at", "dish", "display", "confidence",
              "portion", "kcal", "protein_g", "carbs_g", "fat_g", "corrected"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in analyze.export_rows():
        writer.writerow(row)
    from fastapi.responses import Response

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=macrolens-log.csv"},
    )


@app.post("/api/compare")
def compare(body: CompareIn):
    a = describe(body.dish_a, body.portion_a)
    b = describe(body.dish_b, body.portion_b)
    return {
        "a": {"dish": body.dish_a, "macros": _macros(a)},
        "b": {"dish": body.dish_b, "macros": _macros(b)},
    }


@app.get("/api/accuracy")
def accuracy():
    if RESULTS_JSON.exists():
        data = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
        data["available"] = True
        return data
    return {"available": False}


# ----------------------------------------------------------------- write endpoints
@app.post("/api/analyze")
async def analyze_photo(file: UploadFile = File(...)):
    from src.classify import classify

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="That file was empty.")
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Could not read that image.")

    predictions = classify(image, top_k=5)
    best = predictions[0]
    info = describe(best["label"], 1.0)
    return {
        "predictions": predictions,
        "best": best,
        "confident": best["score"] >= CONFIDENCE_THRESHOLD,
        "threshold": CONFIDENCE_THRESHOLD,
        "macros": _macros(info),
    }


@app.post("/api/analyze-batch")
async def analyze_batch(files: list[UploadFile] = File(...)):
    """Classify many photos in one request. Returns one result per image.

    Batch is where the honesty thesis compounds: mixed confidence across a
    folder is visible at once, and the low-confidence ones are flagged.
    """
    from src.classify import classify

    out = []
    for f in files:
        raw = await f.read()
        try:
            image = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:  # noqa: BLE001
            out.append({"file": f.filename, "ok": False, "error": "unreadable"})
            continue
        preds = classify(image, top_k=5)
        best = preds[0]
        info = describe(best["label"], 1.0)
        out.append({
            "file": f.filename,
            "ok": True,
            "predictions": preds,
            "best": best,
            "confident": best["score"] >= CONFIDENCE_THRESHOLD,
            "macros": _macros(info),
        })
    return {"results": out, "threshold": CONFIDENCE_THRESHOLD}


@app.post("/api/estimate")
def estimate(body: EstimateIn):
    info = describe(body.dish, body.portion)
    return {"dish": body.dish, "macros": _macros(info)}


@app.post("/api/log")
def log_meal(body: LogIn):
    info = describe(body.dish, body.portion)
    meal_id = log.log_meal(
        dish=body.dish,
        display=body.display,
        confidence=body.confidence,
        portion_multiplier=body.portion,
        macros=info,
        corrected=body.corrected,
    )
    return {"ok": True, "id": meal_id}


@app.put("/api/log/{meal_id}")
def update_log(meal_id: int, body: UpdateMealIn):
    meal = log.get_meal(meal_id)
    if meal is None:
        raise HTTPException(status_code=404, detail="No such meal.")
    info = describe(meal["dish"], body.portion)
    log.update_meal(meal_id, body.portion, info)
    return {"ok": True, "macros": _macros(info)}


@app.delete("/api/log/{meal_id}")
def delete_log(meal_id: int):
    if log.get_meal(meal_id) is None:
        raise HTTPException(status_code=404, detail="No such meal.")
    log.delete_meal(meal_id)
    return {"ok": True}


@app.post("/api/log/reset")
def reset_log():
    log.reset()
    return {"ok": True}


# --------------------------------------------------------------------------- static
if SAMPLES_DIR.exists():
    app.mount("/samples", StaticFiles(directory=str(SAMPLES_DIR)), name="samples")
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
