from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .decomposer import decompose
from .models import TaskRequest


class PlannerFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.user = User.objects.get(username="demo")

    def make_request(self, **kw):
        defaults = dict(customer=self.user, description="mop and vacuum my flat, we have a cat",
                        area_m2=90, num_rooms=4, floor_type="tile", budget_sgd=300,
                        start_date=date.today(), deadline_date=date.today() + timedelta(days=2),
                        hours_per_day=4)
        defaults.update(kw)
        return TaskRequest.objects.create(**defaults)


class DecomposerTests(PlannerFixtureMixin, TestCase):

    def test_floor_cleaning_gets_wheeled_base_and_cleaning_pack(self):
        rec = decompose(self.make_request(has_pets=True))
        self.assertEqual(rec.task_request.spec.task_category, "floor_cleaning")
        self.assertEqual(rec.robot_model.platform, "wheeled_amr")
        self.assertIn(rec.skill_pack.code, {"coverage_clean", "spot_clean"})
        self.assertGreater(rec.quoted_price, 0)

    def test_category_hint_overrides_text_model(self):
        rec = decompose(self.make_request(category_hint="lawn_care", floor_type="grass", is_outdoor=True))
        self.assertEqual(rec.task_request.spec.task_category, "lawn_care")
        self.assertEqual(rec.task_request.spec.category_confidence, 1.0)

    def test_tight_budget_is_flagged(self):
        rec = decompose(self.make_request(budget_sgd=10))
        self.assertFalse(rec.task_request.spec.within_budget)

    def test_outdoor_job_never_gets_indoor_only_robot(self):
        rec = decompose(self.make_request(description="patrol the compound at night", is_outdoor=True,
                                          floor_type="concrete", housing_type="landed"))
        self.assertTrue(rec.robot_model.outdoor)


class PlannerViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_full_intake_flow(self):
        self.client.login(username="demo", password="demopass123")
        resp = self.client.post(reverse("planner:start"), {
            "description": "please clean the windows on the 20th floor",
            "housing_type": "condo", "area_m2": 40, "num_rooms": 1, "floor_type": "glass",
            "payload_kg": 0, "budget_sgd": 200, "start_date": date.today(),
            "deadline_date": date.today() + timedelta(days=1), "hours_per_day": 4,
        })
        tr = TaskRequest.objects.get()
        self.assertRedirects(resp, reverse("planner:result", args=[tr.pk]))
        page = self.client.get(reverse("planner:result", args=[tr.pk]))
        self.assertContains(page, "Clearview W1")

    def test_planner_requires_login(self):
        resp = self.client.get(reverse("planner:start"))
        self.assertEqual(resp.status_code, 302)

    def test_staff_panel_blocks_customers(self):
        self.client.login(username="demo", password="demopass123")
        self.assertEqual(self.client.get(reverse("staffpanel:dashboard")).status_code, 302)


class SwapTests(PlannerFixtureMixin, TestCase):
    """S08 / S17: customer swaps are saved as new CUSTOMER recommendations."""

    def test_swap_saves_customer_rec_and_requotes(self):
        from .models import Recommendation
        ml_rec = decompose(self.make_request())
        from .forms import SwapForm
        allowed = SwapForm(task_request=ml_rec.task_request).fields["robot"].queryset
        other = allowed.exclude(pk=ml_rec.robot_model_id).first()
        self.assertIsNotNone(other)
        self.client.login(username="demo", password="demopass123")
        url = reverse("planner:swap", args=[ml_rec.task_request.pk])
        resp = self.client.post(url, {"robot": other.pk})
        self.assertRedirects(resp, reverse("planner:result", args=[ml_rec.task_request.pk]))
        newest = ml_rec.task_request.recommendations.first()
        self.assertEqual(newest.source, Recommendation.Source.CUSTOMER)
        self.assertEqual(newest.robot_model, other)
        self.assertEqual(ml_rec.task_request.recommendations.count(), 2)

    def test_result_page_shows_reasons(self):
        rec = decompose(self.make_request())
        self.client.login(username="demo", password="demopass123")
        resp = self.client.get(reverse("planner:result", args=[rec.task_request.pk]))
        self.assertContains(resp, "Why this setup")
        self.assertNotContains(resp, "policy_conditioning")
