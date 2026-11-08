"""Reviews and after-sales support. Backlog items S13-S14. To be implemented by the team."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def _todo(request, story, title):
    return render(request, "coming_soon.html", {"story": story, "title": title})


@login_required
def review_new(request, order_pk):
    # TODO(S13): only for COMPLETED/COLLECTED orders owned by the user, one review per order.
    return _todo(request, "S13", "Rate your job")


@login_required
def ticket_list(request):
    # TODO(S14): customer's tickets.
    return _todo(request, "S14", "Support tickets")


@login_required
def ticket_new(request):
    # TODO(S14): optional order link; priority URGENT if the order is ON_SITE or RUNNING.
    return _todo(request, "S14", "New support ticket")


@login_required
def ticket_detail(request, pk):
    # TODO(S14): message thread + reply form.
    return _todo(request, "S14", f"Ticket #{pk}")
