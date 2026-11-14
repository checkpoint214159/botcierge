"""Reviews and after-sales support. S14 support built; S13 reviews still to do.

Support is one page: pick one of your orders, then either see its ticket or fill one in.
Every other entry point (the order page, old ticket links) just opens this page with an order picked.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from orders.models import Order
from orders.services import order_summary

from .forms import SupportTicketForm
from .models import SupportTicket

URGENT_STATUSES = [Order.Status.ON_SITE, Order.Status.RUNNING]  # robot is in the customer's home right now


def _todo(request, story, title):
    return render(request, "coming_soon.html", {"story": story, "title": title})


@login_required
def review_new(request, order_pk):
    # TODO(S13): only for COMPLETED/COLLECTED orders owned by the user, one review per order.
    return _todo(request, "S13", "Rate your job")


def _support_url(order_pk=None):
    url = reverse("support:ticket_list")
    return f"{url}?order={order_pk}" if order_pk else url


@login_required
def ticket_list(request):
    """S14. GET ?order=<pk> shows that order's ticket (or an empty form). POST saves a draft or submits."""
    orders = list(Order.objects.filter(customer=request.user).order_by("-created_at"))
    tickets = {t.order_id: t for t in SupportTicket.objects.filter(customer=request.user, order__isnull=False)}
    for o in orders:
        o.ticket = tickets.get(o.pk)

    order_pk = request.POST.get("order") if request.method == "POST" else request.GET.get("order")
    order = get_object_or_404(Order, pk=order_pk, customer=request.user) if order_pk else None
    ticket = tickets.get(order.pk) if order else None

    form = None
    if order and (ticket is None or ticket.is_draft):
        submitting = request.POST.get("action") == "submit"
        form = SupportTicketForm(request.POST or None, instance=ticket, submitting=submitting)
        if request.method == "POST" and form.is_valid():
            ticket = form.save(commit=False)
            ticket.customer, ticket.order = request.user, order  # from the session and our own lookup
            if submitting:
                ticket.status = SupportTicket.Status.OPEN
                ticket.submitted_at = timezone.now()
                ticket.priority = (SupportTicket.Priority.URGENT if order.status in URGENT_STATUSES
                                   else SupportTicket.Priority.NORMAL)
            ticket.save()
            if submitting:
                urgent = " We've marked it urgent because the robot is with you now." if ticket.priority == "urgent" else ""
                messages.success(request, f"Ticket #{ticket.pk} sent. We'll reply by email.{urgent}")
            else:
                messages.info(request, "Draft saved. It isn't sent until you press Submit.")
            return redirect(_support_url(order.pk))
    elif request.method == "POST":
        messages.warning(request, "That ticket was already sent. Email us to add anything.")
        return redirect(_support_url(order.pk if order else None))

    return render(request, "support/support.html", {
        "orders": orders, "order": order, "ticket": ticket, "form": form,
        "summary": order_summary(order) if order else None,
        "replies": ticket.messages.select_related("author") if ticket and ticket.pk else [],
    })


@login_required
def ticket_new(request):
    """Old entry point: open the support page, keeping any ?order= the link carried."""
    return redirect(_support_url(request.GET.get("order")))


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(SupportTicket, pk=pk, customer=request.user)
    return redirect(_support_url(ticket.order_id))
