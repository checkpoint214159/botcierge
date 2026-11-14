"""Orders: booking page, cart, checkout, tracking and history (S08-S12).

Flow: plan (planner.result) -> booking page (S08 adjust setup + S09 dates, address, floor plan,
availability) -> cart (all plans not yet paid for, ready ones first) -> checkout (S10) -> order (S11).
"""
import json
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from planner.decomposer import requote
from planner.models import TaskRequest
from planner.pricing import rec_quote_lines
from planner.views import describe_tuning, total_label

from .forms import BookingForm, CheckoutForm
from .models import Order, PromoCode
from .services import (FLOW, ONGOING, NoUnitFree, booking_problems, booking_window, check_promo, create_order,
                       discount_for, order_summary, preview_booking, rebook, save_booking)


def _open_plan(request, pk):
    """The customer's own plan, its spec and newest recommendation. Booked plans can't be edited:
    returns a redirect to their order instead."""
    tr = get_object_or_404(TaskRequest.objects.select_related("spec", "address"), pk=pk, customer=request.user)
    if tr.status == TaskRequest.Status.BOOKED:
        order = Order.objects.filter(recommendation__task_request=tr, customer=request.user).first()
        messages.info(request, "This plan is already booked.")
        return tr, None, redirect("orders:order_detail", pk=order.pk) if order else redirect("planner:my_plans")
    rec = tr.recommendations.select_related("robot_model", "skill_pack").first()
    if rec is None or not hasattr(tr, "spec"):
        messages.warning(request, "We could not build a plan for this request yet.")
        return tr, None, redirect("planner:start")
    return tr, rec, None


# ---------------------------------------------------------------- booking page (S08 + S09)

@login_required
def booking(request, pk):
    """Adjust the recommended setup and fill in what we need to deliver it.
    The price sidebar updates live through booking_quote(); saving happens here."""
    tr, rec, bail = _open_plan(request, pk)
    if bail:
        return bail
    if request.method == "POST":
        form = BookingForm(request.POST, request.FILES, task_request=tr)
        if form.is_valid():
            rec, setup_changed = save_booking(tr, rec, form.cleaned_data)
            problems = booking_problems(tr, rec)
            if request.POST.get("action") == "checkout" and not problems:
                return redirect("orders:checkout", pk=tr.pk)
            messages.success(request, "Booking saved." if not problems
                             else "Saved. A few things are still needed before checkout.")
            return redirect("orders:booking", pk=tr.pk)
    else:
        form = BookingForm(task_request=tr, initial={
            "robot": rec.robot_model, "addons": rec.addons.all(), "skill_pack": rec.skill_pack,
            "start_date": tr.start_date, "address": tr.address,
            "keep_out_zones": json.dumps(tr.keep_out_zones)})

    # data-* attributes let the page grey out attachments / skill packs that don't fit the chosen robot
    robots = list(form.fields["robot"].queryset)
    addon_list = list(form.fields["addons"].queryset.order_by("name"))
    addon_platforms = {a.pk: a.compatible_platforms for a in addon_list}
    selected_addons = {int(v) for v in (form["addons"].value() or [])}
    pack_robots = {p.pk: ",".join(str(r) for r in p.compatible_robots.values_list("pk", flat=True))
                   for p in form.fields["skill_pack"].queryset}
    return render(request, "orders/booking.html", {
        "tr": tr, "rec": rec, "form": form, "spec": tr.spec,
        "robots": robots, "robot_platforms": {r.pk: r.platform for r in robots},
        "addon_list": addon_list, "selected_addons": selected_addons,
        "addon_platforms": addon_platforms, "pack_robots": pack_robots,
        "lines": rec_quote_lines(rec), "problems": booking_problems(tr, rec),
        "start_end": booking_window(rec),
    })


@login_required
def booking_quote(request, pk):
    """JSON price + availability for the booking page's current (unsaved) choices.
    A GET that changes nothing, so it is safe to call on every edit."""
    tr, rec, bail = _open_plan(request, pk)
    if bail:
        return JsonResponse({"ok": False, "errors": ["This plan can't be edited."]}, status=409)
    form = BookingForm(request.GET, task_request=tr)
    if not form.is_valid():
        errors = [e for errs in form.errors.values() for e in errs]
        return JsonResponse({"ok": False, "errors": errors})
    d = form.cleaned_data
    data = preview_booking(tr, d["robot"], list(d["addons"]), d["skill_pack"], d["start_date"], d["address"])
    return JsonResponse({"ok": True, **data})


# ---------------------------------------------------------------- cart (S09)

def _cart_rows(user):
    """Every plan the customer hasn't paid for yet, with what's still missing."""
    plans = (TaskRequest.objects.filter(customer=user, status=TaskRequest.Status.PLANNED)
             .select_related("spec", "address").prefetch_related("recommendations__robot_model"))
    rows = []
    for tr in plans:
        recs = tr.recommendations.all()  # newest first (Meta.ordering), already prefetched
        rec = recs[0] if recs else None
        if rec is None or not hasattr(tr, "spec"):
            continue
        start, end = booking_window(rec)
        rows.append({"tr": tr, "rec": rec, "start": start, "end": end, "problems": booking_problems(tr, rec)})
    return rows


