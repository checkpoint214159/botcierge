"""Custom staff panel (the brief bans django.contrib.admin). Backlog items A02-A14.

Catalogue management (A03 robots, A04 fleet, A05 add-ons and skill packs) uses one pattern:
a list page, a shared add/edit form page (staffpanel/form.html) and, where it makes sense, a POST-only
switch to list or unlist an item. Nothing is ever deleted, because past orders point at these rows.
"""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalog.checks import catalogue_issues
from catalog.models import AddOn, FleetUnit, RobotModel, SkillPack
from catalog.taxonomy import PLATFORM_CHOICES, TASK_CATEGORY_CHOICES
from orders.models import Order, OrderItem
from orders.services import ONGOING, advance_order, assignable_units, next_status
from planner.ml_registry import coverage, learned_codes, model_cards

from .forms import AddOnForm, FleetUnitForm, RobotModelForm, SkillPackForm

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url="accounts:login")


def _todo(request, story, title):
    return render(request, "coming_soon.html", {"story": story, "title": title, "staff": True})


@staff_required
def dashboard(request):
    # TODO(A02): KPIs - bookings, revenue, fleet utilisation, ML recommendation acceptance rate.
    return _todo(request, "A02", "Staff dashboard")


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


# ---------------------------------------------------------------- shared catalogue helpers

def _issues_for(obj=None):
    """Every catalogue sync issue (they're linked, e.g. a robot change can fix a skill pack warning),
    with the ones about the item being edited marked and listed first."""
    issues = catalogue_issues()
    for i in issues:
        i["mine"] = obj is not None and obj.pk is not None and i["obj"] == obj
    return sorted(issues, key=lambda i: not i["mine"])


def _form_page(request, form, *, title, back, intro="", aside=None):
    """Render the shared add/edit page. aside = list of (label, value) shown beside the form."""
    return render(request, "staffpanel/form.html", {
        "form": form, "title": title, "back": back, "intro": intro,
        "aside": aside or [], "issues": _issues_for(form.instance)})


def _save(request, form, what, list_url):
    """Save a valid bound form, flash a message and go back to the list (Post/Redirect/Get)."""
    created = form.instance.pk is None
    obj = form.save()
    messages.success(request, f"{'Added' if created else 'Saved'} {what} \"{obj}\".")
    return redirect(list_url)


