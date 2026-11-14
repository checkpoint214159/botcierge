from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from orders.models import Order

from .decomposer import CATEGORY_CONFIDENCE_FLOOR, decompose
from .forms import TaskRequestForm
from .models import TaskRequest
from .pricing import rec_quote_lines


@login_required
def start(request):
    """S04-S06: customer describes the task, the space and the constraints."""
    if request.method == "POST":
        form = TaskRequestForm(request.POST, request.FILES)
        if form.is_valid():
            task_request = form.save(commit=False)
            task_request.customer = request.user
            if not form.cleaned_data.get("housing_type") and hasattr(request.user, "profile"):
                task_request.housing_type = request.user.profile.housing_type
            # price delivery straight away if the customer has a default address (changeable at booking)
            task_request.address = request.user.addresses.filter(is_default=True).first()
            task_request.save()
            decompose(task_request)
            return redirect("planner:result", pk=task_request.pk)
    else:
        initial = request.GET.dict()  # conveniently allow prefill, because why not
        if hasattr(request.user, "profile"):
            initial["housing_type"] = request.user.profile.housing_type
        form = TaskRequestForm(initial=initial)
    return render(request, "planner/start.html", {"form": form})


@login_required
def result(request, pk):
    # found at /plan/pk. we gotta match pk of result against the auth_user(id)
    """S07: show the decomposition and the recommended robot, add-ons, skill pack and quote."""
    task_request = get_object_or_404(TaskRequest, pk=pk, customer=request.user)
    rec = task_request.recommendations.first()  # newest first
    spec = getattr(task_request, "spec", None)
    if rec is None or spec is None:
        messages.warning(request, "We could not build a plan for this request yet.")
        return redirect("planner:start")
    order = None
    if task_request.status == TaskRequest.Status.BOOKED:
        order = Order.objects.filter(recommendation__task_request=task_request, customer=request.user).first()
    return render(request, "planner/result.html", {
        "tr": task_request,
        "spec": spec,
        "rec": rec,
        "lines": rec_quote_lines(rec),
        "order": order,
        "low_confidence": spec.category_confidence < CATEGORY_CONFIDENCE_FLOOR,
        "reasons": explain(task_request, spec, rec),
    })


def explain(tr, spec, rec):
    """S17: plain-language reasons for the recommendation. Deliberately excludes the
    staff-only policy_conditioning JSON."""
    reasons = []
    if rec.source == rec.Source.CUSTOMER:
        reasons.append("You changed the robot, attachments or skill pack, so this setup is your own choice.")
    if rec.robot_model:
        reasons.append(
            f"{rec.robot_model.name} is the lowest-priced {rec.robot_model.get_platform_display().lower()} "
            f"robot that can carry {tr.payload_kg} kg"
            f"{' and handle stairs' if tr.has_stairs else ''}{' and work outdoors' if tr.is_outdoor else ''}."
            if rec.source == rec.Source.ML else
            f"{rec.robot_model.name} meets your payload{', stairs' if tr.has_stairs else ''}"
            f"{' and outdoor' if tr.is_outdoor else ''} needs.")
    if rec.source == rec.Source.ML and rec.predicted_platform:
        reasons.append(
            f"Our model matched your task to a {rec.predicted_platform.replace('_', ' ')} platform "
            f"({round(rec.platform_confidence * 100)}% match).")
    for a in rec.addons.all():
        reasons.append(f"{a.name} was added because it suits {spec.get_task_category_display().lower()} jobs.")
    if rec.skill_pack:
        reasons.append(f"The {rec.skill_pack.name} skill pack is tuned for {spec.get_task_category_display().lower()}.")
    reasons.append(
        f"We estimate {spec.est_robot_hours:.1f} robot hours, so we quoted {spec.est_days_needed} day(s).")
    return reasons


@login_required
def my_plans(request):
    """S15: list of the customer's saved task plans."""
    plans = list(TaskRequest.objects.filter(customer=request.user).select_related("spec"))
    # booked plans link to their order instead of offering to book again
    orders = dict(Order.objects.filter(customer=request.user, recommendation__isnull=False)
                  .values_list("recommendation__task_request_id", "pk"))
    for p in plans:
        p.order_id = orders.get(p.pk)
    return render(request, "planner/my_plans.html", {"plans": plans})
