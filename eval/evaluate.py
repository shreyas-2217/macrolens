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


def run(limit: int = 1000, threshold: float = CONFIDENCE_THRESHOLD) -> dict:
    from datasets import load_dataset

    from src.classify import classify, normalize_label
    from src.nutrition import lookup

    print(f"Loading Food-101 test split (limit={limit}) ...")
    ds = load_dataset("food101", split=f"validation[:{limit}]")

    label_names = ds.features["label"].names

    top1 = 0
    top3 = 0
    covered = 0
    refusals = 0
    latencies = []
    examples = []

    for i, row in enumerate(ds):
        image = row["image"].convert("RGB")
        truth = normalize_label(label_names[row["label"]])

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
            print(f"  {i + 1}/{limit}  top-1 so far: {top1 / (i + 1):.1%}")

    n = len(ds)
    results = {
        "model": "nateraw/food (Food-101)",
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
    args = parser.parse_args()

    results = run(limit=args.limit, threshold=args.threshold)
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n=== Results ===")
    print(f"top-1 accuracy      : {results['top1_accuracy']:.1%}")
    print(f"top-3 accuracy      : {results['top3_accuracy']:.1%}")
    print(f"nutrition coverage  : {results['nutrition_coverage']:.1%}")
    print(f"refusal rate        : {results['refusal_rate']:.1%}")
    print(f"avg latency         : {results['avg_latency_ms']} ms/image")
    print(f"\nSaved -> {RESULTS}")


if __name__ == "__main__":
    main()
