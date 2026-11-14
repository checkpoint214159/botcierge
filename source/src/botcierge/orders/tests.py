import io
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import Address
from catalog.models import FleetUnit
from planner.decomposer import decompose
from planner.models import Recommendation, TaskRequest

from .models import Order, OrderStatusEvent
from .services import booking_window, free_units


def tiny_png():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, "PNG")
    return SimpleUploadedFile("plan.png", buf.getvalue(), content_type="image/png")


class BookingFixture(TestCase):
    """Seeded catalogue, the demo customer and one fresh plan, plus helpers to book it."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.user = User.objects.get(username="demo")
        cls.home = Address.objects.get(customer=cls.user)  # seeded, Jurong West (west zone)

    def setUp(self):
        self.client.login(username="demo", password="demopass123")
        self.rec = self.plan()
        self.tr = self.rec.task_request

    def plan(self, **kw):
        defaults = dict(customer=self.user, description="mop and vacuum my flat", area_m2=90, num_rooms=4,
                        floor_type="tile", budget_sgd=500, start_date=date.today() + timedelta(days=3),
                        deadline_date=date.today() + timedelta(days=5), hours_per_day=4)
        defaults.update(kw)
        return decompose(TaskRequest.objects.create(**defaults))

    def booking_data(self, **kw):
        data = {"robot": self.rec.robot_model_id, "addons": [a.pk for a in self.rec.addons.all()],
                "skill_pack": self.rec.skill_pack_id or "", "start_date": self.tr.start_date.isoformat(),
                "address": self.home.pk, "action": "save"}
        data.update(kw)
        return data

    def complete(self, tr=None):
        """Fill in the booking details through the real booking page."""
        tr = tr or self.tr
        resp = self.client.post(reverse("orders:booking", args=[tr.pk]),
                                {**self.booking_data(), "floor_plan": tiny_png()})
        self.assertRedirects(resp, reverse("orders:booking", args=[tr.pk]))
        self.rec = tr.recommendations.first()
        return resp

    def pay(self, promo="", tr=None):
        return self.client.post(reverse("orders:checkout", args=[(tr or self.tr).pk]), {
            "promo_code": promo, "card_name": "A Tester", "card_number": "4242 4242 4242 4242"})



class BookingTests(BookingFixture):
    """S08/S09/S10: booking page, cart and checkout."""

    # ---- cart

    def test_new_plan_is_in_cart_as_incomplete_with_badge(self):
        resp = self.client.get(reverse("orders:cart"))
        self.assertContains(resp, "Needs a few more details")
        self.assertContains(resp, "Choose a delivery address.")
        self.assertContains(resp, "Upload a floor plan")
        self.assertEqual(resp.context["cart_count"], 1)

    def test_completed_booking_moves_to_ready(self):
        self.complete()
        resp = self.client.get(reverse("orders:cart"))
        self.assertContains(resp, "Ready to check out")
        self.assertNotContains(resp, "Needs a few more details")

    def test_remove_and_restore(self):
        self.client.post(reverse("orders:cart_remove", args=[self.tr.pk]))
        self.tr.refresh_from_db()
        self.assertEqual(self.tr.status, TaskRequest.Status.DRAFT)
        self.assertEqual(self.client.get(reverse("orders:cart")).context["cart_count"], 0)
        self.client.post(reverse("orders:cart_restore", args=[self.tr.pk]))
        self.tr.refresh_from_db()
        self.assertEqual(self.tr.status, TaskRequest.Status.PLANNED)

    # ---- booking page (S08 + S09)

    def test_address_change_reprices_without_new_recommendation(self):
        self.complete()
        self.assertEqual(self.tr.recommendations.count(), 1)  # setup unchanged: still the ML row
        self.assertEqual(self.rec.source, Recommendation.Source.ML)
        self.assertEqual(self.rec.price_breakdown["delivery_zone"], "west")
        east = Address.objects.create(customer=self.user, label="Office", line="1 Tampines Ave", postal_code="520123")
        self.client.post(reverse("orders:booking", args=[self.tr.pk]), self.booking_data(address=east.pk))
        rec = self.tr.recommendations.first()
        self.assertEqual(self.tr.recommendations.count(), 1)
        self.assertEqual(rec.price_breakdown["delivery_zone"], "east")
        self.assertGreater(rec.quoted_price, self.rec.quoted_price)

    def test_robot_change_saves_customer_recommendation(self):
        from .forms import BookingForm
        other = BookingForm(task_request=self.tr).fields["robot"].queryset.exclude(pk=self.rec.robot_model_id).first()
        resp = self.client.post(reverse("orders:booking", args=[self.tr.pk]),
                                self.booking_data(robot=other.pk, addons=[], skill_pack=""))
        self.assertRedirects(resp, reverse("orders:booking", args=[self.tr.pk]))
        newest = self.tr.recommendations.first()
        self.assertEqual(newest.source, Recommendation.Source.CUSTOMER)
        self.assertEqual(newest.robot_model, other)
        self.assertEqual(self.tr.recommendations.count(), 2)  # the ML row is kept for A13

    def test_only_robots_and_packs_suited_to_the_task_are_offered(self):
        from catalog.taxonomy import TASK_PLATFORMS, TASK_SKILL_PACKS
        from .forms import BookingForm
        form = BookingForm(task_request=self.tr)
        category = self.tr.spec.task_category  # floor cleaning
        self.assertTrue(form.fields["robot"].queryset.exists())
        self.assertFalse(form.fields["robot"].queryset.exclude(platform__in=TASK_PLATFORMS[category]).exists())
        self.assertFalse(form.fields["robot"].queryset.filter(slug="aiper-scuba-n1-pro").exists())
        self.assertEqual({p.code for p in form.fields["skill_pack"].queryset}, set(TASK_SKILL_PACKS[category]))

    def test_pool_robot_cannot_be_posted_for_floor_cleaning(self):
        from catalog.models import RobotModel
        pool = RobotModel.objects.get(slug="aiper-scuba-n1-pro")
        resp = self.client.post(reverse("orders:booking", args=[self.tr.pk]), self.booking_data(robot=pool.pk))
        self.assertEqual(resp.status_code, 200)  # rejected by the form
        self.assertEqual(self.tr.recommendations.first().robot_model, self.rec.robot_model)

    def test_incompatible_skill_pack_is_rejected(self):
        from catalog.models import SkillPack
        wrong = SkillPack.objects.exclude(compatible_robots=self.rec.robot_model).first()
        resp = self.client.post(reverse("orders:booking", args=[self.tr.pk]), self.booking_data(skill_pack=wrong.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Select a valid choice")  # not offered for this task type at all
        self.assertEqual(self.tr.recommendations.count(), 1)

    def test_past_start_date_is_rejected(self):
        resp = self.client.post(reverse("orders:booking", args=[self.tr.pk]),
                                self.booking_data(start_date=(date.today() - timedelta(days=1)).isoformat()))
        self.assertContains(resp, "can&#x27;t be in the past")

    def test_quote_preview_is_json_and_saves_nothing(self):
        data = self.booking_data()
        del data["action"]
        resp = self.client.get(reverse("orders:booking_quote", args=[self.tr.pk]), data)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["delivery_priced"])
        self.assertGreater(body["units_free"], 0)
        self.tr.refresh_from_db()
        self.assertIsNone(self.tr.address)  # preview didn't save the address

    def test_other_customers_cannot_open_booking(self):
        other = User.objects.create_user("other", password="pw12345678")
        theirs = self.plan(customer=other).task_request
        self.assertEqual(self.client.get(reverse("orders:booking", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("orders:booking_quote", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("orders:checkout", args=[theirs.pk])).status_code, 404)

    def test_cannot_use_someone_elses_address(self):
        other = User.objects.create_user("other", password="pw12345678")
        theirs = Address.objects.create(customer=other, label="Theirs", line="x", postal_code="640123")
        resp = self.client.post(reverse("orders:booking", args=[self.tr.pk]), self.booking_data(address=theirs.pk))
        self.assertEqual(resp.status_code, 200)  # form error, not saved
        self.tr.refresh_from_db()
        self.assertIsNone(self.tr.address)

    # ---- checkout (S10)

    def test_incomplete_booking_cannot_check_out(self):
        self.assertRedirects(self.client.get(reverse("orders:checkout", args=[self.tr.pk])),
                             reverse("orders:booking", args=[self.tr.pk]))

    def test_checkout_creates_order_payment_event_and_reserves_unit(self):
        self.complete()
        resp = self.pay()
        order = Order.objects.get()
        self.assertRedirects(resp, reverse("orders:confirmation", args=[order.pk]))
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertEqual(order.total, self.rec.quoted_price)
        self.assertEqual(order.delivery_address, self.home.one_line())
        self.assertEqual(order.payment.status, "paid")
        self.assertEqual(OrderStatusEvent.objects.filter(order=order).count(), 1)
        unit = order.items.get(kind="robot").fleet_unit
        self.assertEqual(unit.status, FleetUnit.Status.RESERVED)
        self.rec.refresh_from_db()
        self.assertTrue(self.rec.is_selected)
        self.assertEqual(self.rec.task_request.status, TaskRequest.Status.BOOKED)
        self.assertEqual(sum(i.line_total for i in order.items.all()), order.subtotal)

    def test_order_keeps_address_text_after_address_is_deleted(self):
        self.complete()
        self.pay()
        order = Order.objects.get()
        self.home.delete()
        order.refresh_from_db()
        self.assertIn("Jurong West", order.delivery_address)

    def test_booked_plan_cannot_be_booked_again(self):
        self.complete()
        self.pay()
        order = Order.objects.get()
        self.assertRedirects(self.client.get(reverse("orders:booking", args=[self.tr.pk])),
                             reverse("orders:order_detail", args=[order.pk]))
        self.pay()
        self.assertEqual(Order.objects.count(), 1)
        self.assertNotContains(self.client.get(reverse("orders:cart")), self.tr.description)

    def test_promo_preview_then_pay(self):
        self.complete()
        page = self.client.get(reverse("orders:checkout", args=[self.tr.pk]), {"promo": "welcome10"})
        self.assertContains(page, "WELCOME10 applied")
        self.pay("WELCOME10")
        order = Order.objects.get()
        self.assertEqual(order.discount, (self.rec.quoted_price * Decimal("0.10")).quantize(Decimal("0.01")))
        self.assertEqual(order.total, order.subtotal - order.discount)

    def test_bad_promo_blocks_order(self):
        self.complete()
        page = self.client.get(reverse("orders:checkout", args=[self.tr.pk]), {"promo": "NOPE"})
        self.assertContains(page, "not valid")
        self.pay("NOPE")
        self.assertEqual(Order.objects.count(), 0)

    def test_sold_out_dates_block_checkout(self):
        robot = self.rec.robot_model
        for _ in range(robot.units.exclude(status__in=["maintenance", "retired"]).count()):
            self.complete()
            self.pay()
            self.rec = self.plan()
            self.tr = self.rec.task_request
        self.assertEqual(free_units(robot, *booking_window(self.rec)).count(), 0)
        self.complete()
        self.assertContains(self.client.get(reverse("orders:cart")), "is free from")
        self.assertRedirects(self.client.get(reverse("orders:checkout", args=[self.tr.pk])),
                             reverse("orders:booking", args=[self.tr.pk]))


class HistoryAndZonesTests(BookingFixture):
    """S12 order history + rebook, and the floor plan keep-out zones."""

    def book(self):
        self.complete()
        self.pay()
        return Order.objects.latest("pk")

    def test_order_list_splits_ongoing_and_finished(self):
        order = self.book()
        resp = self.client.get(reverse("orders:order_list"))
        self.assertEqual(resp.context["ongoing"], [order])
        Order.objects.filter(pk=order.pk).update(status=Order.Status.COLLECTED)
        resp = self.client.get(reverse("orders:order_list"))
        self.assertEqual(resp.context["past"], [Order.objects.get(pk=order.pk)])
        self.assertContains(resp, "Book again")

    def test_rebook_copies_plan_into_cart_with_new_dates(self):
        order = self.book()
        resp = self.client.post(reverse("orders:order_rebook", args=[order.pk]))
        new = TaskRequest.objects.filter(customer=self.user).latest("pk")
        self.assertRedirects(resp, reverse("orders:booking", args=[new.pk]))
        self.assertNotEqual(new.pk, self.tr.pk)
        self.assertEqual(new.status, TaskRequest.Status.PLANNED)
        self.assertGreater(new.start_date, date.today())
        self.assertEqual(new.recommendations.first().robot_model, self.rec.robot_model)
        self.assertEqual(new.spec.task_category, self.tr.spec.task_category)

    def test_cannot_rebook_someone_elses_order(self):
        order = self.book()
        User.objects.create_user("o3", password="pw12345678")
        self.client.login(username="o3", password="pw12345678")
        self.assertEqual(self.client.post(reverse("orders:order_rebook", args=[order.pk])).status_code, 404)

    def test_keep_out_zones_saved_and_sent_to_robot_config(self):
        import json
        zones = [{"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.25}]
        self.client.post(reverse("orders:booking", args=[self.tr.pk]),
                         {**self.booking_data(), "floor_plan": tiny_png(), "keep_out_zones": json.dumps(zones)})
        self.tr.refresh_from_db()
        self.assertEqual(self.tr.keep_out_zones, zones)
        self.assertEqual(self.tr.recommendations.first().policy_conditioning["map"]["keep_out_zones"], zones)

    def test_bad_keep_out_zones_are_rejected(self):
        import json
        for bad in ["not json", json.dumps([{"x": 0.9, "y": 0.1, "w": 0.5, "h": 0.1}]), json.dumps([{"x": 1}])]:
            resp = self.client.post(reverse("orders:booking", args=[self.tr.pk]), self.booking_data(keep_out_zones=bad))
            self.assertEqual(resp.status_code, 200, bad)  # re-rendered with an error, not saved
        self.tr.refresh_from_db()
        self.assertEqual(self.tr.keep_out_zones, [])


class TrackingTests(BookingFixture):
    """S11 / A07: staff advance an order, the customer sees the timeline."""

    def book(self):
        self.complete()
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
        # A08: can't dispatch before the review is approved
        staff.post(url, {"action": "advance", "note": "On the way"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        staff.post(reverse("staffpanel:review_detail", args=[order.pk]), {"action": "approve"})
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


class ChangeOfPlansTests(BookingFixture):
    """S18: cancel or reschedule until the day before the start date, before dispatch."""

    def setUp(self):
        super().setUp()
        self.complete()
        self.pay()
        self.order = Order.objects.latest("pk")
        self.unit = self.order.items.get(kind="robot").fleet_unit

    def test_cancel_refunds_frees_unit_and_logs_event(self):
        resp = self.client.post(reverse("orders:order_cancel", args=[self.order.pk]))
        self.assertRedirects(resp, reverse("orders:order_detail", args=[self.order.pk]))
        self.order.refresh_from_db()
        self.unit.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.order.payment.status, "refunded")
        self.assertEqual(self.unit.status, FleetUnit.Status.AVAILABLE)
        self.assertTrue(self.order.events.filter(status=Order.Status.CANCELLED).exists())
        self.assertIn(self.unit, free_units(self.unit.robot_model, self.order.start_date, self.order.end_date))
        # a cancelled order is finished, and can't be changed again
        self.assertNotContains(self.client.get(reverse("orders:order_detail", args=[self.order.pk])), "Change of plans?")

    def test_cancel_needs_post(self):
        self.assertEqual(self.client.get(reverse("orders:order_cancel", args=[self.order.pk])).status_code, 405)

    def test_no_changes_after_dispatch_or_on_start_day(self):
        for change in ({"status": Order.Status.DISPATCHED}, {"start_date": date.today()}):
            reset = {"status": Order.Status.CONFIRMED, "start_date": self.tr.start_date, **change}
            Order.objects.filter(pk=self.order.pk).update(**reset)
            self.client.post(reverse("orders:order_cancel", args=[self.order.pk]))
            self.assertNotEqual(Order.objects.get(pk=self.order.pk).status, Order.Status.CANCELLED)

    def test_reschedule_keeps_length_and_price_and_moves_plan(self):
        new_start = self.order.start_date + timedelta(days=7)
        length = self.order.end_date - self.order.start_date
        total = self.order.total
        resp = self.client.post(reverse("orders:order_reschedule", args=[self.order.pk]),
                                {"start_date": new_start.isoformat()})
        self.assertRedirects(resp, reverse("orders:order_detail", args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.start_date, new_start)
        self.assertEqual(self.order.end_date - self.order.start_date, length)
        self.assertEqual(self.order.total, total)
        self.assertTrue(self.order.events.filter(note__startswith="Moved from").exists())
        self.tr.refresh_from_db()
        self.assertEqual(self.tr.start_date, new_start)
        self.assertEqual(self.order.recommendation.policy_conditioning["constraints"]["window"][0], new_start.isoformat())

    def test_reschedule_to_overlapping_dates_keeps_same_unit(self):
        # moving by one day overlaps the order's own booking, which must not count as a clash
        new_start = self.order.start_date + timedelta(days=1)
        self.client.post(reverse("orders:order_reschedule", args=[self.order.pk]), {"start_date": new_start.isoformat()})
        self.order.refresh_from_db()
        self.assertEqual(self.order.start_date, new_start)
        self.assertEqual(self.order.items.get(kind="robot").fleet_unit, self.unit)

    def test_reschedule_rejects_today_and_sold_out_dates(self):
        resp = self.client.post(reverse("orders:order_reschedule", args=[self.order.pk]),
                                {"start_date": date.today().isoformat()})
        self.assertContains(resp, "Pick a date from tomorrow onwards.")
        FleetUnit.objects.filter(robot_model=self.unit.robot_model).update(status=FleetUnit.Status.MAINTENANCE)
        resp = self.client.post(reverse("orders:order_reschedule", args=[self.order.pk]),
                                {"start_date": (self.order.start_date + timedelta(days=10)).isoformat()})
        self.assertContains(resp, "No unit of this robot is free")
        self.assertEqual(Order.objects.get(pk=self.order.pk).start_date, self.order.start_date)

    def test_cannot_change_someone_elses_order(self):
        User.objects.create_user("o4", password="pw12345678")
        self.client.login(username="o4", password="pw12345678")
        self.assertEqual(self.client.post(reverse("orders:order_cancel", args=[self.order.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("orders:order_reschedule", args=[self.order.pk]),
                                          {"start_date": "2099-01-01"}).status_code, 404)
