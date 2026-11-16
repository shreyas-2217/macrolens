# Portfolio entry (ready to paste)

Add this to the `projects` array in
`C:\Users\user\Documents\portfolio\src\data\site.js`.

> **Status: already added** as project `03` (`id: "macrolens"`, `size:
> "featured"`). It is placed third because a 2×2 tile in that slot is the only
> arrangement that leaves zero holes in the 4-column grid. The `Live app` link
> still points at the `MACROLENS_APP_URL` placeholder — set it to the deployed
> URL once the app is hosted.

```js
{
  id: "macrolens",
  number: "03",
  title: "MacroLens",
  subtitle: "Meal photo → nutrition analytics",
  discipline: "Computer Vision + Data",
  year: "2026",
  accent: "olive",
  size: "featured",
  summary:
    "A calorie counter that admits what a photo can't know. A pretrained model names the dish, the interface shows ranges instead of fake-precise numbers, and every log becomes an eating pattern you can act on.",
  highlights: [
    "Pretrained Food-101 classifier, no training",
    "88.9% top-1 / 97.5% top-3 on the Food-101 benchmark",
    "Honest ±20% ranges + a correction path",
  ],
  stack: ["PyTorch", "FastAPI", "pandas", "DuckDB", "Python"],
  links: [
    { label: "Live app", href: "MACROLENS_APP_URL", type: "live" },
    { label: "Code", href: "https://github.com/shreyas-2217/macrolens", type: "code" },
  ],
},
```

## Résumé bullet (one line)

> **MacroLens** — CV nutrition tracker. Classifies meal photos with a
> pretrained Food-101 **ViT** and maps dishes to macro ranges, then analyses
> eating patterns in a hand-built FastAPI + vanilla JS dashboard (no
> framework, no build step). Measured **88.9% top-1 / 97.5% top-3** on 81
> Food-101 validation images, with a confidence-gated correction path instead
> of fake-precise calorie counts.
> `Python · PyTorch · FastAPI · pandas · DuckDB`

## Interview talking points (3 sentences)

1. "It's a photo-to-nutrition project, but the interesting part is what a
   photo *can't* tell you — portion size — so the product shows ranges and
   lets you correct it."
2. "I shipped it with an evaluation harness that scores the classifier against
   real Food-101 validation images, because I wanted my accuracy claim to be
   checkable, not a vibe."
3. "The model half is pretrained; the value I added is the honest interface,
   the evaluation harness, and the analysis pipeline that turns logs into
   patterns."

## Accuracy note (say this, don't overclaim)

- The benchmark is **81 images**, not the full 25,250-image Food-101 test set.
  Say "88.9% top-1 on an 81-image validation slice" — do not say "on
  Food-101" without the slice size if someone asks how it was measured.
- Architecture is a **ViT** (`ViTForImageClassification`, `nateraw/food`),
  not a CNN.
- The frontend is **not** Streamlit. It is vanilla JS against FastAPI, which is
  the deliberate portfolio signal: no framework, no build step.
