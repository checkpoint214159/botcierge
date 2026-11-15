"""Book a spread of test orders so the staff review queue (A08) has something to work through.

    python manage.py seed_demo             # catalogue first
    python manage.py seed_review_orders    # add the test orders
    python manage.py seed_review_orders --reset   # delete them and book a fresh set

Goes through the real code path (decompose -> booking details -> create_order), not the UI.
Test customers are tester1..tester4 (password testpass123). --reset only touches their data.
Ship days run from yesterday (overdue) to a week out, with mixed budgets, so the queue's grouping
(by ship day) and sorting (biggest order first within a day) are visible.
"""
import io
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from accounts.models import Address, CustomerProfile
from catalog.models import RobotModel
from orders.models import Order
from orders.services import NoUnitFree, create_order
from planner.decomposer import decompose, eligible_robots, refresh_conditioning, requote, save_customer_edit
from planner.models import TaskRequest

CUSTOMERS = [
    ("tester1", "Aisha", "Tan", "Blk 456 Bedok North Ave 3", "#05-12", "460456"),
    ("tester2", "Ravi", "Kumar", "12 Sunset Way", "", "597080"),
    ("tester3", "Mei Ling", "Wong", "Blk 88 Toa Payoh Lor 4", "#11-201", "310088"),
    ("tester4", "Daniel", "Lim", "3 Jurong West St 91", "#02-07", "640003"),
]

# customer, ship day offset, days, category hint ("" = let M1 decide), description, budget, extra fields, extras
SCENARIOS = [
    ("tester1", -1, 2, "", "vacuum and mop the whole flat, the cat sheds everywhere", 300,
     dict(area_m2=95, num_rooms=4, floor_type="tile", has_pets=True), {"zones": 2}),
    ("tester2", 0, 1, "event_serving", "serve drinks and canapes at my daughter's birthday party, about 40 guests", 1800,
     dict(area_m2=180, num_rooms=5, housing_type="landed", floor_type="wood", hours_per_day=6, payload_kg=2), {}),
    ("tester3", 0, 3, "", "pls mop the floors before CNY, got toddler running around", 250,
     dict(area_m2=85, num_rooms=4, floor_type="tile", has_children=True), {"zones": 1}),
    # no payload, so the rules map this to a wheeled base and the cheapest is a robot vacuum: a plan review should catch
    ("tester4", 0, 2, "elder_care", "keep my grandmother company in the day, remind her to take her medicine", 900,
     dict(area_m2=100, num_rooms=4, floor_type="tile", hours_per_day=8), {}),
    ("tester1", 1, 5, "elder_care", "help my dad fetch things around the house after his knee surgery", 3000,
     dict(area_m2=110, num_rooms=5, housing_type="condo", floor_type="wood", hours_per_day=8, payload_kg=2), {"zones": 1}),
    ("tester2", 1, 2, "", "mow the lawn and trim the edges, the grass is very long", 400,
     dict(area_m2=200, num_rooms=1, housing_type="landed", floor_type="grass", is_outdoor=True), {}),
    ("tester3", 1, 1, "", "clean the windows of my shop, the glass facade is filthy", 350,
     dict(area_m2=60, num_rooms=1, housing_type="shophouse", floor_type="glass"), {"customer_edit": True}),
    ("tester4", 2, 3, "home_patrol", "patrol the house at night while we are overseas", 900,
     dict(area_m2=250, num_rooms=6, housing_type="landed", floor_type="mixed", has_stairs=True, hours_per_day=10), {}),
    ("tester1", 2, 1, "event_serving", "serve food at a small dinner party for 12", 700,
     dict(area_m2=110, num_rooms=4, housing_type="condo", floor_type="wood", hours_per_day=4), {"review": "approved"}),
    ("tester2", 3, 2, "", "tidy up the kids room, toys everywhere and fragile figurines on the shelf", 900,
     dict(area_m2=40, num_rooms=2, housing_type="landed", floor_type="carpet", fragile_items=True), {"zones": 3}),
    ("tester3", 4, 2, "", "clean the swimming pool, leaves and algae", 450,
     dict(area_m2=35, num_rooms=1, housing_type="landed", floor_type="water", is_outdoor=True), {"review": "rejected"}),
    ("tester4", 6, 3, "floor_cleaning", "deep clean the floors after renovation, lots of dust", 600,
     dict(area_m2=120, num_rooms=5, housing_type="condo", floor_type="mixed"), {}),
]


