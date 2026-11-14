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

from .models import Review, SupportTicket


class SupportFixture(TestCase):
    """Seeded catalogue, the demo customer logged in and one paid order."""

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


class SupportTests(SupportFixture):
    """S14: one ticket per order, drafts editable, submitted tickets read-only."""

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


class ReviewTests(SupportFixture):
    """S13: one review per finished order, from the order's owner."""

    def url_for(self, order=None):
        return reverse("support:review_new", args=[(order or self.order).pk])

    def finish(self):
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.COMPLETED)

    def test_cannot_review_before_the_job_is_done(self):
        resp = self.client.post(self.url_for(), {"rating": 5})
        self.assertRedirects(resp, reverse("orders:order_detail", args=[self.order.pk]))
        self.assertFalse(Review.objects.exists())

    def test_review_is_saved_once_and_shown_on_robot_page(self):
        self.finish()
        self.assertContains(self.client.get(reverse("orders:order_detail", args=[self.order.pk])), "Rate this job")
        self.client.post(self.url_for(), {"rating": 4, "comment": "Quiet and thorough."})
        review = Review.objects.get()
        robot = self.order.items.get(kind="robot").robot_model
        self.assertEqual((review.customer, review.robot_model, review.rating), (self.user, robot, 4))
        self.assertEqual(review.skill_pack, self.order.recommendation.skill_pack)
        # a second try is turned away, and the order page shows the review instead of the button
        self.client.post(self.url_for(), {"rating": 1})
        self.assertEqual(Review.objects.count(), 1)
        page = self.client.get(reverse("orders:order_detail", args=[self.order.pk]))
        self.assertContains(page, "Your review")
        self.assertNotContains(page, "Rate this job")
        self.assertContains(self.client.get(reverse("catalog:robot_detail", args=[robot.slug])), "Quiet and thorough.")

    def test_rating_must_be_1_to_5(self):
        self.finish()
        resp = self.client.post(self.url_for(), {"rating": 9})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Review.objects.exists())

    def test_cannot_review_someone_elses_order(self):
        self.finish()
        User.objects.create_user("o5", password="pw12345678")
        self.client.login(username="o5", password="pw12345678")
        self.assertEqual(self.client.post(self.url_for(), {"rating": 5}).status_code, 404)
