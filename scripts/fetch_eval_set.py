"""Fetch a small, real evaluation set from Food-101 without the 5GB download.

Uses the Hugging Face datasets-server HTTP API to pull one image per dish into
an `eval_set/<dish>/` folder, which `eval/evaluate.py --folder eval_set` then
scores.

    python -m scripts.fetch_eval_set --per-class 1

Why this exists: the full Food-101 download is ~5GB and slow. This gets you a
genuine accuracy number in a minute, on real benchmark images.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_SET = ROOT / "eval_set"
API = "https://datasets-server.huggingface.co/rows"


def _get(url: str, retries: int = 4) -> dict:
    """GET JSON with simple exponential backoff for rate limits."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "macrolens-eval"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise last


def _download(url: str, dest: Path, retries: int = 4) -> bool:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "macrolens-eval"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                dest.write_bytes(resp.read())
            return True
        except Exception:  # noqa: BLE001
            time.sleep(1.5 * (attempt + 1))
    return False


def fetch(per_class: int = 1, total: int = 200) -> int:
    # The validation split stores 250 images per class, grouped. So class `c`
    # starts at row c*250 -- fetch a slice per class to get variety.
    first = _get(
        f"{API.replace('/rows', '/first-rows')}?dataset=ethz%2Ffood101&config=default&split=validation"
    )
    names = []
    for f in first.get("features", []):
        if f.get("name") == "label":
            names = f.get("type", {}).get("names", [])

    n_classes = len(names) or 101
    per_dish: dict[str, int] = {}
    saved = 0

    for class_idx in range(n_classes):
        label = names[class_idx].strip().lower().replace("-", "_").replace(" ", "_")
        offset = class_idx * 250
        url = (
            f"{API}?dataset=ethz%2Ffood101&config=default&split=validation"
            f"&offset={offset}&length={per_class}"
        )
        try:
            data = _get(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {label}: {type(exc).__name__}")
            continue

        for row in data.get("rows", []):
            img_meta = row["row"].get("image") or {}
            src = img_meta.get("src")
            if not src:
                continue

            out_dir = EVAL_SET / label
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{label}_{per_dish.get(label, 0)}.jpg"

            if _download(src, out_path):
                per_dish[label] = per_dish.get(label, 0) + 1
                saved += 1

        time.sleep(0.3)

        if class_idx % 20 == 0:
            print(f"  ...{class_idx}/{n_classes} classes, {saved} images")

    return saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-class", type=int, default=1)
    parser.add_argument("--total", type=int, default=220)
    args = parser.parse_args()

    print(f"Fetching ~{args.per_class} image(s) per dish into {EVAL_SET} ...")
    saved = fetch(per_class=args.per_class, total=args.total)
    print(f"Saved {saved} images across {len(list(EVAL_SET.iterdir())) if EVAL_SET.exists() else 0} dishes.")
    print("Now run:  python -m eval.evaluate --folder eval_set")


if __name__ == "__main__":
    main()
