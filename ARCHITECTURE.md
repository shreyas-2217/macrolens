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
| `app/streamlit_app.py` | The product surface | all of the above |
| `eval/evaluate.py` | Score the classifier on Food-101 test | datasets, classify, nutrition |

## Data flow, concretely

1. An image arrives as a `PIL.Image`.
2. `classify()` returns `[{"label": "pizza", "score": 0.82}, ...]`.
3. `nutrition.describe("pizza", portion=1.0)` returns macros **and ranges**.
4. `log.log_meal(...)` inserts a row.
5. `analyze.*` aggregates rows for the dashboard.

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
