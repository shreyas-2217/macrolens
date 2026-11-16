"""MacroLens - Streamlit app.

Point your camera at a meal, get an honest estimate, log it, and see your
patterns over time.

Run from the project root:
    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `src` importable when Streamlit runs this file directly.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from PIL import Image

from src import analyze, log
from src.classify import classify
from src.nutrition import describe

CONFIDENCE_THRESHOLD = 0.40
DISH_OPTIONS = sorted(
    {
        line.split(",")[0]
        for line in (ROOT / "data" / "nutrition_map.csv").read_text(encoding="utf-8").splitlines()[1:]
        if line.strip()
    }
)

st.set_page_config(page_title="MacroLens", page_icon="🍽️", layout="wide")

st.title("🍽️ MacroLens")
st.caption(
    "Point at a meal → estimate the macros → log it → see your patterns. "
    "Estimates are ranges, not false precision."
)

tab_log, tab_dashboard, tab_about = st.tabs(["📷 Log a meal", "📊 Patterns", "ℹ️ About"])

# ---------------------------------------------------------------- log a meal
with tab_log:
    col_input, col_result = st.columns([1, 1], gap="large")

    with col_input:
        st.subheader("1. Add a photo")
        source = st.radio(
            "Image source", ["Upload", "Sample images"], horizontal=True, label_visibility="collapsed"
        )

        image = None
        if source == "Upload":
            upload = st.file_uploader("Meal photo", type=["jpg", "jpeg", "png", "webp"])
            if upload:
                image = Image.open(upload).convert("RGB")
        else:
            samples = sorted((ROOT / "samples").glob("*.jpg")) + sorted(
                (ROOT / "samples").glob("*.png")
            )
            if samples:
                choice = st.selectbox("Pick a sample", [p.name for p in samples])
                image = Image.open(ROOT / "samples" / choice).convert("RGB")
            else:
                st.info("Drop some .jpg files into `samples/` to use this mode.")

        if image is not None:
            st.image(image, caption="Your meal", use_container_width=True)

    with col_result:
        st.subheader("2. What we think it is")

        if image is None:
            st.info("Add a photo to get a prediction.")
        else:
            with st.spinner("Looking at your plate..."):
                predictions = classify(image, top_k=5)

            best = predictions[0]

            # Honest low-confidence path: ask, don't guess.
            if best["score"] < CONFIDENCE_THRESHOLD:
                st.warning(
                    f"Not confident (best guess **{best['display']}**, "
                    f"{best['score']:.0%}). Tell us what it is:"
                )
                dish = st.selectbox("This looks like...", DISH_OPTIONS)
                confidence = best["score"]
                corrected = True
            else:
                st.success(f"**{best['display']}** — {best['score']:.0%} confident")
                dish = st.selectbox(
                    "Dish",
                    DISH_OPTIONS,
                    index=DISH_OPTIONS.index(best["label"])
                    if best["label"] in DISH_OPTIONS
                    else 0,
                )
                confidence = best["score"]
                corrected = dish != best["label"]

            with st.expander("Top 5 guesses (how sure the model is)"):
                for p in predictions:
                    st.write(f"{p['score']:6.1%} · {p['display']}")
                    st.progress(min(p["score"], 1.0))

            st.subheader("3. Portion")
            st.caption("A photo can't measure grams — so you adjust this. Default is a standard serving.")
            portion = st.slider("Portion multiplier", 0.5, 2.0, 1.0, step=0.25)

            info = describe(dish, portion)

            if info["_known"]:
                lo, hi = info["ranges"]["kcal"]
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Calories", f"{lo:.0f}–{hi:.0f}")
                c2.metric("Protein", f"{info['protein_g']:.0f} g")
                c3.metric("Carbs", f"{info['carbs_g']:.0f} g")
                c4.metric("Fat", f"{info['fat_g']:.0f} g")
                st.caption(info["note"])
            else:
                st.info(
                    "We don't have nutrition data for this dish yet. "
                    "It will still be logged, but excluded from calorie totals."
                )

            if st.button("✅ Log this meal", type="primary", use_container_width=True):
                log.log_meal(
                    dish=dish,
                    display=dish.replace("_", " ").title(),
                    confidence=confidence,
                    portion_multiplier=portion,
                    macros=info,
                    corrected=corrected,
                )
                st.success(f"Logged {dish.replace('_', ' ').title()}.")
                st.balloons()

# ----------------------------------------------------------------- dashboard
with tab_dashboard:
    st.subheader("Your eating patterns")
    s = analyze.summary()

    if s["meals"] == 0:
        st.info("No meals logged yet. Log a few on the first tab and come back.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Meals logged", s["meals"])
        c2.metric("Avg kcal / meal", f"{s['avg_kcal']:.0f}")
        c3.metric("Avg confidence", f"{s['avg_confidence']:.0%}")
        c4.metric("Times you corrected the model", s["corrections"])

        st.divider()

        left, right = st.columns(2)
        with left:
            st.markdown("**Calories per day (last 14 days)**")
            daily = analyze.daily_totals(14)
            if daily is not None and not daily.empty:
                st.bar_chart(daily.set_index("day")["kcal"])
            else:
                st.caption("No recent data.")

        with right:
            st.markdown("**Macro split (total grams)**")
            split = analyze.macro_split()
            st.bar_chart(
                pd.DataFrame(
                    {"grams": [split["protein_g"], split["carbs_g"], split["fat_g"]]},
                    index=["Protein", "Carbs", "Fat"],
                )
            )

        st.markdown("**Most-logged dishes**")
        top = analyze.top_dishes(5)
        if top is not None and not top.empty:
            top = top.rename(
                columns={"display": "Dish", "count": "Times", "avg_kcal": "Avg kcal"}
            )
            st.dataframe(top, use_container_width=True, hide_index=True)

        with st.expander("Raw log"):
            st.dataframe(analyze.load_meals(), use_container_width=True, hide_index=True)

# --------------------------------------------------------------------- about
with tab_about:
    st.markdown(
        """
### How this works

1. **See** — a pretrained Food-101 classifier names the dish.
2. **Convert** — the dish maps to approximate macros per serving.
3. **Adjust** — you set the portion (the one thing a photo can't know).
4. **Analyse** — every log becomes a row the dashboard analyses.

### Why ranges instead of one number

A photo cannot measure how much food is on the plate. Rather than print a
fake-precise "540 kcal", MacroLens shows a range and lets you correct it.
If the model isn't confident, it **asks first** instead of guessing.

### Measured, not claimed

`eval/evaluate.py` scores the classifier on the Food-101 test set
(top-1 / top-3 accuracy, nutrition coverage, refusal rate) so the numbers
here are verifiable, not vibes.
        """
    )
    results_path = ROOT / "eval" / "results.json"
    if results_path.exists():
        import json

        st.markdown("**Latest evaluation:**")
        st.json(json.loads(results_path.read_text(encoding="utf-8")))
    else:
        st.caption("Run `python -m eval.evaluate` to generate accuracy results.")
