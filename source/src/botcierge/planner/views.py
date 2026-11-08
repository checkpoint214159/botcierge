from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .decomposer import CATEGORY_CONFIDENCE_FLOOR, decompose
from .forms import TaskRequestForm
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
        initial = {}
        if hasattr(request.user, "profile"):
            initial["housing_type"] = request.user.profile.housing_type
        form = TaskRequestForm(initial=initial)
    return render(request, "planner/start.html", {"form": form})


@login_required
def result(request, pk):
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
    })


@login_required
def my_plans(request):
    """S15: list of the customer's saved task plans."""
    plans = TaskRequest.objects.filter(customer=request.user).select_related("spec")
    return render(request, "planner/my_plans.html", {"plans": plans})
