"""Booking rules shared by the cart (S09) and checkout (S10)."""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q
from django.utils import timezone

from catalog.models import FleetUnit

from .models import Order, OrderItem, OrderStatusEvent, Payment, PromoCode

# Units in these states can never be booked; every other state is bookable on dates they are free.
UNBOOKABLE = [FleetUnit.Status.MAINTENANCE, FleetUnit.Status.RETIRED]
INACTIVE_ORDERS = [Order.Status.CANCELLED]


def booking_window(rec) -> tuple[date, date]:
    tr = rec.task_request
    days = rec.price_breakdown.get("rental_days", 1)
    return tr.start_date, tr.start_date + timedelta(days=days - 1)


def free_units(robot_model, start: date, end: date):
    """Units of this robot model with no overlapping, non-cancelled booking."""
    busy = OrderItem.objects.filter(
        kind=OrderItem.Kind.ROBOT, fleet_unit__isnull=False,
        order__start_date__lte=end, order__end_date__gte=start,
    ).exclude(order__status__in=INACTIVE_ORDERS).values_list("fleet_unit_id", flat=True)
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


class NoUnitFree(Exception):
    pass


def create_order(user, rec, address: str, promo, method: str = "card", reference: str = "") -> Order:
    """Build the Order, its lines, a paid mock Payment and the first timeline event, and reserve a unit.
    Must be called inside transaction.atomic()."""
    start, end = booking_window(rec)
    unit = free_units(rec.robot_model, start, end).first()
    if unit is None:
        raise NoUnitFree()
    days = rec.price_breakdown.get("rental_days", 1)
    subtotal = rec.quoted_price
    discount = discount_for(subtotal, promo)
    total = subtotal - discount

    order = Order.objects.create(
        customer=user, recommendation=rec, status=Order.Status.CONFIRMED,
        start_date=start, end_date=end, delivery_address=address,
        promo_code=promo, subtotal=subtotal, discount=discount, total=total)

    b = rec.price_breakdown
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
                             unit_price=Decimal(str(b.get("delivery_and_setup", 0))))

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


# Forward-only lifecycle staff step through (A07); the customer sees it as a timeline (S11).
FLOW = [Order.Status.CONFIRMED, Order.Status.DISPATCHED, Order.Status.ON_SITE,
        Order.Status.RUNNING, Order.Status.COMPLETED, Order.Status.COLLECTED]


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
