"""A08: staff review of each paid order's plan before the robot is dispatched.

It never blocks the customer: they get their recommendation and pay straight away. Staff then work
through a queue before the ship day, and an order can only be dispatched (A07) once it is approved.

Queue order: grouped by start date (the day the robot ships), soonest first. Within a day, the most
expensive orders come first, because more is at stake if the plan is wrong.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from catalog.models import FleetUnit
from planner.decomposer import refresh_conditioning, save_customer_edit
from planner.models import Recommendation
from staffpanel.queue import group_by

from .models import Order, OrderItem, OrderStatusEvent
from .services import NoUnitFree, _release_unit, add_items, free_units

ADJUSTMENT = "Adjustment by our team (no change to what you paid)"


SORTS = {"day": "By ship day", "risk": "Riskiest first"}


def review_queue(state=Order.Review.PENDING, sort="day"):
    """Paid orders that haven't been dispatched yet, in review order. Each gets .flags (see risk_flags).

    sort="day": soonest ship day first, biggest order first within a day.
    sort="risk" (A14): most flags first, so shaky recommendations are checked while there's time
    to call the customer; ties keep the ship-day order."""
    orders = list(Order.objects.filter(status=Order.Status.CONFIRMED, review_status=state)
                  .select_related("customer", "recommendation__task_request__spec", "recommendation__robot_model")
                  .order_by("start_date", "-total", "created_at"))
    for o in orders:
        o.flags = risk_flags(o)
    if sort == "risk":
        orders.sort(key=lambda o: -len(o.flags))  # stable, so ship-day order stays within each count
    return orders


def day_label(d) -> str:
    today = timezone.localdate()
    if d < today:
        return "Overdue: should have shipped already"
    if d == today:
        return "Ships today"
    if d == today + timedelta(days=1):
        return "Ships tomorrow"
    return f"Ships {d:%a %d %b}"


def risk_label(n) -> str:
    return "Nothing flagged" if n == 0 else f"{n} thing{'s' if n > 1 else ''} to check"


def grouped(orders, sort="day"):
    """[(label, [orders])] by ship day (or by number of flags), keeping the queue order inside each."""
    if sort == "risk":
        return group_by(orders, key=lambda o: len(o.flags), label=risk_label)
    return group_by(orders, key=lambda o: o.start_date, label=day_label)


def risk_flags(order) -> list[str]:
    """Short reasons to look harder, from the ML output. A14's "riskiest first" sorts by how many there are.
    spec.edge_cases are left out on purpose: most are setup notes (pets, quiet hours) the robot
    config already handles, and the real risks among them (deadline, budget) are flagged here."""
    rec = order.recommendation
    if rec is None:
        return ["No plan attached"]
    spec = rec.task_request.spec
    flags = []
    if spec.category_confidence and spec.category_confidence < 0.6:
        flags.append(f"Unsure of task type ({spec.category_confidence:.0%})")
    if rec.source == Recommendation.Source.ML and rec.platform_confidence and rec.platform_confidence < 0.6:
        flags.append(f"Unsure of platform ({rec.platform_confidence:.0%})")
    if rec.source == Recommendation.Source.CUSTOMER:
        flags.append("Customer changed the setup")
    robot = rec.robot_model
    if robot and spec.task_category not in robot.category_list:
        flags.append("Robot isn't listed for this task type")
    if not spec.feasible_in_time:
        flags.append("May not finish in time")
    if not spec.within_budget:
        flags.append("Over budget")
    return flags


def _decide(order, user, status, note):
    order.review_status = status
    order.review_note = note
    order.reviewed_by = user
    order.reviewed_at = timezone.now()
    order.save(update_fields=["review_status", "review_note", "reviewed_by", "reviewed_at"])


@transaction.atomic
def approve(order, user, note=""):
    _decide(order, user, Order.Review.APPROVED, note)
    OrderStatusEvent.objects.create(order=order, status=order.status, created_by=user,
                                    note="Your setup has been checked by our team.")


def reject(order, user, note):
    """Needs follow-up: staff contact the customer by email. Nothing is shown to the customer here."""
    _decide(order, user, Order.Review.REJECTED, note)


@transaction.atomic
def staff_override(order, user, robot, addons, skill_pack):
    """Staff change the robot, attachments or skill pack before dispatch.

    Saves a Recommendation(source=STAFF), a corrected label for retraining (A12), and rebuilds the
    order's lines. The customer pays exactly what they already paid: an adjustment line balances
    the new prices back to the original subtotal. Raises NoUnitFree if the new robot has no free unit.
    """
    item = order.items.get(kind=OrderItem.Kind.ROBOT)
    if robot == item.robot_model:
        unit = item.fleet_unit
    else:
        unit = free_units(robot, order.start_date, order.end_date, ignore_order=order).first()
        if unit is None:
            raise NoUnitFree()

    old = order.recommendation
    rec = save_customer_edit(old, robot, addons, skill_pack, source=Recommendation.Source.STAFF)
    rec.task_request.recommendations.update(is_selected=False)
    rec.is_selected = True
    rec.save(update_fields=["is_selected"])
    refresh_conditioning(rec)

    old_unit = item.fleet_unit_id
    order.items.all().delete()
    add_items(order, rec, unit)
    gap = order.subtotal - rec.quoted_price
    if gap:
        OrderItem.objects.create(order=order, kind=OrderItem.Kind.SERVICE, description=ADJUSTMENT, unit_price=gap)
    order.recommendation = rec
    order.save(update_fields=["recommendation"])

    if unit and unit.pk != old_unit:
        _release_unit(old_unit, order)
        if unit.status == FleetUnit.Status.AVAILABLE:
            unit.status = FleetUnit.Status.RESERVED
            unit.save(update_fields=["status"])

    changed = [f"robot {item.robot_model.name} → {robot.name}"] if robot != item.robot_model else []
    old_addons = set(old.addons.values_list("name", flat=True)) if old else set()
    new_addons = {a.name for a in addons}
    if old_addons != new_addons:
        changed.append("attachments")
    if old and old.skill_pack != skill_pack:
        changed.append("skill pack")
    OrderStatusEvent.objects.create(
        order=order, status=order.status, created_by=user,
        note=f"Our team adjusted your setup ({', '.join(changed) or 'details'}). No change to what you paid.")
    return rec
