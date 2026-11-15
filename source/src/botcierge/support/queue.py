"""A09: the staff support queue.

Customers' drafts never appear here: a ticket only reaches staff once the customer submits it (S14).
Queue order: urgent tickets first (the robot was in the customer's home when they wrote in), then
normal, then low. Within each group, the ticket that has waited longest comes first.

Staff reply on the ticket page. A reply can be saved as a draft first (SupportTicket.reply_draft),
which the customer never sees; sending it adds a TicketMessage, which shows on the customer's
support page.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from orders.models import Order
from staffpanel.queue import group_by

from .models import SupportTicket, TicketMessage

T = SupportTicket.Status
P = SupportTicket.Priority

# tab code -> (label, ticket statuses in it). Drafts are in none of them.
TABS = {
    "open": ("To answer", [T.OPEN]),
    "in_progress": ("In progress", [T.IN_PROGRESS]),
    "done": ("Resolved", [T.RESOLVED, T.CLOSED]),
}
PRIORITY_RANK = Case(When(priority=P.URGENT, then=Value(0)), When(priority=P.NORMAL, then=Value(1)),
                     default=Value(2), output_field=IntegerField())
GROUP_LABELS = {P.URGENT: "Urgent: robot was with the customer", P.NORMAL: "Normal", P.LOW: "Low"}
ROBOT_IN_HOME = [Order.Status.ON_SITE, Order.Status.RUNNING]


def ticket_queue(tab="open"):
    statuses = TABS.get(tab, TABS["open"])[1]
    return list(SupportTicket.objects.filter(status__in=statuses)
                .select_related("customer", "order")
                .annotate(rank=PRIORITY_RANK)
                .order_by("rank", "submitted_at", "pk"))


def tab_counts():
    return {code: SupportTicket.objects.filter(status__in=statuses).count()
            for code, (_, statuses) in TABS.items()}


def tab_of(ticket) -> str:
    return next((code for code, (_, statuses) in TABS.items() if ticket.status in statuses), "open")


def grouped(tickets):
    return group_by(tickets, key=lambda t: t.priority, label=lambda p: GROUP_LABELS.get(p, p))


def waiting_label(ticket) -> str:
    """How long the customer has been waiting, in words."""
    if not ticket.submitted_at:
        return ""
    hours = (timezone.now() - ticket.submitted_at).total_seconds() / 3600
    if hours < 1:
        return "just now"
    if hours < 24:
        return f"{int(hours)} h ago"
    days = int(hours // 24)
    return f"{days} day{'s' if days > 1 else ''} ago"


def ticket_flags(ticket) -> list[str]:
    """Short reasons to look sooner, like the A08 risk flags."""
    flags = []
    order = ticket.order
    if order and order.status in ROBOT_IN_HOME:
        flags.append("Robot is with the customer now")
    if ticket.category == SupportTicket.Category.SAFETY:
        flags.append("Damage or safety")
    if ticket.status == T.OPEN and ticket.submitted_at and timezone.now() - ticket.submitted_at > timedelta(days=1):
        flags.append("Waiting over a day")
    if order and order.review_status == Order.Review.REJECTED and order.status == Order.Status.CONFIRMED:
        flags.append("Order also needs follow-up before dispatch")
    return flags


def save_draft(ticket, body):
    ticket.reply_draft = body
    ticket.save(update_fields=["reply_draft", "updated_at"])


@transaction.atomic
def send_reply(ticket, user, body, resolve=False):
    """Post the reply to the customer and clear the draft. A first reply moves a ticket from
    'to answer' to 'in progress'; resolve=True closes it off in the same step."""
    TicketMessage.objects.create(ticket=ticket, author=user, body=body)
    ticket.reply_draft = ""
    if resolve:
        ticket.status = T.RESOLVED
    elif ticket.status == T.OPEN:
        ticket.status = T.IN_PROGRESS
    ticket.save(update_fields=["reply_draft", "status", "updated_at"])
