# Explore the pipeline interactively
#
# Start with plumbing (no model), then step up to real inference.
# Run: jupyter lab  (or convert to a script once you like it)

# %%
from pathlib import Path
import sys

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))

from src.nutrition import lookup, describe
from src import log, analyze

# %% 1. Nutrition map works without any model
pizza = lookup("pizza")
print(pizza)

# %% 2. Honest ranges
d = describe("pizza", portion_multiplier=1.0)
print(d["note"])
print(d["ranges"])

# %% 3. Log a few fake meals to see the dashboard shape
log.reset()
for dish, portion in [("pizza", 1.0), ("sushi", 1.5), ("caesar_salad", 1.0), ("ramen", 1.0)]:
    log.log_meal(dish, dish.title(), 0.9, portion, lookup(dish, portion))

print(analyze.summary())
print(analyze.daily_totals(14))
print(analyze.macro_split())
print(analyze.top_dishes(5))

# %% 4. (After installing torch) classify a real photo
# from PIL import Image
# from src.classify import classify
# img = Image.open(ROOT / "samples" / "your_meal.jpg").convert("RGB")
# for row in classify(img):
#     print(row)
