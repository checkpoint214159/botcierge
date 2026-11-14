"""Orders: cart, checkout, tracking. S09/S10 built; S11/S12 still to do."""
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from planner.models import Recommendation

from .forms import CheckoutForm
from .models import Order
from .services import FLOW, NoUnitFree, booking_window, check_promo, create_order, discount_for, free_units

CART_KEY = "cart_rec_id"


def _todo(request, story, title):
    return render(request, "coming_soon.html", {"story": story, "title": title})


def _cart_rec(request):
    """The recommendation in the session cart, or None. Stale or foreign ids are dropped."""
    rec_id = request.session.get(CART_KEY)
    if not rec_id:
        return None
    rec = (Recommendation.objects.filter(pk=rec_id, task_request__customer=request.user)
           .select_related("task_request", "robot_model", "skill_pack").first())
    if rec is None or rec.task_request.status == rec.task_request.Status.BOOKED:
        request.session.pop(CART_KEY, None)
        return None
    return rec


def _problems(rec):
    """Reasons this plan cannot be booked right now (S09 availability check)."""
    start, end = booking_window(rec)
    problems = []
    if rec.robot_model is None:
        problems.append("No robot in the fleet fits this plan yet, so it can't be booked.")
        return problems, 0
    if start < timezone.localdate():
        problems.append("Your start date has already passed. Update your plan with new dates.")
    n_free = free_units(rec.robot_model, start, end).count()
    if n_free == 0:
        problems.append(f"No {rec.robot_model.name} is free from {start:%d %b} to {end:%d %b}. "
                        "Try different dates or swap the robot.")
    return problems, n_free


@login_required
@require_POST
def cart_add(request, rec_id):
    rec = get_object_or_404(Recommendation, pk=rec_id, task_request__customer=request.user)
    request.session[CART_KEY] = rec.pk
    return redirect("orders:cart")


@login_required
@require_POST
def cart_remove(request):
    request.session.pop(CART_KEY, None)
    messages.info(request, "Removed from your cart.")
    return redirect("planner:my_plans")


@login_required
def cart(request):
    """S09: the plan waiting to be booked, with a live availability check for its dates."""
    rec = _cart_rec(request)
    if rec is None:
        return render(request, "orders/cart.html", {"rec": None})
    problems, n_free = _problems(rec)
    start, end = booking_window(rec)
    return render(request, "orders/cart.html", {
        "rec": rec, "tr": rec.task_request, "start": start, "end": end,
        "problems": problems, "n_free": n_free, "can_checkout": not problems,
        "days": rec.price_breakdown.get("rental_days", 1),
    })


@login_required
def checkout(request):
    """S10: delivery details, promo code and mock payment; creates the Order."""
    rec = _cart_rec(request)
    if rec is None:
        messages.info(request, "Your cart is empty. Pick a plan first.")
        return redirect("planner:my_plans")
    problems, _ = _problems(rec)
    if problems:
        for p in problems:
            messages.warning(request, p)
        return redirect("orders:cart")

    profile = getattr(request.user, "profile", None)
    form = CheckoutForm(request.POST or None, initial={"delivery_address": getattr(profile, "address", "")})
    promo, subtotal = None, rec.quoted_price
    if request.method == "POST" and form.is_valid():
        promo, promo_error = check_promo(form.cleaned_data["promo_code"])
        if promo_error:
            form.add_error("promo_code", promo_error)
        else:
            try:
                with transaction.atomic():
                    order = create_order(
                        request.user, rec, form.cleaned_data["delivery_address"], promo,
                        reference=f"MOCK-{uuid.uuid4().hex[:10].upper()}")
            except NoUnitFree:
                messages.error(request, "Sorry, that robot was just booked by someone else for these dates.")
                return redirect("orders:cart")
            request.session.pop(CART_KEY, None)
            return redirect("orders:confirmation", pk=order.pk)
    discount = discount_for(subtotal, promo)
    return render(request, "orders/checkout.html", {
        "form": form, "rec": rec, "subtotal": subtotal, "discount": discount, "total": subtotal - discount})


@login_required
def confirmation(request, pk):
    order = get_object_or_404(Order, pk=pk, customer=request.user)
    return render(request, "orders/confirmation.html", {"order": order, "items": order.items.all()})


@login_required
def order_list(request):
    # TODO(S12): customer's order history with rebook button.
    return _todo(request, "S12", "My orders")


@login_required
def order_detail(request, pk):
    """S11: status timeline built from OrderStatusEvent."""
    order = get_object_or_404(Order, pk=pk, customer=request.user)
    steps = [(st, st.label) for st in FLOW]
    reached = {e.status for e in order.events.all()}
    return render(request, "orders/order_detail.html", {
        "order": order, "items": order.items.all(), "events": order.events.all(),
        "steps": [(label, st in reached) for st, label in steps],
        "cancelled": order.status == Order.Status.CANCELLED,
    })
