"""Custom staff panel (the brief bans django.contrib.admin). Backlog items A01-A12."""
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from orders.models import Order
from orders.services import advance_order, assignable_units, next_status

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url="accounts:login")


def _todo(request, story, title):
    return render(request, "coming_soon.html", {"story": story, "title": title, "staff": True})


@staff_required
def dashboard(request):
    # TODO(A02): KPIs - bookings, revenue, fleet utilisation, ML recommendation acceptance rate.
    return _todo(request, "A02", "Staff dashboard")


@staff_required
def robot_list(request):
    # TODO(A03): CRUD for RobotModel.
    return _todo(request, "A03", "Robot catalogue")


@staff_required
def fleet_list(request):
    # TODO(A04): FleetUnit inventory with status changes.
    return _todo(request, "A04", "Fleet units")


@staff_required
def order_list(request):
    """A07: all orders, newest first, optionally filtered by status."""
    status = request.GET.get("status", "")
    orders = Order.objects.select_related("customer")
    if status:
        orders = orders.filter(status=status)
    return render(request, "staffpanel/order_list.html", {
        "orders": orders, "statuses": Order.Status.choices, "selected": status})


@staff_required
def order_detail(request, pk):
    """A07: assign a fleet unit and advance the order; writes OrderStatusEvent for the customer's timeline."""
    order = get_object_or_404(Order, pk=pk)
    item, units = assignable_units(order)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "assign":
            unit = units.filter(pk=request.POST.get("unit")).first()
            if unit is None:
                messages.error(request, "That unit is not free for these dates.")
            else:
                item.fleet_unit = unit
                item.save(update_fields=["fleet_unit"])
                messages.success(request, f"Assigned {unit}.")
        elif action == "advance":
            if item.fleet_unit_id is None:
                messages.error(request, "Assign a fleet unit before advancing the order.")
            elif advance_order(order, request.user, request.POST.get("note", "").strip()):
                messages.success(request, f"Order moved to {order.get_status_display()}.")
        return redirect("staffpanel:order_detail", pk=order.pk)
    nxt = next_status(order)
    return render(request, "staffpanel/order_detail.html", {
        "order": order, "item": item, "units": units, "items": order.items.all(),
        "events": order.events.select_related("created_by"),
        "next_label": Order.Status(nxt).label if nxt else None})


@staff_required
def request_list(request):
    # TODO(A08): TaskRequests with ML output, full policy_conditioning JSON, staff override.
    return _todo(request, "A08", "Task requests & ML output")


@staff_required
def ticket_list(request):
    # TODO(A09): support queue.
    return _todo(request, "A09", "Support tickets")
