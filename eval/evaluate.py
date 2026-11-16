"""Evaluation harness -- the part almost nobody builds.

We measure the classifier on the Food-101 test set and report honest numbers:

    top-1 accuracy : the single best guess is correct
    top-3 accuracy : the correct dish is in the top 3 guesses
    coverage       : share of dishes we have nutrition data for
    refusals       : share of predictions below our confidence threshold

Run:
    python -m eval.evaluate --limit 1000

Writes eval/results.json so the dashboard/app can display real numbers.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results.json"
CONFIDENCE_THRESHOLD = 0.40

# Food-101 moved to the `ethz` namespace; try the canonical id first, then
# fall back so the harness keeps working across `datasets` versions.
DATASET_IDS = ["ethz/food101", "food101"]


def _load_food101(split: str):
    """Load Food-101 across `datasets` versions (namespace moved to ethz/)."""
    from datasets import load_dataset

    last_error = None
    for dataset_id in DATASET_IDS:
        try:
            return load_dataset(dataset_id, split=split)
        except Exception as exc:  # noqa: BLE001 - try the next id
            last_error = exc
            print(f"  (could not load '{dataset_id}': {type(exc).__name__})")
    raise RuntimeError(f"Could not load Food-101 from {DATASET_IDS}") from last_error


def _iter_hf(limit: int):
    """Yield (PIL image, truth_label) from the Food-101 test split."""
    from src.classify import normalize_label

    ds = _load_food101(f"validation[:{limit}]")
    names = ds.features["label"].names
    for row in ds:
        yield row["image"].convert("RGB"), normalize_label(names[row["label"]])


def _iter_folder(folder: Path):
    """Yield (image, truth) from folder/<label>/*.jpg -- your own photos.

    Layout expected:
        eval_set/pizza/IMG_1.jpg
        eval_set/sushi/IMG_2.jpg
    The folder name is treated as the ground-truth dish (snake_case).
    """
    from PIL import Image

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    for label_dir in sorted(p for p in folder.iterdir() if p.is_dir()):
        truth = label_dir.name.strip().lower().replace("-", "_").replace(" ", "_")
        for img_path in sorted(label_dir.iterdir()):
            if img_path.suffix.lower() in exts:
                yield Image.open(img_path).convert("RGB"), truth


def run(limit: int = 1000, threshold: float = CONFIDENCE_THRESHOLD, folder: str | None = None) -> dict:
    from pathlib import Path as _Path

    from src.classify import classify
    from src.nutrition import lookup

    if folder:
        source = _Path(folder)
        if not source.is_dir():
            raise SystemExit(f"No such folder: {source}")
        print(f"Evaluating on your own images in {source} ...")
        samples = list(_iter_folder(source))
        label = "local folder"
    else:
        print(f"Loading Food-101 test split (limit={limit}) ...")
        samples = list(_iter_hf(limit))
        label = "nateraw/food (Food-101)"

    if not samples:
        raise SystemExit("No images found to evaluate.")

    top1 = 0
    top3 = 0
    covered = 0
    refusals = 0
    latencies = []
    examples = []

    for i, (image, truth) in enumerate(samples):
        started = time.perf_counter()
        preds = classify(image, top_k=5)
        latencies.append(time.perf_counter() - started)

        labels = [p["label"] for p in preds]
        if labels and labels[0] == truth:
            top1 += 1
        if truth in labels[:3]:
            top3 += 1

        if lookup(truth)["_known"]:
            covered += 1

        if preds and preds[0]["score"] < threshold:
            refusals += 1

        if i < 20:
            examples.append(
                {
                    "truth": truth,
                    "predicted": labels[0] if labels else None,
                    "confidence": round(preds[0]["score"], 3) if preds else None,
                    "correct": bool(labels and labels[0] == truth),
                }
            )

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(samples)}  top-1 so far: {top1 / (i + 1):.1%}")

    n = len(samples)
    results = {
        "model": "nateraw/food (Food-101)",
        "source": label,
        "evaluated": n,
        "top1_accuracy": round(top1 / n, 4),
        "top3_accuracy": round(top3 / n, 4),
        "nutrition_coverage": round(covered / n, 4),
        "refusal_rate": round(refusals / n, 4),
        "confidence_threshold": threshold,
        "avg_latency_ms": round(1000 * sum(latencies) / len(latencies), 1),
        "examples": examples,
    }
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--threshold", type=float, default=CONFIDENCE_THRESHOLD)
    parser.add_argument(
        "--folder",
        default=None,
        help="Evaluate on your own photos: folder/<dish>/photo.jpg (skips the 5GB download).",
    )
    args = parser.parse_args()

    results = run(limit=args.limit, threshold=args.threshold, folder=args.folder)
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n=== Results ===")
    print(f"source              : {results['source']}")
    print(f"images evaluated    : {results['evaluated']}")
    print(f"top-1 accuracy      : {results['top1_accuracy']:.1%}")
    print(f"top-3 accuracy      : {results['top3_accuracy']:.1%}")
    print(f"nutrition coverage  : {results['nutrition_coverage']:.1%}")
    print(f"refusal rate        : {results['refusal_rate']:.1%}")
    print(f"avg latency         : {results['avg_latency_ms']} ms/image")
    print(f"\nSaved -> {RESULTS}")


if __name__ == "__main__":
    main()
