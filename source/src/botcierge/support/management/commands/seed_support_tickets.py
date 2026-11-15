"""Raise test support tickets on the seed_review_orders bookings, so the staff queue (A09) has work.

    python manage.py seed_review_orders      # the orders first
    python manage.py seed_support_tickets    # then the tickets (--reset to replace them)

Covers each tab and flag: an urgent ticket, one waiting over a day, a safety one with a staff draft
reply, one in progress, a resolved one, one on an order that also failed plan review, and a customer
draft that must NOT show up for staff.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Order
from support.models import SupportTicket, TicketMessage

S, P, C = SupportTicket.Status, SupportTicket.Priority, SupportTicket.Category

# payment reference of the seeded order, hours since sent, status, priority, category, subject, text, extras
TICKETS = [
    ("TEST-000", 3, S.OPEN, P.URGENT, C.ROBOT, "Robot keeps getting stuck under the sofa",
     "It has tried to go under the sofa five times and beeps every time. The cat is scared of it now.", {}),
    ("TEST-001", 30, S.OPEN, P.NORMAL, C.SCHEDULE, "Can the robot come at 2pm instead?",
     "The party starts at 6pm but we are out in the morning. Can delivery be after 2pm?", {}),
    ("TEST-002", 5, S.OPEN, P.NORMAL, C.SAFETY, "Is the mop water safe around a toddler?",
     "My son puts everything in his mouth. What cleaning liquid does the robot use?",
     {"draft": "Hi Mei Ling, the mop uses plain water unless you add your own cleaner. We can also set the robot "}),
    ("TEST-010", 8, S.OPEN, P.NORMAL, C.SCHEDULE, "Pool cleaning date",
     "Can the pool robot come a day earlier? The leaves are getting worse.", {}),
    ("TEST-005", 50, S.IN_PROGRESS, P.NORMAL, C.BILLING, "Was I charged twice?",
     "My card shows two charges for the lawn mowing booking.",
     {"reply": "Hi Ravi, we only see one payment on our side. Could you send a screenshot of the two charges?"}),
    ("TEST-007", 72, S.RESOLVED, P.LOW, C.OTHER, "Do I need to be home during the patrol?",
     "We will be overseas. Does someone need to let the robot in?",
     {"reply": "No need. Our team will let it in with the access code you gave us and collect it after."}),
    ("TEST-003", 1, S.DRAFT, P.NORMAL, C.ROBOT, "Half-written question about the robot",
     "", {}),  # a customer draft: staff must never see this one
]


class Command(BaseCommand):
    help = "Raise test support tickets on the seed_review_orders bookings for the staff queue (A09)"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="delete the test customers' tickets first")

    def handle(self, *args, **opts):
        testers = User.objects.filter(username__in=["tester1", "tester2", "tester3", "tester4"])
        if opts["reset"]:
            SupportTicket.objects.filter(customer__in=testers).delete()
        staff = User.objects.filter(is_staff=True).first()
        now = timezone.now()
        made, skipped = 0, []
        for ref, hours, status, priority, category, subject, text, extra in TICKETS:
            order = Order.objects.filter(payment__reference=ref, customer__in=testers).order_by("-pk").first()
            if order is None:
                skipped.append(f"{subject} (no order {ref}: run seed_review_orders first)")
                continue
            if SupportTicket.objects.filter(order=order).exists():
                skipped.append(f"{subject} (order #{order.pk} already has a ticket)")
                continue
            sent = now - timedelta(hours=hours)
            t = SupportTicket.objects.create(
                customer=order.customer, order=order, subject=subject, category=category, description=text,
                status=status, priority=priority, reply_draft=extra.get("draft", ""),
                submitted_at=None if status == S.DRAFT else sent)
            if extra.get("reply") and staff:
                m = TicketMessage.objects.create(ticket=t, author=staff, body=extra["reply"])
                TicketMessage.objects.filter(pk=m.pk).update(created_at=sent + timedelta(hours=4))
            SupportTicket.objects.filter(pk=t.pk).update(created_at=sent, updated_at=sent)  # bypass auto_now
            made += 1
        self.stdout.write(self.style.SUCCESS(f"Raised {made} test tickets (one is a customer draft staff shouldn't see)."))
        for s in skipped:
            self.stdout.write(self.style.WARNING(f"  skipped: {s}"))
