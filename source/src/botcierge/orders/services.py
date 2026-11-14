"""Booking rules shared by the booking page (S08/S09), the cart and checkout (S10)."""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from catalog.models import FleetUnit
from planner.decomposer import refresh_conditioning, requote, save_customer_edit
from planner.models import Recommendation, TaskRequest, TaskSpec
from planner.pricing import build_quote, quote_lines

from .models import Order, OrderItem, OrderStatusEvent, Payment, PromoCode

# Units in these states can never be booked; every other state is bookable on dates they are free.
UNBOOKABLE = [FleetUnit.Status.MAINTENANCE, FleetUnit.Status.RETIRED]
INACTIVE_ORDERS = [Order.Status.CANCELLED]


def window_from(start: date, days: int) -> tuple[date, date]:
    return start, start + timedelta(days=days - 1)


def booking_window(rec) -> tuple[date, date]:
    return window_from(rec.task_request.start_date, rec.price_breakdown.get("rental_days", 1))


def free_units(robot_model, start: date, end: date, ignore_order=None):
    """Units of this robot model with no overlapping, non-cancelled booking.
    ignore_order: leave this order's own booking out (used when it is being moved to new dates, S18)."""
    busy = OrderItem.objects.filter(
        kind=OrderItem.Kind.ROBOT, fleet_unit__isnull=False,
        order__start_date__lte=end, order__end_date__gte=start,
    ).exclude(order__status__in=INACTIVE_ORDERS)
    if ignore_order is not None:
        busy = busy.exclude(order=ignore_order)
    busy = busy.values_list("fleet_unit_id", flat=True)
    return (FleetUnit.objects.filter(robot_model=robot_model)
            .exclude(status__in=UNBOOKABLE).exclude(pk__in=busy))


def check_promo(code: str):
    """Return (PromoCode or None, error message)."""
    code = code.strip().upper()
    if not code:
        return None, ""
    promo = PromoCode.objects.filter(code__iexact=code, is_active=True).first()
    if promo is None or (promo.valid_until and promo.valid_until < timezone.localdate()):
        return None, "That promo code is not valid."
    return promo, ""


