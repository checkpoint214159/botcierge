from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Address
from catalog.checks import catalogue_issues
from catalog.models import AddOn, FleetUnit, RobotModel, SkillPack
from orders.services import create_order
from planner.decomposer import decompose
from planner.ml_registry import coverage
from planner.models import TaskRequest


class StaffFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def setUp(self):
        self.client.login(username="staff", password="staffpass123")


class AccessTests(StaffFixture):
    PAGES = ["robot_list", "robot_new", "fleet_list", "fleet_new", "addon_list", "addon_new",
             "skillpack_list", "skillpack_new", "ml_models"]

    def test_staff_can_open_every_catalogue_page(self):
        for name in self.PAGES:
            self.assertEqual(self.client.get(reverse(f"staffpanel:{name}")).status_code, 200, name)

    def test_customers_are_sent_to_login(self):
        self.client.login(username="demo", password="demopass123")
        for name in self.PAGES:
            resp = self.client.get(reverse(f"staffpanel:{name}"))
            self.assertEqual(resp.status_code, 302, name)
            self.assertIn(reverse("accounts:login"), resp["Location"])

    def test_staff_nav_has_no_customer_menus(self):
        resp = self.client.get(reverse("staffpanel:robot_list"))
        self.assertContains(resp, "Catalogue")
        self.assertNotContains(resp, "Plan a new task")
        self.assertNotContains(resp, "My orders")


class RobotTests(StaffFixture):
    """A03."""

    def data(self, **kw):
        d = {"name": "Test Bot", "slug": "", "manufacturer": "Acme", "platform": "wheeled_amr",
             "daily_rate": "40.00", "indoor": "on", "max_payload_kg": "0", "battery_hours": "3",
             "noise_db": "50", "is_active": "on", "categories": ["floor_cleaning"]}
        d.update(kw)
        return d

    def test_add_robot_makes_slug(self):
        resp = self.client.post(reverse("staffpanel:robot_new"), self.data())
        self.assertRedirects(resp, reverse("staffpanel:robot_list"))
        self.assertEqual(RobotModel.objects.get(name="Test Bot").slug, "test-bot")

    def test_robot_must_work_somewhere(self):
        data = self.data()
        del data["indoor"]
        resp = self.client.post(reverse("staffpanel:robot_new"), data)
        self.assertContains(resp, "indoors, outdoors or both")

    def test_unlisting_hides_robot_from_shop_and_flags_new_robot_without_units(self):
        robot = RobotModel.objects.filter(is_active=True).first()
        self.client.post(reverse("staffpanel:robot_toggle", args=[robot.pk]))
        robot.refresh_from_db()
        self.assertFalse(robot.is_active)
        self.assertEqual(self.client.get(reverse("catalog:robot_detail", args=[robot.slug])).status_code, 404)
        # a new listed robot with no units shows up as a problem
        self.client.post(reverse("staffpanel:robot_new"), self.data())
        self.assertTrue(any("Test Bot" in i["text"] for i in catalogue_issues("fleet")))

    def test_listed_robot_needs_a_task_type(self):
        data = self.data()
        del data["categories"]
        self.assertContains(self.client.post(reverse("staffpanel:robot_new"), data), "Pick at least one task type")

    def test_adding_task_type_to_robot_clears_skill_pack_warning_and_makes_it_bookable(self):
        g1 = RobotModel.objects.get(name="G1")
        warning = lambda: [i for i in catalogue_issues("skill_packs") if "G1" in i["text"]]
        self.assertTrue(warning())
        user = User.objects.get(username="demo")
        tr = TaskRequest.objects.create(
            customer=user, description="serve drinks and canapes at my house party", area_m2=120, num_rooms=4,
            floor_type="tile", budget_sgd=2000, start_date=date.today() + timedelta(days=3),
            deadline_date=date.today() + timedelta(days=3), hours_per_day=4, category_hint="event_serving")
        decompose(tr)
        from planner.decomposer import eligible_robots
        self.assertNotIn(g1, eligible_robots(tr))
        resp = self.client.post(reverse("staffpanel:robot_edit", args=[g1.pk]), self.data(
            name=g1.name, slug=g1.slug, platform=g1.platform, categories=g1.category_list + ["event_serving"]))
        self.assertRedirects(resp, reverse("staffpanel:robot_list"))
        self.assertFalse(warning())
        self.assertIn(g1, eligible_robots(tr))

    def test_edit_page_shows_issues_with_this_item_first(self):
        pack = SkillPack.objects.get(name="Serve & Navigate")
        resp = self.client.get(reverse("staffpanel:skillpack_edit", args=[pack.pk]))
        self.assertContains(resp, "This item: Serve &amp; Navigate lists G1")

    def test_toggle_needs_post(self):
        robot = RobotModel.objects.first()
        self.assertEqual(self.client.get(reverse("staffpanel:robot_toggle", args=[robot.pk])).status_code, 405)


