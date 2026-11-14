from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Address, CustomerProfile


class ProfileTests(TestCase):
    def test_customer_can_edit_profile(self):
        user = User.objects.create_user("p1", password="pw12345678")
        CustomerProfile.objects.create(user=user, housing_type="hdb")
        self.client.login(username="p1", password="pw12345678")
        resp = self.client.post(reverse("accounts:profile"), {
            "phone": "91234567", "housing_type": "condo", "household_size": 3})
        self.assertRedirects(resp, reverse("accounts:profile"))
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.housing_type, "condo")

    def test_profile_requires_login(self):
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 302)


class AddressTests(TestCase):
    """S19: saved delivery addresses."""

    def setUp(self):
        self.user = User.objects.create_user("a1", password="pw12345678")
        self.client.login(username="a1", password="pw12345678")

    def add(self, **kw):
        data = {"label": "Home", "line": "1 Test Rd", "unit": "", "postal_code": "640123"}
        data.update(kw)
        return self.client.post(reverse("accounts:addresses"), data)

    def test_first_address_becomes_default_and_new_default_replaces_old(self):
        self.add()
        self.assertTrue(Address.objects.get(label="Home").is_default)
        self.add(label="Office", postal_code="238801", is_default="on")
        self.assertFalse(Address.objects.get(label="Home").is_default)
        self.assertTrue(Address.objects.get(label="Office").is_default)

    def test_rejects_non_singapore_postal_code(self):
        resp = self.add(postal_code="999999")
        self.assertContains(resp, "deliver to")
        self.assertFalse(Address.objects.exists())

    def test_cannot_touch_someone_elses_address(self):
        other = User.objects.create_user("a2", password="pw12345678")
        theirs = Address.objects.create(customer=other, label="Theirs", line="x", postal_code="640123")
        self.assertEqual(self.client.get(reverse("accounts:address_edit", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("accounts:address_delete", args=[theirs.pk])).status_code, 404)

    def test_next_redirect_only_to_our_site(self):
        resp = self.add(next="/orders/cart/")
        self.assertRedirects(resp, "/orders/cart/", fetch_redirect_response=False)
        resp = self.add(label="Two", next="https://evil.example/")
        self.assertRedirects(resp, reverse("accounts:addresses"))