def _toggle_active(request, model, pk, list_url, on="listed", off="unlisted"):
    obj = get_object_or_404(model, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    messages.success(request, f"\"{obj}\" is now {on if obj.is_active else off}.")
    return redirect(list_url)


def _upcoming_by_robot():
    """Robot model id -> number of live orders still using it."""
    counts = {}
    for rid in (OrderItem.objects.filter(kind=OrderItem.Kind.ROBOT, order__status__in=ONGOING)
                .values_list("robot_model_id", flat=True)):
        counts[rid] = counts.get(rid, 0) + 1
    return counts


# ---------------------------------------------------------------- A03 robot models

@staff_required
def robot_list(request):
    robots = list(RobotModel.objects.prefetch_related("units").order_by("-is_active", "platform", "daily_rate"))
    upcoming = _upcoming_by_robot()
    labels = dict(TASK_CATEGORY_CHOICES)
    for r in robots:
        r.category_names = [labels.get(c, c) for c in r.category_list]
        units = list(r.units.all())
        r.n_units = len(units)
        r.n_bookable = sum(u.status not in (FleetUnit.Status.MAINTENANCE, FleetUnit.Status.RETIRED) for u in units)
        r.n_upcoming = upcoming.get(r.pk, 0)
    return render(request, "staffpanel/robot_list.html", {
        "robots": robots, "issues": _issues_for()})


@staff_required
def robot_edit(request, pk=None):
    robot = get_object_or_404(RobotModel, pk=pk) if pk else RobotModel()
    form = RobotModelForm(request.POST or None, request.FILES or None, instance=robot)
    if request.method == "POST" and form.is_valid():
        return _save(request, form, "robot", "staffpanel:robot_list")
    aside = []
    if robot.pk:
        aside = [("Units", robot.units.count()),
                 ("Live orders", _upcoming_by_robot().get(robot.pk, 0)),
                 ("Skill packs", ", ".join(sp.name for sp in robot.skill_packs.all()) or "none")]
    return _form_page(request, form, title=f"Edit {robot.name}" if robot.pk else "Add a robot",
                      back=reverse("staffpanel:robot_list"), aside=aside,
                      intro="Unlisting a robot hides it from customers and the planner. Orders already "
                            "booked with it still go ahead.")


@staff_required
@require_POST
def robot_toggle(request, pk):
    return _toggle_active(request, RobotModel, pk, "staffpanel:robot_list")


# ---------------------------------------------------------------- A04 fleet units

SERVICE_INTERVAL_DAYS = 90  # a unit not serviced for this long is flagged


@staff_required
def fleet_list(request):
    units = FleetUnit.objects.select_related("robot_model").order_by("robot_model__name", "serial_number")
    robot_id, status = request.GET.get("robot", ""), request.GET.get("status", "")
    counts = {s: 0 for s, _ in FleetUnit.Status.choices}
    for st in units.values_list("status", flat=True):
        counts[st] += 1
    if robot_id:
        units = units.filter(robot_model_id=robot_id)
    if status:
        units = units.filter(status=status)
    units = list(units)

    # next live booking per unit, so staff see what a status change would affect
    next_order = {}
    for item in (OrderItem.objects.filter(fleet_unit__in=units, order__status__in=ONGOING)
                 .select_related("order").order_by("order__start_date")):
        next_order.setdefault(item.fleet_unit_id, item.order)
    due = timezone.localdate() - timedelta(days=SERVICE_INTERVAL_DAYS)
    for u in units:
        u.next_order = next_order.get(u.pk)
        u.service_due = u.status != FleetUnit.Status.RETIRED and (u.last_serviced is None or u.last_serviced < due)
    return render(request, "staffpanel/fleet_list.html", {
        "units": units, "robots": RobotModel.objects.order_by("name"),
        "statuses": FleetUnit.Status.choices, "counts": counts,
        "selected_robot": robot_id, "selected_status": status,
        "service_days": SERVICE_INTERVAL_DAYS, "issues": _issues_for()})


@staff_required
def fleet_edit(request, pk=None):
    unit = get_object_or_404(FleetUnit, pk=pk) if pk else FleetUnit()
    initial = {"robot_model": request.GET.get("robot")} if not pk else None
    form = FleetUnitForm(request.POST or None, instance=unit, initial=initial)
    if request.method == "POST" and form.is_valid():
        return _save(request, form, "unit", "staffpanel:fleet_list")
    aside = []
    if unit.pk:
        orders = (Order.objects.filter(items__fleet_unit=unit, status__in=ONGOING)
                  .order_by("start_date").distinct())
        aside = [("Live orders", ", ".join(f"#{o.pk} ({o.start_date:%d %b})" for o in orders) or "none")]
    return _form_page(request, form, title=f"Edit {unit}" if unit.pk else "Add a fleet unit",
                      back=reverse("staffpanel:fleet_list"), aside=aside,
                      intro="Units in maintenance or retired can't be booked. A unit that is booked "
                            "can't be taken out of service until its order has another unit.")


# ---------------------------------------------------------------- A05 add-ons and skill packs

@staff_required
def addon_list(request):
    learned = learned_codes()["addons"]
    addons = list(AddOn.objects.order_by("-is_active", "name"))
    labels = dict(PLATFORM_CHOICES)
    for a in addons:
        a.learned = a.code in learned
        a.platform_names = [labels.get(p, p) for p in a.platform_list]
    return render(request, "staffpanel/addon_list.html", {"addons": addons, "issues": _issues_for()})


@staff_required
def addon_edit(request, pk=None):
    addon = get_object_or_404(AddOn, pk=pk) if pk else AddOn()
    form = AddOnForm(request.POST or None, instance=addon)
    if request.method == "POST" and form.is_valid():
        return _save(request, form, "attachment", "staffpanel:addon_list")
    learned = addon.code in learned_codes()["addons"] if addon.pk else False
    return _form_page(request, form, title=f"Edit {addon.name}" if addon.pk else "Add an attachment",
                      back=reverse("staffpanel:addon_list"),
                      aside=[("Recommender (M3)", "suggests this" if learned else "doesn't know this yet")],
                      intro="Customers can add any listed attachment that fits their robot. The recommender only "
                            "suggests attachments it was trained on; new ones need a retrain.")


@staff_required
@require_POST
def addon_toggle(request, pk):
    return _toggle_active(request, AddOn, pk, "staffpanel:addon_list", on="offered", off="hidden")


@staff_required
def skillpack_list(request):
    learned = learned_codes()["skill_packs"]
    labels = dict(TASK_CATEGORY_CHOICES)
    packs = list(SkillPack.objects.prefetch_related("compatible_robots").order_by("-is_active", "name"))
    for p in packs:
        p.learned = p.code in learned
        p.category_names = [labels.get(c, c) for c in p.category_list]
        p.robot_names = [r.name for r in p.compatible_robots.all() if r.is_active]
    return render(request, "staffpanel/skillpack_list.html", {
        "packs": packs, "issues": _issues_for()})


@staff_required
def skillpack_edit(request, pk=None):
    pack = get_object_or_404(SkillPack, pk=pk) if pk else SkillPack()
    form = SkillPackForm(request.POST or None, instance=pack)
    if request.method == "POST" and form.is_valid():
        return _save(request, form, "skill pack", "staffpanel:skillpack_list")
    learned = pack.code in learned_codes()["skill_packs"] if pack.pk else False
    return _form_page(request, form, title=f"Edit {pack.name}" if pack.pk else "Add a skill pack",
                      back=reverse("staffpanel:skillpack_list"),
                      aside=[("Recommender (M4)", "suggests this" if learned else "doesn't know this yet")],
                      intro="The booking page offers a pack when the job's task type is ticked and the "
                            "chosen robot is in its robot list.")


@staff_required
@require_POST
def skillpack_toggle(request, pk):
    return _toggle_active(request, SkillPack, pk, "staffpanel:skillpack_list", on="offered", off="hidden")


# ---------------------------------------------------------------- recommendation models page

@staff_required
def ml_models(request):
    """The ML recommenders (M1-M5): what each decides, how well it scored, and whether it knows the current catalogue.
    Named "recommendation models" for staff so they aren't confused with skill packs (the robot's own software)."""
    return render(request, "staffpanel/ml_models.html", {
        "cards": model_cards(), "sections": coverage(), "issues": _issues_for()})
