from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, render

from .models import RobotModel, SkillPack
from .taxonomy import PLATFORM_CHOICES


def home(request):
    """Landing page: value proposition + entry point into the planner."""
    featured = RobotModel.objects.filter(is_active=True)[:4]
    return render(request, "catalog/home.html", {"featured": featured})


def robot_list(request):
    """S02: browse the robot catalogue with simple filters."""
    robots = RobotModel.objects.filter(is_active=True).annotate(
        avg_rating=Avg("reviews__rating", filter=Q(reviews__is_visible=True)))
    platform = request.GET.get("platform", "")
    outdoor = request.GET.get("outdoor") == "1"
    q = request.GET.get("q", "").strip()
    if platform:
        robots = robots.filter(platform=platform)
    if outdoor:
        robots = robots.filter(outdoor=True)
    if q:
        robots = robots.filter(Q(name__icontains=q) | Q(tagline__icontains=q) | Q(description__icontains=q))
    return render(request, "catalog/robot_list.html", {
        "robots": robots, "platforms": PLATFORM_CHOICES,
        "selected_platform": platform, "outdoor": outdoor, "q": q,
    })


def robot_detail(request, slug):
    """S03: robot detail with compatible skill packs and reviews."""
    robot = get_object_or_404(RobotModel, slug=slug, is_active=True)
    reviews = robot.reviews.filter(is_visible=True).select_related("customer")
    stats = reviews.aggregate(avg=Avg("rating"), n=Count("id"))
    return render(request, "catalog/robot_detail.html", {
        "robot": robot,
        "skill_packs": robot.skill_packs.filter(is_active=True),
        "reviews": reviews[:10],
        "stats": stats,
    })
