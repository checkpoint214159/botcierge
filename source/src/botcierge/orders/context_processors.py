"""Adds cart_count to every template so the navbar badge works on every page."""
from planner.models import TaskRequest


def cart(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or user.is_staff:
        return {}
    return {"cart_count": TaskRequest.objects.filter(customer=user, status=TaskRequest.Status.PLANNED).count()}
