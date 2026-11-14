"""Task decomposition: TaskRequest -> TaskSpec + Recommendation.

Pipeline
  1. M1 classifies the free-text description into a task category
     (skipped if the customer picked a category themselves).
  2. M5 estimates robot-hours for job-based tasks (cleaning, mowing, tidying).
     Time-based services (elder care, patrol, serving) run for the booked
     window instead. Rules turn hours into days and check deadline and budget.
  3. M2 predicts the robot platform; a business rule picks the cheapest
     active catalogue robot of that platform that meets the hard
     constraints (stairs, outdoor, payload).
  4. M3 predicts the add-on set, filtered to add-ons the robot supports.
  5. M4 predicts the skill pack (policy family).
  6. Rules assemble the policy conditioning (the per-job config sent to the
     robot) and the quote.

Models are loaded once per process and cached.
"""
from decimal import Decimal
from functools import lru_cache
import math

import joblib
import pandas as pd
from django.conf import settings
from django.db import transaction
from django.db.models import Q

from catalog.models import AddOn, RobotModel, SkillPack
from catalog.taxonomy import TASK_PLATFORMS

from .models import Recommendation, TaskRequest, TaskSpec
from .pricing import build_quote

CATEGORY_CONFIDENCE_FLOOR = 0.55  # below this we tell the customer we are unsure
TIME_BASED_CATEGORIES = {"elder_care", "home_patrol", "event_serving"}

SUBTASK_TEMPLATES = {
    "floor_cleaning": ["Map the floor plan", "Mark keep-out zones", "Vacuum pass", "Mop pass",
                       "Return to dock and empty bin"],
    "window_cleaning": ["Attach safety tether", "Map glass panels", "Crawl and wipe each panel",
                        "Squeegee edges", "Detach and pack"],
    "lawn_care": ["Walk boundary to set perimeter", "Mow in stripes", "Edge along paths",
                  "Return to base"],
    "pool_cleaning": ["Lower crawler into pool", "Floor coverage pass", "Wall scrub pass",
                      "Retrieve and empty filter"],
    "tidying": ["Map rooms and storage spots", "Detect loose items", "Pick and sort by type",
                "Place items in bins/shelves", "Report items it could not place"],
    "elder_care": ["Learn home layout", "Set check-in schedule", "Medication reminders",
                   "Fall detection watch", "Fetch requested items", "Daily summary to family"],
    "event_serving": ["Map venue and kitchen pickup point", "Load trays", "Circulate among guests",
                      "Return empties", "Recharge between rounds"],
    "home_patrol": ["Map perimeter and entry points", "Set patrol waypoints", "Run patrol loop",
                    "Send alerts with snapshots", "Daily report"],
}


@lru_cache(maxsize=None)
def load_model(name: str) -> dict:
    return joblib.load(settings.ML_MODEL_DIR / f"{name}.joblib")


def _feature_row(tr: TaskRequest, category: str) -> pd.DataFrame:
    """Build the single-row DataFrame the structured models (M2-M5) expect."""
    row = {
        "task_category": category,
        "floor_type": tr.floor_type,
        "housing_type": tr.housing_type,
        "area_m2": float(tr.area_m2),
        "num_rooms": tr.num_rooms,
        "payload_kg": float(tr.payload_kg),
        "budget_sgd": float(tr.budget_sgd),
        "duration_days": tr.duration_days,
        "hours_per_day": tr.hours_per_day,
        "has_stairs": int(tr.has_stairs),
        "is_outdoor": int(tr.is_outdoor),
        "has_pets": int(tr.has_pets),
        "has_children": int(tr.has_children),
        "fragile_items": int(tr.fragile_items),
    }
    features = load_model("m2_platform")["features"]
    return pd.DataFrame([row])[features]


def predict_category(description: str) -> tuple[str, float]:
    m1 = load_model("m1_task_category")["model"]
    proba = m1.predict_proba([description])[0]
    best = proba.argmax()
    return m1.classes_[best], float(proba[best])


def eligible_robots(tr: TaskRequest, category: str | None = None):
    """Robots that can do this job: a platform suited to the task type (TASK_PLATFORMS) plus
    the hard constraints (payload, stairs, outdoor). Shared by the ML pick below and the
    customer's own choice on the booking page."""
    category = category or tr.spec.task_category
    qs = RobotModel.objects.filter(is_active=True, max_payload_kg__gte=tr.payload_kg,
                                   platform__in=TASK_PLATFORMS.get(category, []))
    if tr.has_stairs:
        # wheeled bases are allowed because they can take a stair kit add-on
        qs = qs.filter(Q(can_climb_stairs=True) | Q(platform__in=["wheeled_amr", "mobile_manipulator"]))
    if tr.is_outdoor:
        qs = qs.filter(outdoor=True)
    return qs


