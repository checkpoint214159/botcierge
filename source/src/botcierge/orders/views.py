"""Orders: cart, checkout, tracking. Backlog items S09-S12. To be implemented by the team."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def _todo(request, story, title):
    return render(request, "coming_soon.html", {"story": story, "title": title})


@login_required
def cart(request):
    # TODO(S09): session-based cart holding a Recommendation id; check FleetUnit availability for the dates.
    return _todo(request, "S09", "Booking cart")


@login_required
def checkout(request):
    # TODO(S10): create Order + OrderItems from the selected Recommendation, apply PromoCode,
    #            mock Payment, first OrderStatusEvent, mark FleetUnit RESERVED.
    return _todo(request, "S10", "Checkout")


@login_required
def order_list(request):
    # TODO(S12): customer's order history with rebook button.
    return _todo(request, "S12", "My orders")


@login_required
def order_detail(request, pk):
    # TODO(S11): status timeline from OrderStatusEvent, links to review (S13) and support (S14).
    return _todo(request, "S11", f"Order #{pk}")
