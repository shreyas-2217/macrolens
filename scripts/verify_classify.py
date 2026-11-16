"""Create a synthetic test image and run the real classifier end to end.

Downloads the pretrained model on first run (cached afterwards).
    python scripts/verify_classify.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402


def make_test_image(path: Path) -> Path:
    """A crude 'pizza-ish' image: tan circle with red dots on a plate."""
    img = Image.new("RGB", (400, 400), (245, 245, 240))
    d = ImageDraw.Draw(img)
    d.ellipse((40, 40, 360, 360), fill=(240, 230, 200), outline=(200, 180, 140), width=4)
    d.ellipse((110, 110, 290, 290), fill=(220, 160, 70))
    for x, y in [(160, 160), (230, 150), (200, 220), (160, 240), (250, 210)]:
        d.ellipse((x - 14, y - 14, x + 14, y + 14), fill=(190, 40, 40))
    d.polygon([(200, 120), (215, 150), (185, 150)], fill=(90, 160, 90))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def main() -> int:
    from src.classify import classify

    sample = make_test_image(ROOT / "samples" / "_test_pizza.png")
    print(f"Test image: {sample}")
    print("Loading model (first run downloads ~350MB)...")

    img = Image.open(sample).convert("RGB")
    preds = classify(img, top_k=5)

    print("\nPredictions:")
    for p in preds:
        bar = "#" * int(p["score"] * 40)
        print(f"  {p['score']:6.1%}  {p['display']:<24} {bar}")

    assert preds, "classify() returned nothing"
    assert preds[0]["score"] >= preds[-1]["score"], "not sorted by confidence"
    print("\nClassifier works end to end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
