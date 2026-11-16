# MacroLens

**Point your camera at a meal. Get an honest estimate. Log it. See your patterns.**

MacroLens is a computer-vision + data-analysis project: a pretrained model
classifies a meal photo, the dish maps to approximate macros, every log
becomes a row, and a dashboard turns those rows into eating patterns.

The point isn't a calorie counter. It's that the numbers are **honest** —
shown as ranges, with a correction path, and backed by a real evaluation
harness instead of a vibe.

---

## How it works

```
📷 meal photo
   │
   ▼
[1] CV  ──────► pretrained Food-101 classifier → "pizza, 82%"
   │
   ▼
[2] MAP ──────► dish → approximate macros per serving
   │
   ▼
[3] ADJUST ───► you set the portion (the one thing a photo can't know)
   │
   ▼
[4] LOG ──────► one row in DuckDB
   │
   ▼
[5] ANALYSE ──► Streamlit dashboard: daily calories, macro split, top dishes
```

## Quickstart

```bash
# 1. install
pip install -r requirements.txt

# 2. check the plumbing (no model needed, ~2s)
python eval/smoke_test.py

# 3. classify your own photo from the CLI
python -m src.classify path/to/your/meal.jpg

# 4. run the app
streamlit run app/streamlit_app.py
```

The first classification downloads the pretrained model (~350 MB), then caches it.

## Measure it (the differentiator)

```bash
python -m eval.evaluate --limit 1000
```

Reports **top-1 accuracy, top-3 accuracy, nutrition coverage, refusal rate,
and latency** on the Food-101 test set, then writes `eval/results.json`,
which the app displays under **About**. Numbers are measured, not claimed.

## Project layout

```
macrolens/
├── app/streamlit_app.py     # the UI
├── src/
│   ├── classify.py          # pretrained model → ranked predictions
│   ├── nutrition.py         # dish → macros + honest ranges
│   ├── log.py               # DuckDB persistence
│   └── analyze.py           # pandas/SQL patterns
├── eval/
│   ├── evaluate.py          # accuracy harness (Food-101 test set)
│   └── smoke_test.py        # fast plumbing checks, no model
├── data/nutrition_map.csv   # 101 dishes → per-serving macros
├── samples/                 # drop a few meal photos here
└── notebooks/               # scratchpad
```

## Design choices (and why)

| Choice | Reason |
|---|---|
| **Ranges, not single numbers** | A photo can't measure portion size; false precision is dishonest. |
| **"Not sure? You tell us"** | Low-confidence predictions ask instead of guessing. |
| **Portion slider** | Hands the user the one variable the model genuinely cannot know. |
| **Published accuracy** | The eval harness makes the honesty verifiable. |
| **Pretrained only** | Round one ships a working product; fine-tuning is a later upgrade. |

## Known limits

- Single-label: one main dish per photo (no multi-food plates yet).
- Portion is user-supplied; macro values are per standard serving.
- Food-101 is studio-style imagery — real phone photos are messier, so
  expect lower accuracy than the benchmark on your own kitchen.

## Roadmap

- [ ] Multi-food detection (bounding boxes per item)
- [ ] Open Food Facts API for a wider dish/brand catalogue
- [ ] Weekly email/CSV export of the log
- [ ] A public accuracy page that updates on every eval run
