from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Address
from orders.models import Order
from orders.services import create_order
from planner.decomposer import decompose
from planner.models import TaskRequest

from .models import SupportTicket


class SupportTests(TestCase):
    """S14: one ticket per order, drafts editable, submitted tickets read-only."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.user = User.objects.get(username="demo")

    def setUp(self):
        self.client.login(username="demo", password="demopass123")
        tr = TaskRequest.objects.create(
            customer=self.user, description="mop and vacuum my flat", area_m2=90, num_rooms=4, floor_type="tile",
            budget_sgd=500, start_date=date.today() + timedelta(days=3), deadline_date=date.today() + timedelta(days=5),
            hours_per_day=4, address=Address.objects.get(customer=self.user))
        self.order = create_order(self.user, decompose(tr), "1 Test Rd", None)
        self.url = reverse("support:ticket_list")

    def post(self, action, **kw):
        data = {"order": self.order.pk, "category": "robot", "subject": "Stopped halfway",
                "description": "It stopped in the kitchen.", "action": action}
        data.update(kw)
        return self.client.post(self.url, data)

    def test_order_page_links_to_support_with_order_picked(self):
        resp = self.client.get(reverse("orders:order_detail", args=[self.order.pk]))
        self.assertContains(resp, f"{self.url}?order={self.order.pk}")
        page = self.client.get(self.url, {"order": self.order.pk})
        self.assertContains(page, "New ticket")

    def test_draft_then_submit(self):
        self.post("draft", description="")  # drafts may be half-written
        t = SupportTicket.objects.get()
        self.assertEqual(t.status, SupportTicket.Status.DRAFT)
        self.assertContains(self.client.get(self.url), "draft saved")
        self.post("submit")
        t.refresh_from_db()
        self.assertEqual(t.status, SupportTicket.Status.OPEN)
        self.assertIsNotNone(t.submitted_at)
        self.assertEqual(SupportTicket.objects.count(), 1)  # same ticket, not a second one

    def test_submit_needs_a_description(self):
        resp = self.post("submit", description="")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(SupportTicket.objects.exists())

    def test_submitted_ticket_is_read_only(self):
        self.post("submit")
        self.post("submit", subject="Changed my mind")
        self.assertEqual(SupportTicket.objects.get().subject, "Stopped halfway")
        page = self.client.get(self.url, {"order": self.order.pk})
        self.assertContains(page, "Ticket #")
        self.assertNotContains(page, "Submit ticket")

    def test_urgent_when_robot_is_on_site(self):
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.ON_SITE)
        self.post("submit")
        self.assertEqual(SupportTicket.objects.get().priority, SupportTicket.Priority.URGENT)

    def test_cannot_raise_ticket_on_someone_elses_order(self):
        User.objects.create_user("o4", password="pw12345678")
        self.client.login(username="o4", password="pw12345678")
        self.assertEqual(self.post("submit").status_code, 404)
        self.assertEqual(self.client.get(self.url, {"order": self.order.pk}).status_code, 404)
        self.assertFalse(SupportTicket.objects.exists())
