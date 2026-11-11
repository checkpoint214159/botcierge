from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import CustomerProfile


class ProfileTests(TestCase):
    def test_customer_can_edit_profile(self):
        user = User.objects.create_user("p1", password="pw12345678")
        CustomerProfile.objects.create(user=user, housing_type="hdb")
        self.client.login(username="p1", password="pw12345678")
        resp = self.client.post(reverse("accounts:profile"), {
            "phone": "91234567", "address": "1 Test Rd", "postal_code": "123456",
            "housing_type": "condo", "household_size": 3})
        self.assertRedirects(resp, reverse("accounts:profile"))
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.housing_type, "condo")

    def test_profile_requires_login(self):
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 302)
