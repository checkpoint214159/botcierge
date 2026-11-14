"""Generate synthetic training data for the Botcierge models.

Outputs (in source/ml/data/):
  task_descriptions.csv  free-text chore descriptions -> task_category   (M1)
                         with a `split` column (train/test) and a `source`
                         column (seed, paraphrase, augmented, template)
  task_specs.csv         structured task specs -> platform, add-ons,
                         skill pack, robot-hours                          (M2-M5)

M1 text comes from two sources:
  1. seed_requests/<category>.txt: hand-written customer requests (written by
     an LLM, Claude, from general knowledge of how people phrase requests to
     cleaners, handymen and home-service apps in Singapore; no posts were
     copied). Each seed may be followed by "~" paraphrases of it.
  2. The old template generator (TEXT_SLOTS below), kept as a smaller share.
A quarter of the seed groups per category are held out as the test set. Only
the original seed text of those groups is used, and their paraphrases are
dropped, so no reworded copy of a test request is ever trained on.

The labelling rules for M2-M5 stand in for what an operations team would
decide by hand on historical jobs. Noise is injected so the models have to
generalise rather than memorise a lookup table.

Run:  python source/ml/generate_data.py
"""
from pathlib import Path
import random

import numpy as np
import pandas as pd

from taxonomy import ADDONS, FLOOR_TYPES, HOUSING_TYPES, TASK_CATEGORIES

SEED = 2108
rng = np.random.default_rng(SEED)
random.seed(SEED)
OUT = Path(__file__).parent / "data"

# --------------------------------------------------------------------------
# M1: free-text descriptions
# --------------------------------------------------------------------------
# --- M1 part 1: template generator (the original approach) ---
# Fills opener + verb + object + context + filler from fixed word lists. Easy to
# separate, so on its own it gave a meaningless ~100% test score. It is now only a
# small share of the training data and is never used for testing.
TEXT_SLOTS = {
    "floor_cleaning": {
        "verbs": ["vacuum", "mop", "clean", "sweep", "scrub", "wash", "deep clean"],
        "objects": ["the floors", "my flat", "the living room", "all the rooms", "the kitchen floor",
                    "the whole house", "the tiles", "the parquet", "the carpet", "the bedroom floors"],
        "context": ["before we move out", "after renovation, lots of dust", "every week",
                    "my dog sheds a lot", "for a move-in clean", "after a party", "it's very dusty",
                    "before chinese new year", "before the landlord inspection"],
    },
    "window_cleaning": {
        "verbs": ["clean", "wipe", "wash", "squeegee", "polish"],
        "objects": ["the windows", "the glass panels", "the balcony glass", "the sliding doors",
                    "the outside of my windows", "the high windows", "the glass facade of my shop"],
        "context": ["they are very high up", "streaky from the rain", "on the 20th floor",
                    "cannot reach safely", "before guests come", "once a month"],
    },
    "lawn_care": {
        "verbs": ["mow", "trim", "cut", "maintain", "edge"],
        "objects": ["the lawn", "the grass", "the garden", "the backyard", "the front yard",
                    "the turf around the house"],
        "context": ["it's overgrown", "every two weeks", "while we are overseas",
                    "the grass is getting long", "before the open house", "weekly"],
    },
    "pool_cleaning": {
        "verbs": ["clean", "scrub", "vacuum", "skim", "maintain"],
        "objects": ["the pool", "the swimming pool", "the pool floor", "the pool walls",
                    "the jacuzzi", "the plunge pool"],
        "context": ["full of leaves", "algae on the walls", "before the weekend",
                    "weekly maintenance", "it's turning green"],
    },
    "tidying": {
        "verbs": ["tidy", "declutter", "organise", "put away", "sort", "pick up", "fold"],
        "objects": ["the toys", "the kids' room", "the laundry", "the clothes", "the shelves",
                    "the storeroom", "boxes after moving", "books and magazines", "the dishes"],
        "context": ["the kids leave everything everywhere", "after moving in",
                    "it's a mess every evening", "need things sorted into bins",
                    "I don't have time", "every night"],
    },
    "elder_care": {
        "verbs": ["keep an eye on", "check on", "accompany", "remind", "assist", "watch over"],
        "objects": ["my grandmother", "my elderly father", "my mum", "my grandparents",
                    "an elderly relative living alone", "my dad who uses a walker"],
        "context": ["while I'm at work", "remind her to take medicine", "in case he falls",
                    "fetch water and things for her", "she gets lonely during the day",
                    "alert me if something happens"],
    },
    "event_serving": {
        "verbs": ["serve", "carry", "hand out", "bring around", "deliver"],
        "objects": ["drinks", "food trays", "canapes", "snacks to guests", "dishes to tables",
                    "cake at the party"],
        "context": ["at my house party", "for a birthday party", "during a wedding dinner at home",
                    "for 40 guests", "at our shop opening", "during the open house"],
    },
    "home_patrol": {
        "verbs": ["patrol", "guard", "monitor", "watch", "check"],
        "objects": ["the house", "the compound", "the perimeter", "the shop at night",
                    "the garden and gate", "the property"],
        "context": ["while we are on holiday", "at night", "there were break-ins nearby",
                    "send me alerts", "check doors are locked", "during the week we're away"],
    },
}
OPENERS = ["", "", "I need a robot to ", "can you help me ", "looking for something to ",
           "want to ", "need help to ", "pls ", "hi, I want to "]
