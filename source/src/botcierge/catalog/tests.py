from django.test import TestCase

# Create your tests here.


class RobotSortTests(TestCase):
    def test_sort_by_price(self):
        from django.core.management import call_command
        from django.urls import reverse
        call_command("seed_demo", verbosity=0)
        for key, rev in (("price_asc", False), ("price_desc", True)):
            robots = self.client.get(reverse("catalog:robot_list"), {"sort": key}).context["robots"]
            prices = [r.daily_rate for r in robots]
            self.assertEqual(prices, sorted(prices, reverse=rev))
