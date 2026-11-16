# MacroLens

**Point your camera at a meal. Get an honest estimate. Log it. See your patterns.**

MacroLens is a computer-vision + data-analysis project: a pretrained model
classifies a meal photo, the dish maps to approximate macros, every log
becomes a row, and a dashboard turns those rows into eating patterns.

The point isn't a calorie counter. It's that the numbers are **honest** —
shown as ranges, with a correction path, and backed by a real evaluation
harness instead of a vibe.

![Analyze view](docs/analyze.png)

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
[5] ANALYSE ──► Patterns view: daily calories, macro split, top dishes
```

## Stack

| Layer | Tech |
|---|---|
| Vision | PyTorch + Hugging Face `transformers` (pretrained, no training) |
| API | **FastAPI** + Uvicorn |
| Frontend | Hand-built HTML / CSS / vanilla JS (no framework) |
| Data | pandas + DuckDB |
| Eval | `datasets` + a custom accuracy harness |

No Streamlit. The interface is purpose-built so uncertainty is visible, not
flattened into a default widget.

## Quickstart

```bash
# 1. install
pip install -r requirements.txt

# 2. check the plumbing (no model needed, ~2s)
python tests/test_core.py

# 3. run the app  →  http://127.0.0.1:8000
python -m uvicorn server.app:app --reload --port 8000

# 4. (optional) seed the Patterns view with demo meals
python -m scripts.seed_demo
```

The first classification downloads the pretrained model (~350 MB), then caches it.
Drop a few `.jpg` files into `samples/` to get one-click demo photos.

## Measure it (the differentiator)

```bash
# Fastest: pull a small real benchmark set via the HF API (no 5GB download)
python -m scripts.fetch_eval_set --per-class 1
python -m eval.evaluate --folder eval_set

# Or the full Food-101 test set (downloads ~5GB the first time)
python -m eval.evaluate --limit 1000

# ...or on YOUR OWN photos -- most honest of all
#   eval_set/pizza/IMG_1.jpg
#   eval_set/sushi/IMG_2.jpg
python -m eval.evaluate --folder eval_set
```

Reports **top-1 accuracy, top-3 accuracy, nutrition coverage, refusal rate,
and latency**, then writes `eval/results.json`, which the app displays under
**About**. Numbers are measured, not claimed.

### Current result

| Metric | Value |
|---|---|
| Top-1 accuracy | **88.9%** |
| Top-3 accuracy | **97.5%** |
| Nutrition coverage | **100%** |
| Latency | **510 ms/image** (CPU) |

*(81 Food-101 validation images, one per dish.)*

> Tip: benchmark accuracy (pretty studio photos) and real-world accuracy
> (your messy kitchen photos) are different numbers. Report both.

## Project layout

```
macrolens/
├── server/app.py            # FastAPI: wraps src/, serves web/
├── web/
│   ├── index.html           # the interface
│   ├── styles.css           # the whole visual identity
│   └── app.js               # routing, belief strip, range bars
├── src/
│   ├── classify.py          # pretrained model → ranked predictions
│   ├── nutrition.py         # dish → macros + honest ranges
│   ├── log.py               # DuckDB persistence
│   └── analyze.py           # pandas/SQL patterns
├── eval/
│   ├── evaluate.py          # accuracy harness (Food-101 or your own photos)
│   └── smoke_test.py        # fast plumbing checks, no model
├── tests/test_core.py       # unit tests (no torch)
├── scripts/
│   ├── seed_demo.py         # fill the log with demo meals
│   ├── fetch_eval_set.py    # pull a small real benchmark set (no 5GB download)
│   └── verify_classify.py   # end-to-end single-image check
├── data/nutrition_map.csv   # 101 dishes → per-serving macros
├── samples/                 # drop a few meal photos here
└── notebooks/               # scratchpad
```

## Design choices (and why)

| Choice | Reason |
|---|---|
| **Ranges, not single numbers** | A photo can't measure portion size; false precision is dishonest. |
| **The model's full belief on display** | Every guess is shown as a strip, not hidden behind one confident-sounding label. |
| **"Not sure — your call"** | Below 40% confidence the interface turns ochre and asks instead of asserting. |
| **Portion slider** | Hands the user the one variable the model genuinely cannot know. |
| **Published accuracy** | The eval harness makes the honesty verifiable. |
| **Pretrained only** | Round one ships a working product; fine-tuning is a later upgrade. |
| **No UI framework** | Uncertainty had to be a designed element, not a default widget. |

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