def choose_robot(platform: str, tr: TaskRequest, category: str):
    """Business rule on top of M2: cheapest eligible robot of the predicted platform. If M2
    predicted a platform with no eligible robot, fall back to the cheapest eligible one.
    Returns None when nothing in the fleet suits the task, rather than a robot that can't do it."""
    qs = eligible_robots(tr, category)
    same_platform = qs.filter(platform=platform).order_by("daily_rate").first()
    return same_platform or qs.order_by("daily_rate").first()


def find_edge_cases(tr: TaskRequest, category: str, days_needed: int, quote: Decimal,
                    robot) -> list[str]:
    cases = []
    if tr.has_stairs:
        cases.append("Multi-level space: robot needs stair capability or a stair kit.")
    if tr.has_pets:
        cases.append("Pets present: pet-aware navigation and slower speed enabled.")
    if tr.has_children:
        cases.append("Children present: child-safe mode, no unattended operation near play areas.")
    if tr.fragile_items:
        cases.append("Fragile items: keep-out zones should be drawn on the floor plan.")
    if tr.is_outdoor:
        cases.append("Outdoor work: job pauses automatically during heavy rain.")
    if tr.quiet_hours:
        cases.append(f"Quiet hours {tr.quiet_hours}: noisy modules disabled in this window.")
    if days_needed > tr.duration_days:
        cases.append(f"Deadline risk: estimated {days_needed} day(s) at {tr.hours_per_day} h/day, "
                     f"but your window is {tr.duration_days} day(s). Increase hours per day or extend the deadline.")
    if quote > tr.budget_sgd:
        cases.append(f"Over budget by S${quote - tr.budget_sgd:.2f}.")
    if robot is None:
        cases.append("No robot in the current fleet meets every constraint. Our team will contact you.")
    if not tr.floor_plan:
        cases.append("No floor plan uploaded: the robot will map the space on arrival (adds ~1 hour).")
    return cases


def build_conditioning(tr, category, skill_pack, addons, est_hours, subtasks) -> dict:
    """Per-job policy conditioning. Staff-facing; the customer sees a summary."""
    base = dict(skill_pack.default_conditioning) if skill_pack else {}
    safety_mode = "child_safe" if tr.has_children else "pet_aware" if tr.has_pets else "standard"
    base.update({
        "goal": tr.description,
        "task_category": category,
        "subtasks": subtasks,
        "map": {
            "floor_plan": tr.floor_plan.name if tr.floor_plan else None,
            "area_m2": float(tr.area_m2),
            "rooms": tr.num_rooms,
            "floor_type": tr.floor_type,
            "multi_level": tr.has_stairs,
            "outdoor": tr.is_outdoor,
            # rectangles drawn on the floor plan, as fractions of its width/height (x, y, w, h)
            "keep_out_zones": tr.keep_out_zones,
        },
        "constraints": {
            "window": [tr.start_date.isoformat(), tr.deadline_date.isoformat()],
            "hours_per_day": tr.hours_per_day,
            "quiet_hours": tr.quiet_hours or None,
            "est_robot_hours": round(est_hours, 1),
            "max_payload_kg": float(tr.payload_kg),
        },
        "safety": {
            "mode": safety_mode,
            "max_speed_mps": 0.3 if safety_mode != "standard" else 0.6,
            "keep_out_fragile": tr.fragile_items,
        },
        "hardware": [a.code for a in addons],
    })
    return base


