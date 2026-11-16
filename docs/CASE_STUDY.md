# Case study: MacroLens

*A computer-vision project where the hard part isn't the model — it's being
honest about what the model can't know.*

---

## The friction

Calorie-tracking apps ask you to search a database and guess a portion. It's
tedious, so people quit. The obvious fix is a photo: snap your plate, get the
number. But a photo **cannot tell you how much food is on the plate** — and
every app that prints a confident "540 kcal" from a picture is quietly
inventing precision it doesn't have.

That gap — between what an image shows and what a number claims — is the
whole project.

## What I built

MacroLens takes a meal photo and:

1. **Classifies the dish** with a pretrained Food-101 model.
2. **Maps it to macros** from a per-serving nutrition table.
3. **Asks the user for the portion** — the one variable the image genuinely
   cannot supply — via a slider, and shows **ranges** instead of one number.
4. **Logs a row** for every meal.
5. **Analyses the log** in a dashboard: daily calories, macro split,
   most-logged dishes.

If the model isn't confident, it doesn't guess. It says *"not sure — tell me
what this is"* and moves on.

## The interesting decisions

| Decision | Why |
|---|---|
| **Ranges, not point estimates** | ±20% band reflects real portion uncertainty. A number without an error bar is a lie with decimal places. |
| **A correction path, always** | Every prediction is editable. Corrections are logged, so the app measures how often it was overruled. |
| **Refuse when unsure** | Below a confidence threshold, the UI asks instead of asserting. "Graceful way out" as a default, not an exception. |
| **Pretrained, not trained** | Round one ships a working product. Fine-tuning is a named, later upgrade — not a reason to stall. |
| **A published eval harness** | `eval/evaluate.py` reports top-1/top-3 accuracy, coverage, and refusal rate on the Food-101 test set. Trust is measured, not asserted. |

## What I'd tell someone starting this

- **Don't train.** A pretrained classifier is a one-liner. The multi-week
  GPU rabbit hole can be a v2 problem; shipping is a v1 problem.
- **The portion is the whole ballgame.** Model architecture barely matters
  next to the fact that a JPEG can't measure grams. Lean into it.
- **Report two accuracies:** the benchmark number and the number on your own
  messy kitchen photos. They are not the same, and pretending they are is the
  exact dishonesty this project is about.

## Numbers

*(Real run: 81 Food-101 validation images, one per dish, fetched via the HF API.)*

| Metric | Value |
|---|---|
| Top-1 accuracy | **88.9%** |
| Top-3 accuracy | **97.5%** |
| Nutrition coverage | **100%** |
| Refusal rate | 0.0% |
| Latency | **510 ms/image** (CPU) |

Reproduce: `python -m scripts.fetch_eval_set --per-class 1 && python -m eval.evaluate --folder eval_set`

## Stack

Python · PyTorch · Hugging Face `transformers` · **FastAPI** · pandas · DuckDB ·
a hand-built HTML/CSS/JS frontend (no UI framework)

## The interface

The design is built in the visual language of a nutrition-facts panel — heavy
rules, uppercase micro-labels, right-aligned figures — then subverted so that
**uncertainty is the most prominent thing on screen**:

- a **belief strip** showing the model's distribution across all its guesses;
- every macro drawn as a **range band**, never a lone figure;
- an ochre **"Not sure — your call"** state that asks instead of asserting.

## Links

- Live app: *(URL)*
- Code: *(GitHub URL)*
