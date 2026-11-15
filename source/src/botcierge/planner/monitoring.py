"""Is the ML helping? (A13 acceptance rate) and what should it learn next? (A12 override export)

Every plan keeps its original ML recommendation (source=ML). When a customer changes the setup on the
booking page (S08), a source=CUSTOMER row is added, but only if something really changed. When staff
change it in review before dispatch (A08), a source=STAFF row is added. So for each booked order:

- kept by the customer: its plan has no CUSTOMER row;
- kept in review: its plan has no STAFF row;
- accepted: both, so the robot shipped exactly as the models chose it.

Orders still waiting for payment are left out (they never reached checkout).
"""
import csv

from catalog.taxonomy import TASK_CATEGORY_CHOICES
from orders.models import Order

from .models import Recommendation

SRC = Recommendation.Source
CATEGORY_LABELS = dict(TASK_CATEGORY_CHOICES)


def _pct(part, whole):
    return round(100 * part / whole) if whole else None


def _booked_plans():
    """[(task category, sources used on that plan)] for every booked order that came from a plan."""
    orders = (Order.objects.exclude(status=Order.Status.PENDING_PAYMENT)
              .filter(recommendation__isnull=False)
              .select_related("recommendation__task_request__spec")
              .prefetch_related("recommendation__task_request__recommendations"))
    rows = []
    for o in orders:
        tr = o.recommendation.task_request
        spec = getattr(tr, "spec", None)
        rows.append((spec.task_category if spec else "", {r.source for r in tr.recommendations.all()}))
    return rows


def _summary(rows):
    n = len(rows)
    customer_kept = sum(1 for _, s in rows if SRC.CUSTOMER not in s)
    staff_kept = sum(1 for _, s in rows if SRC.STAFF not in s)
    accepted = sum(1 for _, s in rows if not s & {SRC.CUSTOMER, SRC.STAFF})
    return {"orders": n, "accepted": accepted, "accepted_pct": _pct(accepted, n),
            "customer_kept_pct": _pct(customer_kept, n), "customer_changed": n - customer_kept,
            "staff_kept_pct": _pct(staff_kept, n), "staff_changed": n - staff_kept}


def acceptance():
    """Overall rates plus one row per task type, lowest acceptance first (where the models need work)."""
    rows = _booked_plans()
    by_type = {}
    for cat, sources in rows:
        by_type.setdefault(cat, []).append((cat, sources))
    per_type = [{"label": CATEGORY_LABELS.get(cat, "Unknown"), **_summary(r)} for cat, r in by_type.items()]
    per_type.sort(key=lambda t: (t["accepted_pct"], -t["orders"]))
    return {**_summary(rows), "per_type": per_type}


# ---------------------------------------------------------------- A12 export

CSV_COLUMNS = [
    "plan_id", "changed_by", "changed_at", "description", "task_category", "housing_type", "area_m2",
    "num_rooms", "floor_type", "has_stairs", "is_outdoor", "has_pets", "has_children", "fragile_items",
    "payload_kg", "budget_sgd", "hours_per_day",
    "model_robot", "model_platform", "model_addons", "model_skill_pack",
    "chosen_robot", "chosen_platform", "chosen_addons", "chosen_skill_pack",
]


def _setup(rec):
    robot = rec.robot_model
    return [robot.name if robot else "", robot.platform if robot else "",
            " ".join(sorted(a.code for a in rec.addons.all())), rec.skill_pack.code if rec.skill_pack else ""]


def override_rows():
    """One row per human change (customer or staff), next to what the models first suggested.
    The 'chosen_*' columns are the corrected labels for M2 (platform), M3 (add-ons) and M4 (skill pack)."""
    changes = (Recommendation.objects.filter(source__in=[SRC.CUSTOMER, SRC.STAFF])
               .select_related("task_request__spec", "robot_model", "skill_pack")
               .prefetch_related("addons").order_by("created_at"))
    ml = {r.task_request_id: r for r in Recommendation.objects.filter(source=SRC.ML)
          .select_related("robot_model", "skill_pack").prefetch_related("addons")}
    for rec in changes:
        tr = rec.task_request
        spec = getattr(tr, "spec", None)
        first = ml.get(tr.pk)
        yield [tr.pk, rec.source, rec.created_at.strftime("%Y-%m-%d %H:%M"), tr.description,
               spec.task_category if spec else "", tr.housing_type, tr.area_m2, tr.num_rooms, tr.floor_type,
               tr.has_stairs, tr.is_outdoor, tr.has_pets, tr.has_children, tr.fragile_items,
               tr.payload_kg, tr.budget_sgd, tr.hours_per_day,
               *(_setup(first) if first else ["", "", "", ""]), *_setup(rec)]


def write_overrides_csv(out):
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    writer.writerows(override_rows())