class FleetTests(StaffFixture):
    """A04."""

    def test_add_unit_and_service_date_not_in_future(self):
        robot = RobotModel.objects.filter(is_active=True).first()
        data = {"robot_model": robot.pk, "serial_number": "NEW-001", "status": "available", "depot": "Jurong West"}
        resp = self.client.post(reverse("staffpanel:fleet_new"),
                                {**data, "last_serviced": (date.today() + timedelta(days=1)).isoformat()})
        self.assertContains(resp, "can&#x27;t be in the future")
        self.client.post(reverse("staffpanel:fleet_new"), data)
        self.assertTrue(FleetUnit.objects.filter(serial_number="NEW-001", robot_model=robot).exists())

    def test_booked_unit_cannot_go_to_maintenance(self):
        user = User.objects.get(username="demo")
        tr = TaskRequest.objects.create(
            customer=user, description="mop and vacuum my flat", area_m2=90, num_rooms=4, floor_type="tile",
            budget_sgd=500, start_date=date.today() + timedelta(days=3), deadline_date=date.today() + timedelta(days=5),
            hours_per_day=4, address=Address.objects.get(customer=user))
        order = create_order(user, decompose(tr), "1 Test Rd", None)
        unit = order.items.get(kind="robot").fleet_unit
        unit.status = FleetUnit.Status.AVAILABLE  # pretend it's free-looking so the status field is editable
        unit.save()
        resp = self.client.post(reverse("staffpanel:fleet_edit", args=[unit.pk]), {
            "serial_number": unit.serial_number, "status": "maintenance", "depot": unit.depot})
        self.assertContains(resp, f"booked for order #{order.pk}")
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.Status.AVAILABLE)

    def test_reserved_status_is_not_editable_by_hand(self):
        unit = FleetUnit.objects.first()
        unit.status = FleetUnit.Status.RESERVED
        unit.save()
        self.client.post(reverse("staffpanel:fleet_edit", args=[unit.pk]), {
            "serial_number": unit.serial_number, "status": "available", "depot": unit.depot})
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.Status.RESERVED)


