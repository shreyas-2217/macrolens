# Architecture

## The "mix" in one line

> Computer vision turns pixels into a **dataset**; data analysis turns that
> dataset into **decisions**.

```
┌──────────────┐   ┌───────────────┐   ┌──────────────┐   ┌─────────────┐
│  Image input │──►│  Classifier   │──►│  Nutrition   │──►│   DuckDB    │
│ (upload/CLI) │   │  (pretrained) │   │    map       │   │   meals     │
└──────────────┘   └───────────────┘   └──────────────┘   └──────┬──────┘
                                                                  │
                                          ┌───────────────────────┘
                                          ▼
                                   ┌──────────────┐   ┌──────────────────┐
                                   │   pandas /   │──►│    Streamlit     │
                                   │     SQL      │   │    dashboard     │
                                   └──────────────┘   └──────────────────┘
```

## Components

| Module | Responsibility | Depends on |
|---|---|---|
| `src/classify.py` | Load a pretrained Food-101 model, return ranked (label, score) predictions | transformers, torch |
| `src/nutrition.py` | Map dish → approximate macros; produce honest ranges | data/nutrition_map.csv |
| `src/log.py` | Append/read meal rows in DuckDB | duckdb |
| `src/analyze.py` | Daily totals, macro split, top dishes, summary | pandas, log |
| `server/app.py` | FastAPI: JSON endpoints wrapping `src/`, serves `web/` | fastapi, all of the above |
| `web/` | Hand-built interface: belief strip + measured gauges | the API |
| `eval/evaluate.py` | Score the classifier: Food-101 test set **or** your own `eval_set/` photos | datasets, classify, nutrition |

## Data flow, concretely

1. An image arrives at `POST /api/analyze` (or as a `PIL.Image` in Python).
2. `classify()` returns `[{"label": "pizza", "score": 0.82}, ...]`.
3. `nutrition.describe("pizza", portion=1.0)` returns macros **and ranges**.
4. The interface renders the belief strip and measured gauges from that payload.
5. `POST /api/log` inserts a row; `GET /api/patterns` aggregates them.

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Model readiness + refusal threshold |
| GET | `/api/dishes` | The 101 known dishes (for the correction picker) |
| GET | `/api/samples` | Demo photos in `samples/` |
| GET | `/api/patterns` | Summary, daily totals, macro split, top dishes, raw log |
| GET | `/api/accuracy` | Latest `eval/results.json` |
| POST | `/api/analyze` | Multipart image → predictions + macros |
| POST | `/api/estimate` | `{dish, portion}` → recomputed macros |
| POST | `/api/log` | Persist a meal row |

## Why this split

Each layer is independently testable and replaceable:
- swap the model in `classify.py` without touching anything else,
- swap DuckDB for Postgres in `log.py`,
- extend `nutrition_map.csv` without code changes.

## Honesty as an architecture decision

Uncertainty is not an afterthought bolted onto the UI — it lives in the data:
- `nutrition.uncertainty_band()` computes ranges at the source.
- `log_meal(corrected=...)` records when the human overruled the model.
- `evaluate.py` produces the numbers that justify trust.

The interface is just the visible surface of these guarantees.