@transaction.atomic
def decompose(tr: TaskRequest) -> Recommendation:
    # 1. category
    if tr.category_hint:
        category, cat_conf = tr.category_hint, 1.0
    else:
        category, cat_conf = predict_category(tr.description)

    X = _feature_row(tr, category)

    # 2. effort, days, feasibility
    if category in TIME_BASED_CATEGORIES:
        # the robot runs for the whole booked window, so effort is fixed by the booking
        est_hours = float(tr.duration_days * tr.hours_per_day)
        days_needed = tr.duration_days
    else:
        est_hours = max(0.5, float(load_model("m5_robot_hours")["model"].predict(X)[0]))
        days_needed = max(1, math.ceil(est_hours / max(1, tr.hours_per_day)))
    rental_days = days_needed

    # 3. platform -> robot
    m2 = load_model("m2_platform")["model"]
    p_proba = m2.predict_proba(X)[0]
    platform = m2.classes_[p_proba.argmax()]
    robot = choose_robot(platform, tr, category)

    # 4. add-ons
    m3 = load_model("m3_addons")
    addon_flags = m3["model"].predict(X)[0]
    wanted = [code for code, on in zip(m3["labels"], addon_flags) if on]
    addons = [a for a in AddOn.objects.filter(code__in=wanted, is_active=True)
              if robot is None or a.fits(robot.platform)]

    # 5. skill pack
    pack_code = load_model("m4_skill_pack")["model"].predict(X)[0]
    skill_pack = SkillPack.objects.filter(code=pack_code, is_active=True).first()

    # 6. quote
    total, breakdown = build_quote(robot, addons, skill_pack, rental_days, _postal_code(tr))

    subtasks = SUBTASK_TEMPLATES.get(category, [])
    edge_cases = find_edge_cases(tr, category, days_needed, total, robot)

    TaskSpec.objects.update_or_create(task_request=tr, defaults={
        "task_category": category,
        "category_confidence": cat_conf,
        "subtasks": subtasks,
        "edge_cases": edge_cases,
        "est_robot_hours": round(est_hours, 2),
        "est_days_needed": days_needed,
        "feasible_in_time": days_needed <= tr.duration_days,
        "within_budget": total <= tr.budget_sgd,
    })

    rec = Recommendation.objects.create(
        task_request=tr,
        source=Recommendation.Source.ML,
        robot_model=robot,
        predicted_platform=platform,
        platform_confidence=float(p_proba.max()),
        skill_pack=skill_pack,
        policy_conditioning=build_conditioning(tr, category, skill_pack, addons, est_hours, subtasks),
        quoted_price=total,
        price_breakdown=breakdown,
    )
    rec.addons.set(addons)
    tr.status = TaskRequest.Status.PLANNED
    tr.save(update_fields=["status"])
    return rec


def _postal_code(tr: TaskRequest) -> str | None:
    return tr.address.postal_code if tr.address_id else None


@transaction.atomic
def save_customer_edit(base: Recommendation, robot, addons, skill_pack) -> Recommendation:
    """S08: the customer changed the robot, add-ons or skill pack. Re-quote and save a new
    Recommendation(source=CUSTOMER); the ML row is kept so acceptance can be measured (A13)."""
    tr = base.task_request
    spec = tr.spec
    total, breakdown = build_quote(robot, addons, skill_pack, spec.est_days_needed, _postal_code(tr))
    rec = Recommendation.objects.create(
        task_request=tr,
        source=Recommendation.Source.CUSTOMER,
        robot_model=robot,
        predicted_platform=base.predicted_platform,
        platform_confidence=base.platform_confidence,
        skill_pack=skill_pack,
        policy_conditioning=build_conditioning(
            tr, spec.task_category, skill_pack, addons, spec.est_robot_hours, spec.subtasks),
        quoted_price=total,
        price_breakdown=breakdown,
    )
    rec.addons.set(addons)
    _refresh_spec_checks(tr, spec, total, robot)
    return rec


def requote(rec: Recommendation) -> Recommendation:
    """Re-price a recommendation in place, e.g. after the delivery address changed.
    The setup is unchanged, so this is not a customer edit and no new row is saved."""
    tr = rec.task_request
    total, breakdown = build_quote(rec.robot_model, list(rec.addons.all()), rec.skill_pack,
                                   tr.spec.est_days_needed, _postal_code(tr))
    if total != rec.quoted_price or breakdown != rec.price_breakdown:
        rec.quoted_price, rec.price_breakdown = total, breakdown
        rec.save(update_fields=["quoted_price", "price_breakdown"])
        _refresh_spec_checks(tr, tr.spec, total, rec.robot_model)
    return rec


def _refresh_spec_checks(tr, spec, total, robot):
    spec.within_budget = total <= tr.budget_sgd
    spec.edge_cases = find_edge_cases(tr, spec.task_category, spec.est_days_needed, total, robot)
    spec.save(update_fields=["within_budget", "edge_cases"])


def refresh_conditioning(rec: Recommendation) -> Recommendation:
    """Rebuild the robot's config after booking details changed (dates, floor plan, keep-out zones)."""
    tr, spec = rec.task_request, rec.task_request.spec
    rec.policy_conditioning = build_conditioning(
        tr, spec.task_category, rec.skill_pack, list(rec.addons.all()), spec.est_robot_hours, spec.subtasks)
    rec.save(update_fields=["policy_conditioning"])
    return rec
