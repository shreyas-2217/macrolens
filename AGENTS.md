# AGENTS.md — working notes for this repo

MacroLens: meal photo → dish classification (CV) → macro estimate →
log → analytics dashboard.

## Golden rules

- **Never train a model here.** Use pretrained only. Fine-tuning is a
  deliberate future upgrade, not a task.
- **Honesty over precision.** New numbers must come with ranges or a stated
  uncertainty. No fake-precise calorie values.
- **Keep layers separate.** `classify.py` (model) ← never imports analysis;
  `log.py`/`analyze.py` never import the model. This keeps the fast
  smoke test runnable without torch.

## Layout

| Path | Role |
|---|---|
| `src/classify.py` | pretrained Food-101 → ranked predictions |
| `src/nutrition.py` | dish → macros + uncertainty ranges |
| `src/log.py` | DuckDB persistence (`data/logs.duckdb`) |
| `src/analyze.py` | pandas/SQL aggregations for the dashboard |
| `app/streamlit_app.py` | the UI |
| `eval/evaluate.py` | accuracy on Food-101 test set → `eval/results.json` |
| `eval/smoke_test.py` | fast plumbing checks, **no model needed** |
| `scripts/seed_demo.py` | fill the log with demo meals |
| `data/nutrition_map.csv` | 101 dishes → per-serving macros |

## Commands

```bash
python eval/smoke_test.py          # fast, no model (~2s)
python -m scripts.seed_demo        # populate dashboard demo data
python -m src.classify IMAGE.jpg   # one-image CLI test
python -m eval.evaluate --limit 200
streamlit run app/streamlit_app.py
```

## Conventions

- Import from `src.*` (the app inserts the repo root onto `sys.path`).
- The nutrition map keys are `snake_case` and must match Food-101 labels
  (see `src/classify.normalize_label`).
- SQL lives in `analyze.py`, not in the app.
- All uncertainty constants live in `src/nutrition.py`.

## Adding a dish

Append a row to `data/nutrition_map.csv`:

```
dish_name,kcal,protein_g,carbs_g,fat_g,portion
```

The key must match the Food-101 label with spaces → underscores.