FILLER = ["", "", "", " thanks", " asap", " on weekends", " if possible", " budget is tight"]


def make_description(category: str) -> str:
    s = TEXT_SLOTS[category]
    text = f"{random.choice(OPENERS)}{random.choice(s['verbs'])} {random.choice(s['objects'])}"
    if random.random() < 0.8:
        text += f", {random.choice(s['context'])}"
    text += random.choice(FILLER)
    # ~15% of rows borrow an object from another category to blur the boundaries
    if random.random() < 0.15:
        other = random.choice([c for c in TASK_CATEGORIES if c != category])
        text += f" and maybe {random.choice(TEXT_SLOTS[other]['objects'])}"
    return text


def gen_descriptions(n_per_class: int = 400) -> pd.DataFrame:
    rows = [{"description": make_description(c), "task_category": c}
            for c in TASK_CATEGORIES for _ in range(n_per_class)]
    return pd.DataFrame(rows).sample(frac=1, random_state=SEED).reset_index(drop=True)


# --- M1 part 2: hand-written seed requests, paraphrases and augmentation ---
SEED_DIR = Path(__file__).parent / "seed_requests"
TEST_GROUP_FRACTION = 0.25    # share of seed groups per category held out for testing
TEMPLATES_PER_CLASS = 100     # template rows kept per class, so they are a minority
AUGMENTED_PER_ROW = 2         # noisy copies made of each training seed/paraphrase

# Separate RNG for everything in this section. The global `random` and `rng` are
# shared with gen_specs(), so drawing from them here would change task_specs.csv
# (the M2-M5 data) even though M2-M5 have nothing to do with the text.
text_rng = random.Random(SEED)


def load_seed_requests() -> pd.DataFrame:
    """Read seed_requests/<category>.txt into rows of (group, category, text, source).

    A plain line starts a new group (one customer request). A "~" line is a
    paraphrase of the seed above it and joins that group, so the split below can
    keep a seed and its rewordings on the same side.
    """
    rows = []
    for category in TASK_CATEGORIES:
        group = -1
        for line in (SEED_DIR / f"{category}.txt").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("~"):
                rows.append({"group": f"{category}-{group}", "task_category": category,
                             "description": line[1:].strip(), "source": "paraphrase"})
            else:
                group += 1
                rows.append({"group": f"{category}-{group}", "task_category": category,
                             "description": line, "source": "seed"})
    return pd.DataFrame(rows)


def pick_test_groups(corpus: pd.DataFrame) -> set:
    """Hold out TEST_GROUP_FRACTION of the groups in each category (stratified by class)."""
    test = set()
    for category in TASK_CATEGORIES:
        groups = sorted(corpus.loc[corpus["task_category"] == category, "group"].unique())
        text_rng.shuffle(groups)
        test.update(groups[:round(len(groups) * TEST_GROUP_FRACTION)])
    return test


# How people shorten words when typing on a phone.
CHAT_ABBREVIATIONS = {"please": "pls", "you": "u", "your": "ur", "tomorrow": "tmr", "before": "b4",
                      "because": "cos", "with": "w", "thanks": "thx", "need": "nd", "the": "da",
                      "and": "n", "my": "me", "every": "evry", "weekend": "wkend"}


def add_noise(text: str) -> str:
    """Cheap, deterministic typing noise: real users mistype, skip words and shout.

    Applies one or two of: swap two adjacent letters, drop a letter, drop a word,
    chat-style abbreviations, strip punctuation. (No case changes: TF-IDF lower-cases
    everything, so they would teach the model nothing.)
    """
    for _ in range(text_rng.choice([1, 1, 2])):
        words = text.split()
        op = text_rng.choice(["swap", "drop_char", "drop_word", "abbrev", "no_punct"])
        long_words = [i for i, w in enumerate(words) if len(w) > 3]
        if op in ("swap", "drop_char") and long_words:
            i = text_rng.choice(long_words)
            w = words[i]
            j = text_rng.randrange(len(w) - 1)
            words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:] if op == "swap" else w[:j] + w[j + 1:]
        elif op == "drop_word" and len(words) > 3:
            del words[text_rng.randrange(len(words))]
        elif op == "abbrev":
            words = [CHAT_ABBREVIATIONS.get(w.lower(), w) for w in words]
        elif op == "no_punct":
            words = [w.strip(".,!?") for w in words]
        text = " ".join(w for w in words if w)
    return text