class AddOnAndSkillPackTests(StaffFixture):
    """A05 and the recommendation models page."""

    def test_new_addon_is_offered_but_not_learned(self):
        resp = self.client.post(reverse("staffpanel:addon_new"), {
            "code": "uv_lamp", "name": "UV lamp", "daily_rate": "6.00", "platforms": ["wheeled_amr"],
            "is_active": "on"})
        self.assertRedirects(resp, reverse("staffpanel:addon_list"))
        addon = AddOn.objects.get(code="uv_lamp")
        self.assertEqual(addon.compatible_platforms, "wheeled_amr")
        rows = {r["code"]: r["state"] for s in coverage() if s["model"] == "M3" for r in s["rows"]}
        self.assertEqual(rows["uv_lamp"], "not_learned")
        self.assertEqual(rows["mop_module"], "live")

    def test_bad_code_is_rejected_and_code_is_locked_on_edit(self):
        resp = self.client.post(reverse("staffpanel:addon_new"), {"code": "UV Lamp", "name": "x", "daily_rate": "1"})
        self.assertContains(resp, "Lower-case letters")
        addon = AddOn.objects.get(code="mop_module")
        self.client.post(reverse("staffpanel:addon_edit", args=[addon.pk]), {
            "code": "hacked", "name": "Mop module", "daily_rate": "9.00", "is_active": "on"})
        addon.refresh_from_db()
        self.assertEqual((addon.code, str(addon.daily_rate)), ("mop_module", "9.00"))

    def test_hiding_a_learned_addon_shows_switched_off(self):
        addon = AddOn.objects.get(code="mop_module")
        self.client.post(reverse("staffpanel:addon_toggle", args=[addon.pk]))
        rows = {r["code"]: r["state"] for s in coverage() if s["model"] == "M3" for r in s["rows"]}
        self.assertEqual(rows["mop_module"], "switched_off")

    def test_skill_pack_json_and_task_types(self):
        robot = RobotModel.objects.filter(platform="wheeled_amr", is_active=True).first()
        base = {"code": "quick_tidy", "name": "Quick Tidy", "version": "1.0", "flat_fee": "10",
                "compatible_robots": [robot.pk], "is_active": "on"}
        resp = self.client.post(reverse("staffpanel:skillpack_new"), {**base, "conditioning": "{oops"})
        self.assertContains(resp, "isn&#x27;t valid JSON")
        resp = self.client.post(reverse("staffpanel:skillpack_new"), {**base, "conditioning": "{}"})
        self.assertContains(resp, "Pick at least one task type")
        self.client.post(reverse("staffpanel:skillpack_new"),
                         {**base, "conditioning": '{"passes": 2}', "categories": ["floor_cleaning"]})
        pack = SkillPack.objects.get(code="quick_tidy")
        self.assertEqual((pack.task_categories, pack.default_conditioning), ("floor_cleaning", {"passes": 2}))

    def test_new_skill_pack_is_offered_on_booking_page_for_its_task_type(self):
        from orders.forms import BookingForm
        user = User.objects.get(username="demo")
        tr = TaskRequest.objects.create(
            customer=user, description="mop and vacuum my flat", area_m2=90, num_rooms=4, floor_type="tile",
            budget_sgd=500, start_date=date.today() + timedelta(days=3), deadline_date=date.today() + timedelta(days=5),
            hours_per_day=4)
        decompose(tr)
        pack = SkillPack.objects.create(code="quick_tidy", name="Quick Tidy", task_categories="floor_cleaning")
        self.assertIn(pack, BookingForm(task_request=tr).fields["skill_pack"].queryset)
        pack.task_categories = "lawn_care"
        pack.save()
        self.assertNotIn(pack, BookingForm(task_request=tr).fields["skill_pack"].queryset)

    def test_seeded_catalogue_is_in_sync(self):
        self.assertEqual([i["text"] for i in catalogue_issues() if i["level"] == "danger"], [])

    def test_models_page_shows_metrics_and_coverage(self):
        resp = self.client.get(reverse("staffpanel:ml_models"))
        self.assertContains(resp, "M1 · Task type")
        self.assertContains(resp, "RandomForestClassifier")
        self.assertContains(resp, "Coverage")


