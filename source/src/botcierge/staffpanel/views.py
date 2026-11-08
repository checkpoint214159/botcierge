"""Custom staff panel (the brief bans django.contrib.admin). Backlog items A01-A12."""
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render

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
    # TODO(A07): orders, assign FleetUnit, advance status (writes OrderStatusEvent).
    return _todo(request, "A07", "Orders")


@staff_required
def request_list(request):
    # TODO(A08): TaskRequests with ML output, full policy_conditioning JSON, staff override.
    return _todo(request, "A08", "Task requests & ML output")


@staff_required
def ticket_list(request):
    # TODO(A09): support queue.
    return _todo(request, "A09", "Support tickets")
