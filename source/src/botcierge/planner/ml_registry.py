"""What the live ML models know, for the staff "Recommendation models" page.

Reads each joblib bundle ({"model", "features", "labels", "metrics"}) and compares the labels a model
can predict with what is in the catalogue right now. That comparison ("coverage") is what tells staff
whether a catalogue change needs a retrain:

  live         the model predicts it and it's active in the catalogue
  not_learned  active in the catalogue, but the model has never seen it: customers can still pick it
               on the booking page, the model just won't recommend it until it is retrained
  switched_off the model can predict it, but it is inactive or missing, so the recommendation drops it
  inactive     neither (nothing to do)
"""
from datetime import datetime

from django.conf import settings

from catalog.models import AddOn, RobotModel, SkillPack
from catalog.taxonomy import PLATFORM_CHOICES, TASK_CATEGORY_CHOICES

from .decomposer import load_model

# file name, short name, what it decides
MODELS = [
    ("m1_task_category", "M1", "Task type from the customer's description"),
    ("m2_platform", "M2", "Robot platform for the job"),
    ("m3_addons", "M3", "Which attachments to add"),
    ("m4_skill_pack", "M4", "Which skill pack to load"),
    ("m5_robot_hours", "M5", "Robot-hours the job needs"),
]


def _algorithm(pipeline) -> str:
    """Last step of the sklearn Pipeline, e.g. 'RandomForestClassifier'."""
    est = pipeline.steps[-1][1]
    inner = getattr(est, "estimator", None)  # MultiOutputClassifier wraps another estimator
    return f"{type(est).__name__} ({type(inner).__name__})" if inner is not None else type(est).__name__


def model_cards() -> list[dict]:
    cards = []
    for name, short, purpose in MODELS:
        path = settings.ML_MODEL_DIR / f"{name}.joblib"
        bundle = load_model(name)
        cards.append({
            "name": name, "short": short, "purpose": purpose,
            "algorithm": _algorithm(bundle["model"]),
            "features": bundle["features"], "labels": bundle["labels"], "metrics": bundle["metrics"],
            "trained_at": datetime.fromtimestamp(path.stat().st_mtime),
            "size_kb": round(path.stat().st_size / 1024),
        })
    return cards


def _row(code, label, learned, active, note="", obj=None):
    if learned and active:
        state = "live"
    elif active:
        state = "not_learned"
    elif learned:
        state = "switched_off"
    else:
        state = "inactive"
    return {"code": code, "label": label, "state": state, "note": note, "obj": obj}


def coverage() -> list[dict]:
    """One section per classifier: the model's labels lined up against the catalogue."""
    m1 = set(load_model("m1_task_category")["labels"])
    m2 = set(load_model("m2_platform")["labels"])
    m3 = set(load_model("m3_addons")["labels"])
    m4 = set(load_model("m4_skill_pack")["labels"])

    robots_per_platform = {}
    for r in RobotModel.objects.filter(is_active=True):
        robots_per_platform.setdefault(r.platform, []).append(r.name)

    platforms = [_row(code, label, code in m2, code in robots_per_platform,
                      ", ".join(robots_per_platform.get(code, [])) or "no active robot")
                 for code, label in PLATFORM_CHOICES]
    addons = list(AddOn.objects.order_by("name"))
    packs = list(SkillPack.objects.order_by("name"))
    in_db_addons, in_db_packs = {a.code for a in addons}, {p.code for p in packs}

    sections = [
        {"model": "M1", "title": "Task types", "editable": False,
         "rows": [_row(code, label, code in m1, True) for code, label in TASK_CATEGORY_CHOICES]},
        {"model": "M2", "title": "Platforms", "editable": False, "rows": platforms},
        {"model": "M3", "title": "Attachments", "editable": True,
         "rows": [_row(a.code, a.name, a.code in m3, a.is_active, obj=a) for a in addons]
         + [_row(c, c, True, False, "in the model but not in the catalogue") for c in sorted(m3 - in_db_addons)]},
        {"model": "M4", "title": "Skill packs", "editable": True,
         "rows": [_row(p.code, p.name, p.code in m4, p.is_active, obj=p) for p in packs]
         + [_row(c, c, True, False, "in the model but not in the catalogue") for c in sorted(m4 - in_db_packs)]},
    ]
    for s in sections:
        s["counts"] = {state: sum(r["state"] == state for r in s["rows"])
                       for state in ("live", "not_learned", "switched_off")}
    return sections


def learned_codes() -> dict:
    """Codes each catalogue-backed model can predict, for the 'ML' badge on the staff lists."""
    return {"addons": set(load_model("m3_addons")["labels"]),
            "skill_packs": set(load_model("m4_skill_pack")["labels"])}