class ReviewTests(StaffFixture):
    """A08: review every paid order before dispatch; approve, follow up or change the setup."""

    def book(self, offset=3, budget=500, description="mop and vacuum my flat", **kw):
        user = User.objects.get(username="demo")
        start = date.today() + timedelta(days=offset)
        tr = TaskRequest.objects.create(
            customer=user, description=description, area_m2=90, num_rooms=4, floor_type="tile",
            budget_sgd=budget, start_date=start, deadline_date=start + timedelta(days=1), hours_per_day=4,
            address=Address.objects.get(customer=user), **kw)
        return create_order(user, decompose(tr), "1 Test Rd", None)

    def test_queue_groups_by_ship_day_then_biggest_first(self):
        from orders.review import grouped, review_queue
        later = self.book(offset=5)
        small = self.book(offset=2, budget=300)
        big = self.book(offset=2, budget=3000, description="keep my grandmother company", category_hint="elder_care",
                        payload_kg=1)
        if big.total < small.total:  # make sure the test means what it says
            small, big = big, small
        queue = review_queue()
        self.assertEqual([o.pk for o in queue], [big.pk, small.pk, later.pk])
        self.assertEqual([len(os) for _, os in grouped(queue)], [2, 1])
        resp = self.client.get(reverse("staffpanel:review_list"))
        self.assertContains(resp, "Start reviewing")
        self.assertContains(resp, f"Order #{big.pk}")

    def test_approve_tells_customer_and_moves_to_next(self):
        first, second = self.book(offset=2), self.book(offset=4)
        resp = self.client.post(reverse("staffpanel:review_detail", args=[first.pk]), {"action": "approve"})
        self.assertRedirects(resp, reverse("staffpanel:review_detail", args=[second.pk]))
        first.refresh_from_db()
        self.assertEqual(first.review_status, "approved")
        self.assertTrue(first.events.filter(note__contains="checked by our team").exists())
        # last one goes back to the list
        resp = self.client.post(reverse("staffpanel:review_detail", args=[second.pk]), {"action": "approve"})
        self.assertRedirects(resp, reverse("staffpanel:review_list"))

    def test_follow_up_needs_a_note_and_stays_internal(self):
        order = self.book()
        url = reverse("staffpanel:review_detail", args=[order.pk])
        self.client.post(url, {"action": "reject"})
        order.refresh_from_db()
        self.assertEqual(order.review_status, "pending")
        self.client.post(url, {"action": "reject", "note": "Ask about the stairs"})
        order.refresh_from_db()
        self.assertEqual((order.review_status, order.review_note), ("rejected", "Ask about the stairs"))
        self.assertEqual(order.events.count(), 1)  # nothing new on the customer's timeline

    def test_override_saves_staff_recommendation_and_keeps_what_customer_paid(self):
        from planner.models import Recommendation
        order = self.book()
        paid = order.total
        tr = order.recommendation.task_request
        from planner.decomposer import eligible_robots
        other = eligible_robots(tr).exclude(pk=order.recommendation.robot_model_id).first()
        resp = self.client.post(reverse("staffpanel:review_detail", args=[order.pk]), {
            "action": "override", "robot": other.pk, "addons": [], "skill_pack": ""})
        self.assertRedirects(resp, reverse("staffpanel:review_detail", args=[order.pk]))
        order.refresh_from_db()
        rec = order.recommendation
        self.assertEqual((rec.source, rec.robot_model, rec.is_selected), (Recommendation.Source.STAFF, other, True))
        self.assertEqual(order.items.get(kind="robot").robot_model, other)
        self.assertEqual(order.items.get(kind="robot").fleet_unit.robot_model, other)
        self.assertEqual(order.total, paid)
        self.assertEqual(sum(i.line_total for i in order.items.all()), order.subtotal)
        self.assertTrue(order.events.filter(note__contains="adjusted your setup").exists())
        self.assertEqual(tr.recommendations.filter(source="ml").count(), 1)  # ML row kept for A13

    def test_override_rejects_incompatible_attachment(self):
        order = self.book()
        robot = order.recommendation.robot_model
        bad = next(a for a in AddOn.objects.filter(is_active=True) if not a.fits(robot.platform))
        resp = self.client.post(reverse("staffpanel:review_detail", args=[order.pk]), {
            "action": "override", "robot": robot.pk, "addons": [bad.pk], "skill_pack": ""})
        self.assertContains(resp, "Not compatible with")

    def test_customers_cannot_open_review(self):
        order = self.book()
        self.client.login(username="demo", password="demopass123")
        self.assertEqual(self.client.get(reverse("staffpanel:review_detail", args=[order.pk])).status_code, 302)
