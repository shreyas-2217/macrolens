"""Meal photo -> dish classification using a PRETRAINED model.

No training. We load a Food-101 classifier from Hugging Face and run
inference. Everything returns a ranked list of (label, confidence) so the
UI can be honest about uncertainty instead of faking certainty.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# A ViT model fine-tuned on Food-101 (101 dish classes).
# Swap this for any Hugging Face image-classification model if you like.
MODEL_ID = "nateraw/food"


def normalize_label(label: str) -> str:
    """'Apple Pie' -> 'apple_pie' so labels match the nutrition map keys."""
    return label.strip().lower().replace("-", "_").replace(" ", "_")


def display_name(label: str) -> str:
    """'apple_pie' -> 'Apple Pie' for a friendly UI."""
    return label.replace("_", " ").strip().title()


@lru_cache(maxsize=1)
def load_classifier():
    """Load and cache the pretrained pipeline (downloads once, then cached)."""
    from transformers import pipeline

    # top_k=None returns ALL classes with scores, which we need for honest UI.
    return pipeline(
        "image-classification",
        model=MODEL_ID,
        top_k=None,
    )


def classify(image, top_k: int = 5) -> list[dict]:
    """Classify a PIL image.

    Returns a ranked list like:
        [{"label": "apple_pie", "display": "Apple Pie", "score": 0.82}, ...]
    """
    clf = load_classifier()
    raw = clf(image)

    # Some pipelines return a dict for a single result; normalize to a list.
    if isinstance(raw, dict):
        raw = [raw]

    ranked = sorted(raw, key=lambda r: r["score"], reverse=True)[:top_k]
    return [
        {
            "label": normalize_label(r["label"]),
            "display": display_name(normalize_label(r["label"])),
            "score": float(r["score"]),
        }
        for r in ranked
    ]


def top_prediction(image) -> dict:
    """Convenience: the single best guess plus its confidence."""
    return classify(image, top_k=1)[0]


if __name__ == "__main__":
    import sys

    from PIL import Image

    if len(sys.argv) < 2:
        print("Usage: python -m src.classify path/to/meal.jpg")
        raise SystemExit(1)

    path = Path(sys.argv[1])
    img = Image.open(path).convert("RGB")
    for row in classify(img):
        print(f"{row['score']:6.1%}  {row['display']}")
