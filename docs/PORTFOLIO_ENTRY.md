# Portfolio entry (ready to paste)

Add this to the `projects` array in
`C:\Users\user\Documents\portfolio\src\data\site.js` when the project is
deployed, so it appears in the "Selected Work" section.

```js
{
  id: "macrolens",
  number: "06",
  title: "MacroLens",
  subtitle: "Meal photo → nutrition analytics",
  discipline: "Computer Vision + Data",
  year: "2026",
  accent: "orange",
  size: "wide",
  summary:
    "Point your camera at a meal, get an honest macro estimate as a range, log it, and watch your eating patterns build up in a dashboard. A pretrained model names the dish; you set the portion it can't see.",
  highlights: [
    "Pretrained Food-101 classifier, no training",
    "Honest ±20% ranges + low-confidence correction path",
    "Published eval harness: top-1/top-3 accuracy on the test set",
  ],
  stack: ["Python", "PyTorch", "transformers", "pandas", "DuckDB", "Streamlit"],
  links: [
    { label: "Live app", href: "STREAMLIT_URL_HERE", type: "live" },
    { label: "Code", href: "GITHUB_URL_HERE", type: "code" },
  ],
},
```

## Résumé bullet (one line)

> **MacroLens** — CV nutrition tracker. Classifies meal photos with a
> pretrained CNN, maps dishes to macro ranges, and analyses eating patterns
> in a Streamlit dashboard. Ships an evaluation harness (87% top-3) and a
> correction path instead of fake-precise calorie counts.
> `Python · PyTorch · pandas · DuckDB · Streamlit`

*(Replace 87% with your real number from `eval/results.json`.)*

## Interview talking points (3 sentences)

1. "It's a photo-to-nutrition project, but the interesting part is what a
   photo *can't* tell you — portion size — so the product shows ranges and
   lets you correct it."
2. "I shipped it with an evaluation harness that scores the classifier on the
   Food-101 test set, because I wanted my accuracy claim to be checkable, not
   a vibe."
3. "The model half is pretrained; the value I added is the honest interface
   and the analysis pipeline that turns logs into patterns."