def discount_for(subtotal: Decimal, promo) -> Decimal:
    if promo is None:
        return Decimal("0.00")
    return (subtotal * promo.percent_off / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def booking_problems(tr, rec) -> list[str]:
    """Everything still stopping this booking from going to checkout. Empty list = ready.
    The booking page, the cart and checkout all use this, so they never disagree."""
    if rec is None or rec.robot_model is None:
        return ["No robot in the fleet fits this plan yet, so it can't be booked."]
    problems = []
    start, end = booking_window(rec)
    if start < timezone.localdate():
        problems.append("Your start date has passed. Pick a new date.")
    if tr.address_id is None:
        problems.append("Choose a delivery address.")
    if not tr.floor_plan:
        problems.append("Upload a floor plan or a photo of the space.")
    if not free_units(rec.robot_model, start, end).exists():
        problems.append(f"No {rec.robot_model.name} is free from {start:%d %b} to {end:%d %b}. "
                        "Try other dates or another robot.")
    return problems


def preview_booking(tr, robot, addons, skill_pack, start: date, address) -> dict:
    """Price and availability for choices the customer has not saved yet (live sidebar).
    Writes nothing to the database."""
    days = tr.spec.est_days_needed
    total, breakdown = build_quote(robot, addons, skill_pack, days, address.postal_code if address else None)
    start, end = window_from(start, days)
    n_free = free_units(robot, start, end).count() if robot else 0
    return {
        "lines": [{"label": label, "amount": amount}
                  for label, amount in quote_lines(breakdown, robot, addons, skill_pack)],
        "total": f"{total:.2f}",
        "delivery_priced": "delivery_and_setup" in breakdown,
        "within_budget": total <= tr.budget_sgd,
        "budget": f"{tr.budget_sgd:.2f}",
        "start": start.strftime("%d %b %Y"),
        "end": end.strftime("%d %b %Y"),
        "days": days,
        "units_free": n_free,
    }


@transaction.atomic
def save_booking(tr, rec, data) -> tuple:
    """Save the booking page. Returns (current recommendation, setup_changed).

    Task details (dates, address, floor plan) are saved on the TaskRequest. If the robot,
    add-ons or skill pack changed, that is a customer edit of the ML output and gets its own
    Recommendation row (S08). Otherwise the existing one is only re-priced.
    """
    shift = data["start_date"] - tr.start_date
    tr.start_date += shift
    tr.deadline_date += shift  # keep the same window length
    tr.address = data["address"]
    tr.keep_out_zones = data.get("keep_out_zones") or []
    if data.get("floor_plan"):
        tr.floor_plan = data["floor_plan"]
    tr.status = TaskRequest.Status.PLANNED  # saving puts a removed plan back in the cart
    tr.save()

    robot, addons, skill_pack = data["robot"], list(data["addons"]), data["skill_pack"]
    setup_changed = (robot != rec.robot_model or skill_pack != rec.skill_pack
                     or {a.pk for a in addons} != set(rec.addons.values_list("pk", flat=True)))
    if setup_changed:
        rec = save_customer_edit(rec, robot, addons, skill_pack)
    else:
        rec = requote(rec)
    # dates, floor plan and keep-out zones feed the robot's config, so rebuild it either way
    return refresh_conditioning(rec), setup_changed


class NoUnitFree(Exception):
    pass


def add_items(order, rec, unit):
    """The order's lines for a recommendation, at today's prices (copied, so later price changes
    don't touch the order). Used at checkout and when staff change the setup (A08)."""
    days = rec.price_breakdown.get("rental_days", 1)
    OrderItem.objects.create(
        order=order, kind=OrderItem.Kind.ROBOT, robot_model=rec.robot_model, fleet_unit=unit,
        description=rec.robot_model.name, quantity=days, unit_price=rec.robot_model.daily_rate)
    for a in rec.addons.all():
        OrderItem.objects.create(order=order, kind=OrderItem.Kind.ADDON, addon=a,
                                 description=a.name, quantity=days, unit_price=a.daily_rate)
    if rec.skill_pack:
        OrderItem.objects.create(order=order, kind=OrderItem.Kind.SKILL_PACK, skill_pack=rec.skill_pack,
                                 description=f"{rec.skill_pack.name} skill pack", unit_price=rec.skill_pack.flat_fee)
    OrderItem.objects.create(order=order, kind=OrderItem.Kind.SERVICE, description="Delivery, setup and collection",
                             unit_price=Decimal(str(rec.price_breakdown.get("delivery_and_setup", 0))))


def create_order(user, rec, address: str, promo, method: str = "card", reference: str = "") -> Order:
    """Build the Order, its lines, a paid mock Payment and the first timeline event, and reserve a unit.
    Must be called inside transaction.atomic()."""
    start, end = booking_window(rec)
    unit = free_units(rec.robot_model, start, end).first()
    if unit is None:
        raise NoUnitFree()
    subtotal = rec.quoted_price
    discount = discount_for(subtotal, promo)
    total = subtotal - discount

    order = Order.objects.create(
        customer=user, recommendation=rec, status=Order.Status.CONFIRMED,
        start_date=start, end_date=end, delivery_address=address,
        promo_code=promo, subtotal=subtotal, discount=discount, total=total)

    add_items(order, rec, unit)

    Payment.objects.create(order=order, method=method, amount=total, status=Payment.Status.PAID,
                           reference=reference, paid_at=timezone.now())
    OrderStatusEvent.objects.create(order=order, status=order.status, note="Booking confirmed and paid.",
                                    created_by=user)

    if unit.status == FleetUnit.Status.AVAILABLE:
        unit.status = FleetUnit.Status.RESERVED
        unit.save(update_fields=["status"])

    # mark this version as the one that went to checkout (feeds the acceptance rate, A13)
    rec.task_request.recommendations.update(is_selected=False)
    rec.is_selected = True
    rec.save(update_fields=["is_selected"])
    tr = rec.task_request
    tr.status = tr.Status.BOOKED
    tr.save(update_fields=["status"])
    return order


@transaction.atomic
def rebook(order):
    """S12: copy the plan behind a past order (task, spec and the setup that was booked) into a
    fresh PLANNED plan starting in 3 days. Returns the new TaskRequest, or None if the plan is gone."""
    rec = order.recommendation
    if rec is None:
        return None
    old = rec.task_request
    spec = TaskSpec.objects.get(task_request=old)
    length = old.deadline_date - old.start_date

    tr = TaskRequest.objects.get(pk=old.pk)
    tr.pk = None  # saving an instance with no pk inserts a copy
    tr._state.adding = True
    tr.start_date = timezone.localdate() + timedelta(days=3)
    tr.deadline_date = tr.start_date + length
    tr.status = TaskRequest.Status.PLANNED
    tr.save()

    spec.pk = None
    spec._state.adding = True
    spec.task_request = tr
    spec.save()

    new = Recommendation.objects.create(
        task_request=tr, source=rec.source, robot_model=rec.robot_model,
        predicted_platform=rec.predicted_platform, platform_confidence=rec.platform_confidence,
        skill_pack=rec.skill_pack, policy_conditioning=rec.policy_conditioning,
        quoted_price=rec.quoted_price, price_breakdown=rec.price_breakdown)
    new.addons.set(rec.addons.all())
    refresh_conditioning(requote(new))  # today's prices, new dates
    return tr


# Forward-only lifecycle staff step through (A07); the customer sees it as a timeline (S11).
FLOW = [Order.Status.CONFIRMED, Order.Status.DISPATCHED, Order.Status.ON_SITE,
        Order.Status.RUNNING, Order.Status.COMPLETED, Order.Status.COLLECTED]
# Still in progress until the robot is collected (or the order is cancelled).
ONGOING = [Order.Status.PENDING_PAYMENT, *FLOW[:-1]]
# The job is done, so the customer can rate it (S13).
REVIEWABLE = [Order.Status.COMPLETED, Order.Status.COLLECTED]


def next_status(order):
    if order.status in FLOW and order.status != FLOW[-1]:
        return FLOW[FLOW.index(order.status) + 1]
    return None


def advance_order(order, user, note: str = ""):
    """Move the order one step forward, log the timeline event and keep the unit's status in step."""
    nxt = next_status(order)
    if nxt is None:
        return None
    order.status = nxt
    order.save(update_fields=["status"])
    OrderStatusEvent.objects.create(order=order, status=nxt, note=note, created_by=user)
    unit = order.items.filter(kind=OrderItem.Kind.ROBOT).values_list("fleet_unit", flat=True).first()
    if unit:
        new = {Order.Status.DISPATCHED: FleetUnit.Status.DEPLOYED,
               Order.Status.COLLECTED: FleetUnit.Status.AVAILABLE}.get(nxt)
        if new:
            FleetUnit.objects.filter(pk=unit).update(status=new)
    return nxt


def assignable_units(order):
    """Free units for this order's dates (plus the one it already holds) for the staff picker."""
    item = order.items.get(kind=OrderItem.Kind.ROBOT)
    qs = free_units(item.robot_model, order.start_date, order.end_date)
    if item.fleet_unit_id:
        qs = qs | FleetUnit.objects.filter(pk=item.fleet_unit_id)
    return item, qs.distinct()


def order_summary(order) -> dict:
    """What the shared setup summary partial needs, built from the order's own line items
    (the prices copied at checkout), not from today's catalogue."""
    items = list(order.items.select_related("robot_model", "addon", "skill_pack"))
    lines = []
    for i in items:
        days = f" × {i.quantity} day{'s' if i.quantity != 1 else ''}" if i.kind in (i.Kind.ROBOT, i.Kind.ADDON) else ""
        lines.append((i.description + days, i.line_total))
    robot_item = next((i for i in items if i.kind == OrderItem.Kind.ROBOT), None)
    pack_item = next((i for i in items if i.kind == OrderItem.Kind.SKILL_PACK), None)
    return {
        "robot": robot_item.robot_model if robot_item else None,
        "addons": [i.addon for i in items if i.kind == OrderItem.Kind.ADDON],
        "skill_pack": pack_item.skill_pack if pack_item else None,
        "lines": lines,
        "total": order.total,
        "discount": order.discount,
        "promo_code": order.promo_code.code if order.promo_code else "",
    }


# ---------------------------------------------------------------- cancel and reschedule (S18)

# Changes are allowed until the day before the start date, and only before the robot leaves the depot.
CHANGEABLE = [Order.Status.PENDING_PAYMENT, Order.Status.CONFIRMED]


def can_change(order) -> bool:
    return order.status in CHANGEABLE and order.start_date > timezone.localdate()


def last_change_day(order) -> date:
    return order.start_date - timedelta(days=1)


def _release_unit(unit_id, order):
    """A reserved unit goes back to available, unless another live order still holds it."""
    if unit_id is None:
        return
    still_held = (OrderItem.objects.filter(kind=OrderItem.Kind.ROBOT, fleet_unit_id=unit_id,
                                           order__status__in=ONGOING).exclude(order=order).exists())
    if not still_held:
        FleetUnit.objects.filter(pk=unit_id, status=FleetUnit.Status.RESERVED).update(
            status=FleetUnit.Status.AVAILABLE)


@transaction.atomic
def cancel_order(order, user):
    """Cancel, refund in full (nothing has been delivered yet), free the unit and log it on the timeline."""
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status"])
    refunded = Payment.objects.filter(order=order, status=Payment.Status.PAID).update(
        status=Payment.Status.REFUNDED)
    note = f"Cancelled by the customer. S${order.total} refunded to your card." if refunded         else "Cancelled by the customer."
    OrderStatusEvent.objects.create(order=order, status=order.status, note=note, created_by=user)
    item = order.items.filter(kind=OrderItem.Kind.ROBOT).first()
    _release_unit(item.fleet_unit_id if item else None, order)
    return order


@transaction.atomic
def reschedule_order(order, user, new_start: date):
    """Move the booking to a new start date, keeping the same number of days and the same price.
    Keeps the same unit if it is free on the new dates, otherwise swaps to another free one.
    Raises NoUnitFree if none is."""
    days = (order.end_date - order.start_date).days + 1
    start, end = window_from(new_start, days)
    item = order.items.get(kind=OrderItem.Kind.ROBOT)
    units = free_units(item.robot_model, start, end, ignore_order=order)
    unit = units.filter(pk=item.fleet_unit_id).first() or units.first()
    if unit is None:
        raise NoUnitFree()

    old_start = order.start_date
    order.start_date, order.end_date = start, end
    order.save(update_fields=["start_date", "end_date"])
    if unit.pk != item.fleet_unit_id:
        old_unit = item.fleet_unit_id
        item.fleet_unit = unit
        item.save(update_fields=["fleet_unit"])
        _release_unit(old_unit, order)
        if unit.status == FleetUnit.Status.AVAILABLE:
            unit.status = FleetUnit.Status.RESERVED
            unit.save(update_fields=["status"])
    OrderStatusEvent.objects.create(
        order=order, status=order.status, created_by=user,
        note=f"Moved from {old_start:%d %b} to {start:%d %b} - {end:%d %b}.")

    # keep the plan's window (and the robot's config built from it) in step with the order
    rec = order.recommendation
    if rec is not None:
        tr = rec.task_request
        shift = start - tr.start_date
        tr.start_date += shift
        tr.deadline_date += shift
        tr.save(update_fields=["start_date", "deadline_date"])
        refresh_conditioning(rec)
    return order