def floor_plan_png(seed: int) -> bytes:
    """A simple drawn floor plan (rooms as rectangles), different per order."""
    img = Image.new("RGB", (480, 320), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 470, 310], outline="black", width=4)
    split = 160 + (seed * 37) % 140
    d.line([split, 10, split, 310], fill="black", width=3)
    d.line([split, 160, 470, 160], fill="black", width=3)
    d.line([10, 120 + (seed * 23) % 100, split, 120 + (seed * 23) % 100], fill="black", width=3)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


ZONES = [{"x": 0.05, "y": 0.08, "w": 0.2, "h": 0.25}, {"x": 0.6, "y": 0.6, "w": 0.3, "h": 0.3},
         {"x": 0.4, "y": 0.1, "w": 0.15, "h": 0.2}]


class Command(BaseCommand):
    help = "Book test orders (several task types, ship days and budgets) for the staff review queue"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="delete the test customers' orders and plans first")

    def handle(self, *args, **opts):
        if not RobotModel.objects.filter(is_active=True).exists():
            self.stderr.write(self.style.ERROR("No robots in the catalogue. Run: python manage.py seed_demo"))
            return
        users = {}
        for username, first, last, line, unit, postal in CUSTOMERS:
            u, created = User.objects.get_or_create(username=username, defaults={
                "first_name": first, "last_name": last, "email": f"{username}@botcierge.test"})
            if created:
                u.set_password("testpass123")
                u.save()
                CustomerProfile.objects.create(user=u, housing_type="hdb", postal_code=postal)
            if not u.addresses.exists():
                Address.objects.create(customer=u, label="Home", line=line, unit=unit, postal_code=postal)
            users[username] = u

        if opts["reset"]:
            Order.objects.filter(customer__in=users.values()).delete()
            TaskRequest.objects.filter(customer__in=users.values()).delete()

        staff = User.objects.filter(is_staff=True).first()
        today = timezone.localdate()
        made, skipped = 0, []
        for i, (who, offset, days, hint, text, budget, fields, extra) in enumerate(SCENARIOS):
            user = users[who]
            start = today + timedelta(days=offset)
            try:
                with transaction.atomic():
                    tr = TaskRequest.objects.create(
                        customer=user, description=text, category_hint=hint, budget_sgd=budget,
                        start_date=start, deadline_date=start + timedelta(days=days - 1),
                        **{"hours_per_day": 4, "num_rooms": 3, "area_m2": 80, **fields})
                    rec = decompose(tr)
                    if rec.robot_model is None:
                        # say why, so a missing or edited catalogue is obvious
                        raise ValueError(f"no active robot is listed for {tr.spec.task_category} and fits "
                                         f"this home; run seed_demo, or check /staff/robots/")
                    if extra.get("customer_edit"):
                        # the customer swapped to a pricier robot, if there is one
                        other = eligible_robots(tr).exclude(pk=rec.robot_model_id).order_by("-daily_rate").first()
                        if other:
                            rec = save_customer_edit(rec, other, [a for a in rec.addons.all() if a.fits(other.platform)],
                                                     rec.skill_pack if rec.skill_pack and
                                                     rec.skill_pack.compatible_robots.filter(pk=other.pk).exists() else None)
                    tr.refresh_from_db()
                    tr.address = user.addresses.first()
                    tr.keep_out_zones = ZONES[:extra.get("zones", 0)]
                    tr.floor_plan.save(f"test-plan-{i}.png", ContentFile(floor_plan_png(i)), save=False)
                    tr.status = TaskRequest.Status.PLANNED
                    tr.save()
                    rec = refresh_conditioning(requote(rec))
                    order = create_order(user, rec, tr.address.one_line(), None, reference=f"TEST-{i:03d}")
                    if extra.get("review") == "approved":
                        order.review_status, order.reviewed_by = Order.Review.APPROVED, staff
                    elif extra.get("review") == "rejected":
                        order.review_status, order.reviewed_by = Order.Review.REJECTED, staff
                        order.review_note = "Pool is very green, check if they need a shock treatment first."
                    if extra.get("review"):
                        order.reviewed_at = timezone.now()
                        order.save()
                    made += 1
            except (NoUnitFree, ValueError) as e:
                skipped.append(f"{text[:40]}... ({e.__class__.__name__ if isinstance(e, NoUnitFree) else e})")

        self.stdout.write(self.style.SUCCESS(f"Booked {made} test orders for tester1-4 (password testpass123)."))
        for s in skipped:
            self.stdout.write(self.style.WARNING(f"  skipped: {s}"))