@login_required
def cart(request):
    rows = _cart_rows(request.user)
    return render(request, "orders/cart.html", {
        "ready": [r for r in rows if not r["problems"]],
        "incomplete": [r for r in rows if r["problems"]],
    })


@login_required
@require_POST
def cart_remove(request, pk):
    """Take a plan out of the cart. It stays under My plans and can be put back."""
    tr = get_object_or_404(TaskRequest, pk=pk, customer=request.user, status=TaskRequest.Status.PLANNED)
    tr.status = TaskRequest.Status.DRAFT
    tr.save(update_fields=["status"])
    messages.info(request, f"Removed \"{tr}\" from your cart. You can find it under My plans.")
    return redirect("orders:cart")


@login_required
@require_POST
def cart_restore(request, pk):
    tr = get_object_or_404(TaskRequest, pk=pk, customer=request.user, status=TaskRequest.Status.DRAFT)
    tr.status = TaskRequest.Status.PLANNED
    tr.save(update_fields=["status"])
    messages.success(request, f"\"{tr}\" is back in your cart.")
    return redirect("orders:cart")


# ---------------------------------------------------------------- checkout (S10)

@login_required
def checkout(request, pk):
    """Promo code and mock payment for one booking; creates the Order.
    Applying a promo is a GET (?promo=CODE): it only previews the discount. Paying is a POST."""
    tr, rec, bail = _open_plan(request, pk)
    if bail:
        return bail
    rec = requote(rec)  # always charge current prices for the current address
    problems = booking_problems(tr, rec)
    if problems:
        for p in problems:
            messages.warning(request, p)
        return redirect("orders:booking", pk=tr.pk)

    code = request.POST.get("promo_code") if request.method == "POST" else request.GET.get("promo", "")
    promo, promo_error = check_promo(code or "")

    form = CheckoutForm(request.POST or None, initial={"promo_code": promo.code if promo else ""})
    if request.method == "POST" and form.is_valid():
        if promo_error:
            messages.error(request, promo_error)
            return redirect("orders:checkout", pk=tr.pk)
        try:
            with transaction.atomic():
                order = create_order(request.user, rec, tr.address.one_line(), promo,
                                     reference=f"MOCK-{uuid.uuid4().hex[:10].upper()}")
        except NoUnitFree:
            messages.error(request, "Sorry, that robot was just booked by someone else for these dates.")
            return redirect("orders:booking", pk=tr.pk)
        messages.success(request, f"Payment received. Order #{order.pk} is confirmed.")
        return redirect("orders:confirmation", pk=order.pk)

    subtotal = rec.quoted_price
    discount = discount_for(subtotal, promo)
    start, end = booking_window(rec)
    return render(request, "orders/checkout.html", {
        "form": form, "tr": tr, "rec": rec, "lines": rec_quote_lines(rec), "start": start, "end": end,
        "tuning": describe_tuning(tr, tr.spec),
        "subtotal": subtotal, "discount": discount, "total": subtotal - discount,
        "promo": promo, "promo_error": promo_error, "promo_entered": code or "",
        "available_promos": PromoCode.objects.filter(is_active=True),
    })


@login_required
def confirmation(request, pk):
    order = get_object_or_404(Order, pk=pk, customer=request.user)
    return render(request, "orders/confirmation.html", {"order": order, "summary": order_summary(order)})


# ---------------------------------------------------------------- after booking (S11, S12)

def _with_progress(order):
    """Attach the robot (for the photo) and 'step x of y' so the list can show where an order is."""
    item = next((i for i in order.items.all() if i.kind == i.Kind.ROBOT), None)
    order.robot = item.robot_model if item else None
    order.step = FLOW.index(order.status) + 1 if order.status in FLOW else None
    order.steps_total = len(FLOW)
    return order


@login_required
def order_list(request):
    """S12: ongoing orders first, finished ones below with a rebook button."""
    orders = [_with_progress(o) for o in Order.objects.filter(customer=request.user)
              .prefetch_related("items__robot_model").order_by("start_date")]
    ongoing = [o for o in orders if o.status in ONGOING]
    past = sorted((o for o in orders if o.status not in ONGOING), key=lambda o: o.start_date, reverse=True)
    return render(request, "orders/order_list.html", {"ongoing": ongoing, "past": past})


@login_required
@require_POST
def order_rebook(request, pk):
    """S12: copy a past order's plan into the cart with new dates, then finish it on the booking page."""
    order = get_object_or_404(Order, pk=pk, customer=request.user)
    tr = rebook(order)
    if tr is None:
        messages.error(request, "We can't rebook this one because its plan was deleted. Start a new plan instead.")
        return redirect("orders:order_list")
    messages.success(request, "Copied into your cart. Check the dates and details, then check out.")
    return redirect("orders:booking", pk=tr.pk)


@login_required
def order_detail(request, pk):
    """S11: status timeline built from OrderStatusEvent."""
    order = get_object_or_404(Order, pk=pk, customer=request.user)
    steps = [(st, st.label) for st in FLOW]
    reached = {e.status for e in order.events.all()}
    return render(request, "orders/order_detail.html", {
        "order": order, "summary": order_summary(order), "events": order.events.all(),
        "steps": [(label, st in reached) for st, label in steps],
        "cancelled": order.status == Order.Status.CANCELLED,
        "ongoing": order.status in ONGOING,
    })