def build_m1_dataset(templates: pd.DataFrame) -> pd.DataFrame:
    corpus = load_seed_requests()
    test_groups = pick_test_groups(corpus)
    in_test = corpus["group"].isin(test_groups)

    # Test: only the original wording of held-out seeds; their paraphrases are thrown away.
    test = corpus[in_test & (corpus["source"] == "seed")].assign(split="test")

    # Train: the other seeds and their paraphrases, plus noisy copies of both.
    train = corpus[~in_test].assign(split="train")
    noisy = train.loc[train.index.repeat(AUGMENTED_PER_ROW)].copy()
    noisy["description"] = [add_noise(t) for t in noisy["description"]]
    noisy["source"] = "augmented"

    # A minority of template rows keeps vocabulary like "facade" or "perimeter" in play.
    tmpl = (templates.groupby("task_category").head(TEMPLATES_PER_CLASS)
            .assign(split="train", source="template", group=""))

    cols = ["description", "task_category", "split", "source", "group"]
    out = pd.concat([train, noisy, tmpl, test])[cols]
    return out.sample(frac=1, random_state=SEED).reset_index(drop=True)


# --------------------------------------------------------------------------
# M2-M5: structured specs
# --------------------------------------------------------------------------
FLOOR_BY_CATEGORY = {
    "floor_cleaning": ["tile", "wood", "carpet", "mixed"],
    "window_cleaning": ["glass"],
    "lawn_care": ["grass"],
    "pool_cleaning": ["water"],
    "tidying": ["tile", "wood", "carpet", "mixed"],
    "elder_care": ["tile", "wood", "mixed"],
    "event_serving": ["tile", "wood", "concrete", "grass", "mixed"],
    "home_patrol": ["concrete", "grass", "tile", "mixed"],
}
OUTDOOR_PROB = {"lawn_care": 1.0, "pool_cleaning": 0.9, "home_patrol": 0.7, "window_cleaning": 0.5,
                "event_serving": 0.3, "floor_cleaning": 0.0, "tidying": 0.0, "elder_care": 0.05}


def sample_spec(category: str) -> dict:
    housing = rng.choice(HOUSING_TYPES, p=[0.5, 0.25, 0.15, 0.10])
    base_area = {"hdb": 90, "condo": 110, "landed": 250, "shophouse": 160}[housing]
    area = float(np.clip(rng.normal(base_area, base_area * 0.35), 15, 800))
    if category == "pool_cleaning":
        area = float(np.clip(rng.normal(40, 15), 8, 120))
    return {
        "task_category": category,
        "floor_type": rng.choice(FLOOR_BY_CATEGORY[category]),
        "housing_type": housing,
        "area_m2": round(area, 1),
        "num_rooms": int(np.clip(round(area / 30 + rng.normal(0, 1)), 1, 12)),
        "payload_kg": round(float(rng.choice([0, 0, 0.5, 1, 2, 5, 10])
                                  if category in ("tidying", "elder_care", "event_serving") else 0), 1),
        "budget_sgd": round(float(rng.lognormal(np.log(400), 0.7)), 0),
        "duration_days": int(rng.choice([1, 1, 2, 3, 5, 7, 14, 30])),
        "hours_per_day": int(rng.choice([2, 4, 6, 8, 12, 24], p=[0.2, 0.3, 0.2, 0.15, 0.1, 0.05])),
        "has_stairs": bool(rng.random() < (0.7 if housing in ("landed", "shophouse") else 0.05)),
        "is_outdoor": bool(rng.random() < OUTDOOR_PROB[category]),
        "has_pets": bool(rng.random() < 0.3),
        "has_children": bool(rng.random() < 0.35),
        "fragile_items": bool(rng.random() < 0.25),
    }


def label_platform(s: dict) -> str:
    c, b = s["task_category"], s["budget_sgd"]
    if c == "window_cleaning":
        return "window_crawler"
    if c == "lawn_care":
        return "quadruped" if s["has_stairs"] and b > 900 else "lawn_robot"
    if c == "pool_cleaning":
        return "pool_crawler"
    if c == "floor_cleaning":
        return "quadruped" if s["has_stairs"] and b > 1200 else "wheeled_amr"
    if c == "tidying":
        if s["has_stairs"] and b > 1500:
            return "humanoid"
        return "mobile_manipulator"
    if c == "elder_care":
        if b > 2000 or (s["has_stairs"] and b > 1200):
            return "humanoid"
        return "mobile_manipulator" if s["payload_kg"] > 0 else "wheeled_amr"
    if c == "event_serving":
        return "mobile_manipulator" if b > 800 else "service_cart"
    if c == "home_patrol":
        return "quadruped" if s["is_outdoor"] or s["has_stairs"] else "wheeled_amr"
    raise ValueError(c)


