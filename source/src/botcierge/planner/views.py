from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .decomposer import CATEGORY_CONFIDENCE_FLOOR, decompose, save_customer_edit
from .forms import SwapForm, TaskRequestForm
from .models import TaskRequest


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
    b = rec.price_breakdown
    days = b.get("rental_days", 1)
    lines = []
    if rec.robot_model:
        lines.append((f"{rec.robot_model.name} × {days} day(s)", b.get("robot", 0)))
    for a in rec.addons.all():
        lines.append((f"{a.name} × {days} day(s)", b.get(f"addon:{a.code}", 0)))
    if rec.skill_pack:
        lines.append((f"{rec.skill_pack.name} skill pack", b.get("skill_pack", 0)))
    lines.append(("Delivery, setup and collection", b.get("delivery_and_setup", 0)))
    return render(request, "planner/result.html", {
        "tr": task_request,
        "spec": spec,
        "rec": rec,
        "lines": lines,
        "low_confidence": spec.category_confidence < CATEGORY_CONFIDENCE_FLOOR,
        "reasons": explain(task_request, spec, rec),
    })


def explain(tr, spec, rec):
    """S17: plain-language reasons for the recommendation. Deliberately excludes the
    staff-only policy_conditioning JSON."""
    reasons = []
    if rec.source == rec.Source.CUSTOMER:
        reasons.append("You changed the robot or attachments, so this setup is your own choice.")
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
def swap(request, pk):
    """S08: swap the robot or add-ons; the quote is recomputed and saved as source=CUSTOMER."""
    task_request = get_object_or_404(TaskRequest, pk=pk, customer=request.user)
    rec = task_request.recommendations.first()
    if rec is None or not hasattr(task_request, "spec"):
        return redirect("planner:start")
    if request.method == "POST":
        form = SwapForm(request.POST, task_request=task_request)
        if form.is_valid():
            save_customer_edit(rec, form.cleaned_data["robot"], list(form.cleaned_data["addons"]))
            messages.success(request, "Your changes are saved and the quote is updated.")
            return redirect("planner:result", pk=task_request.pk)
    else:
        form = SwapForm(task_request=task_request,
                        initial={"robot": rec.robot_model, "addons": rec.addons.all()})
    return render(request, "planner/swap.html", {"tr": task_request, "rec": rec, "form": form})


@login_required
def my_plans(request):
    """S15: list of the customer's saved task plans."""
    plans = TaskRequest.objects.filter(customer=request.user).select_related("spec")
    return render(request, "planner/my_plans.html", {"plans": plans})
