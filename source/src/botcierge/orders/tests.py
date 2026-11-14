from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from catalog.models import FleetUnit
from planner.decomposer import decompose
from planner.models import TaskRequest

from .models import Order, OrderStatusEvent
from .services import booking_window, free_units


class BookingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.user = User.objects.get(username="demo")

    def setUp(self):
        self.client.login(username="demo", password="demopass123")
        self.rec = self.plan()

    def plan(self, **kw):
        defaults = dict(customer=self.user, description="mop and vacuum my flat", area_m2=90, num_rooms=4,
                        floor_type="tile", budget_sgd=500, start_date=date.today() + timedelta(days=3),
                        deadline_date=date.today() + timedelta(days=5), hours_per_day=4)
        defaults.update(kw)
        return decompose(TaskRequest.objects.create(**defaults))

    def add_to_cart(self, rec=None):
        return self.client.post(reverse("orders:cart_add", args=[(rec or self.rec).pk]))

    def pay(self, promo=""):
        return self.client.post(reverse("orders:checkout"), {
            "delivery_address": "1 Test Rd", "promo_code": promo,
            "card_name": "A Tester", "card_number": "4242 4242 4242 4242"})

    def test_cart_shows_availability(self):
        self.add_to_cart()
        resp = self.client.get(reverse("orders:cart"))
        self.assertContains(resp, "free on your dates")
        self.assertContains(resp, "Checkout")

    def test_checkout_creates_order_payment_event_and_reserves_unit(self):
        self.add_to_cart()
        resp = self.pay()
        order = Order.objects.get()
        self.assertRedirects(resp, reverse("orders:confirmation", args=[order.pk]))
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertEqual(order.total, self.rec.quoted_price)
        self.assertEqual(order.payment.status, "paid")
        self.assertEqual(OrderStatusEvent.objects.filter(order=order).count(), 1)
        unit = order.items.get(kind="robot").fleet_unit
        self.assertEqual(unit.status, FleetUnit.Status.RESERVED)
        self.rec.refresh_from_db()
        self.assertTrue(self.rec.is_selected)
        self.assertEqual(self.rec.task_request.status, TaskRequest.Status.BOOKED)
        item_sum = sum(i.line_total for i in order.items.all())
        self.assertEqual(item_sum, order.subtotal)

    def test_promo_code_discounts_total(self):
        self.add_to_cart()
        self.pay("welcome10")
        order = Order.objects.get()
        self.assertEqual(order.discount, (self.rec.quoted_price * Decimal("0.10")).quantize(Decimal("0.01")))
        self.assertEqual(order.total, order.subtotal - order.discount)

    def test_bad_promo_blocks_order(self):
        self.add_to_cart()
        resp = self.pay("NOPE")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "not valid")
        self.assertEqual(Order.objects.count(), 0)

    def test_sold_out_dates_block_checkout(self):
        robot = self.rec.robot_model
        for _ in range(robot.units.exclude(status__in=["maintenance", "retired"]).count()):
            self.add_to_cart()
            self.pay()
            self.rec = self.plan()
        self.assertEqual(free_units(robot, *booking_window(self.rec)).count(), 0)
        self.add_to_cart()
        resp = self.client.get(reverse("orders:cart"))
        self.assertContains(resp, "is free from")
        self.assertRedirects(self.client.get(reverse("orders:checkout")), reverse("orders:cart"))

    def test_cannot_add_other_customers_plan(self):
        other = User.objects.create_user("other", password="pw12345678")
        rec = self.plan(customer=other)
        self.assertEqual(self.add_to_cart(rec).status_code, 404)

    def test_empty_cart_checkout_redirects(self):
        self.assertEqual(self.client.get(reverse("orders:checkout")).status_code, 302)


class TrackingTests(BookingTests):
    """S11 / A07: staff advance an order, the customer sees the timeline."""

    def book(self):
        self.add_to_cart()
        self.pay()
        return Order.objects.get()

    def staff_client(self):
        from django.test import Client
        c = Client()
        c.login(username="staff", password="staffpass123")
        return c

    def test_customer_sees_timeline_and_not_others(self):
        order = self.book()
        resp = self.client.get(reverse("orders:order_detail", args=[order.pk]))
        self.assertContains(resp, "Tracking")
        User.objects.create_user("o2", password="pw12345678")
        self.client.login(username="o2", password="pw12345678")
        self.assertEqual(self.client.get(reverse("orders:order_detail", args=[order.pk])).status_code, 404)

    def test_staff_advance_updates_status_unit_and_timeline(self):
        order = self.book()
        staff = self.staff_client()
        url = reverse("staffpanel:order_detail", args=[order.pk])
        staff.post(url, {"action": "advance", "note": "On the way"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DISPATCHED)
        unit = order.items.get(kind="robot").fleet_unit
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.Status.DEPLOYED)
        self.assertTrue(order.events.filter(status="dispatched", note="On the way").exists())
        for _ in range(4):
            staff.post(url, {"action": "advance"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COLLECTED)
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.Status.AVAILABLE)

    def test_staff_can_reassign_free_unit(self):
        order = self.book()
        item = order.items.get(kind="robot")
        other = free_units(item.robot_model, order.start_date, order.end_date).first()
        self.staff_client().post(reverse("staffpanel:order_detail", args=[order.pk]),
                                 {"action": "assign", "unit": other.pk})
        item.refresh_from_db()
        self.assertEqual(item.fleet_unit, other)

    def test_customers_cannot_use_staff_pages(self):
        order = self.book()
        resp = self.client.get(reverse("staffpanel:order_detail", args=[order.pk]))
        self.assertEqual(resp.status_code, 302)