def label_addons(s: dict, platform: str) -> dict:
    c = s["task_category"]
    a = {k: False for k in ADDONS}
    if c == "floor_cleaning":
        a["vacuum_module"] = s["floor_type"] in ("carpet", "mixed", "wood") or s["has_pets"]
        a["mop_module"] = s["floor_type"] in ("tile", "wood", "mixed")
    if platform in ("mobile_manipulator", "humanoid") or c == "tidying":
        a["gripper"] = True
    a["stair_kit"] = s["has_stairs"] and platform in ("wheeled_amr", "mobile_manipulator")
    a["outdoor_kit"] = s["is_outdoor"] and platform not in ("lawn_robot", "pool_crawler", "window_crawler")
    a["camera_mast"] = c in ("home_patrol", "elder_care")
    a["tray_rack"] = c == "event_serving"
    a["extra_battery"] = s["hours_per_day"] >= 8 or s["area_m2"] > 300
    a["pet_safe_bumper"] = s["has_pets"] and platform in ("wheeled_amr", "lawn_robot", "mobile_manipulator")
    a["voice_interface"] = c == "elder_care" or (c == "event_serving" and s["budget_sgd"] > 1000)
    # label noise: flip ~3% of add-on decisions
    for k in a:
        if rng.random() < 0.03:
            a[k] = not a[k]
    return a


def label_skill_pack(s: dict) -> str:
    c = s["task_category"]
    if c == "floor_cleaning":
        return "spot_clean" if s["area_m2"] < 50 or (s["has_pets"] and s["duration_days"] > 7) else "coverage_clean"
    if c == "window_cleaning":
        return "facade_crawl"
    if c == "lawn_care":
        return "lawn_coverage"
    if c == "pool_cleaning":
        return "pool_coverage"
    if c == "tidying":
        return "declutter_sort" if s["num_rooms"] >= 4 or s["fragile_items"] else "pick_and_place"
    if c == "elder_care":
        return "fetch_and_deliver" if s["payload_kg"] > 0 else "companion_monitor"
    if c == "event_serving":
        return "serve_and_navigate"
    if c == "home_patrol":
        return "patrol_route"
    raise ValueError(c)


HOURS_PER_M2 = {"floor_cleaning": 0.025, "window_cleaning": 0.06, "lawn_care": 0.02,
                "pool_cleaning": 0.05, "tidying": 0.04, "elder_care": 0.0, "event_serving": 0.0,
                "home_patrol": 0.0}


def label_robot_hours(s: dict) -> float:
    """Total robot-hours of operation needed to complete the job."""
    c = s["task_category"]
    if c in ("elder_care", "home_patrol", "event_serving"):
        # time-based services: robot runs for the whole booked window
        hours = s["duration_days"] * s["hours_per_day"]
    else:
        hours = s["area_m2"] * HOURS_PER_M2[c] * (1 + 0.15 * s["num_rooms"] / 4)
        hours *= 1.3 if s["has_stairs"] else 1.0
        hours *= 1.2 if s["has_pets"] else 1.0
        hours *= 1.25 if s["fragile_items"] else 1.0
        hours *= 1.15 if s["floor_type"] in ("carpet", "mixed") else 1.0
        # recurring jobs: one pass per week of the booking window
        hours *= max(1, s["duration_days"] // 7)
    return round(float(max(0.5, hours * rng.normal(1.0, 0.08))), 2)


def gen_specs(n: int = 6000) -> pd.DataFrame:
    rows = []
    for _ in range(n):
        s = sample_spec(random.choice(TASK_CATEGORIES))
        platform = label_platform(s)
        if rng.random() < 0.04:  # 4% of historical jobs used a different platform
            platform = random.choice(["wheeled_amr", "mobile_manipulator", "quadruped", "humanoid"])
        addons = label_addons(s, platform)
        rows.append({
            **s,
            "platform": platform,
            **{f"addon_{k}": int(v) for k, v in addons.items()},
            "skill_pack": label_skill_pack(s),
            "robot_hours": label_robot_hours(s),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    # gen_descriptions() must still run first with the default size: it advances the
    # shared random state that gen_specs() continues from, which keeps task_specs.csv
    # identical to earlier runs. Only a subsample of its rows is used.
    templates = gen_descriptions()
    d = build_m1_dataset(templates)
    d.to_csv(OUT / "task_descriptions.csv", index=False)
    s = gen_specs()
    s.to_csv(OUT / "task_specs.csv", index=False)
    print(f"task_descriptions.csv: {len(d)} rows")
    print(d.groupby(["split", "source"]).size().to_string())
    print(f"task_specs.csv: {len(s)} rows")
    print(s["platform"].value_counts().to_string())
