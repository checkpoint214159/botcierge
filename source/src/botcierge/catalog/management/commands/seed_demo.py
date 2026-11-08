"""Populate the database with a demo catalogue, fleet and accounts.

    python manage.py seed_demo          # add data (idempotent)
    python manage.py seed_demo --reset  # wipe catalogue/fleet first

All robot names and manufacturers are fictional.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import CustomerProfile
from catalog.models import AddOn, FleetUnit, RobotModel, SkillPack
from orders.models import PromoCode

# name, slug, platform, rate, indoor, outdoor, stairs, payload, battery, noise, tagline
ROBOTS = [
    ("Dustin S1", "dustin-s1", "wheeled_amr", 39, True, False, False, 0, 3, 58, "Compact vacuum-mop base for flats"),
    ("Dustin Pro", "dustin-pro", "wheeled_amr", 59, True, True, False, 2, 5, 52, "Larger base, quiet mode, outdoor capable"),
    ("Tidbit M2", "tidbit-m2", "mobile_manipulator", 129, True, False, False, 3, 4, 50, "Wheeled base with a 6-DoF arm"),
    ("Tidbit M4", "tidbit-m4", "mobile_manipulator", 189, True, True, False, 8, 6, 48, "Heavier payload, dual-purpose indoor/outdoor"),
    ("Strider Q", "strider-q", "quadruped", 219, True, True, True, 5, 3, 60, "Legged robot for stairs and rough ground"),
    ("Atlas-lite H1", "atlas-lite-h1", "humanoid", 449, True, False, True, 10, 3, 55, "General-purpose humanoid for complex homes"),
    ("Greenstripe L1", "greenstripe-l1", "lawn_robot", 45, False, True, False, 0, 4, 62, "Boundary-learning lawn mower"),
    ("Clearview W1", "clearview-w1", "window_crawler", 35, True, True, False, 0, 2, 50, "Suction crawler for glass, tethered"),
    ("Deepblue P1", "deepblue-p1", "pool_crawler", 42, False, True, False, 0, 3, 40, "Floor and wall pool crawler"),
    ("Butler C1", "butler-c1", "service_cart", 69, True, True, False, 15, 6, 45, "Three-tier serving cart for events"),
]

# code, name, rate, compatible platforms ("" = all)
ADDONS = [
    ("vacuum_module", "Vacuum module", 8, "wheeled_amr,mobile_manipulator,quadruped"),
    ("mop_module", "Mop module", 8, "wheeled_amr,mobile_manipulator"),
    ("gripper", "Soft gripper", 15, "mobile_manipulator,humanoid,quadruped"),
    ("stair_kit", "Stair kit", 25, "wheeled_amr,mobile_manipulator"),
    ("outdoor_kit", "Outdoor weatherproofing kit", 12, ""),
    ("camera_mast", "Camera mast", 10, ""),
    ("tray_rack", "Tray rack", 6, "mobile_manipulator,service_cart,humanoid"),
    ("extra_battery", "Extra battery", 9, ""),
    ("pet_safe_bumper", "Pet-safe bumper", 4, "wheeled_amr,mobile_manipulator,lawn_robot"),
    ("voice_interface", "Voice interface", 7, ""),
]

# code, name, fee, compatible platforms, summary, default conditioning
SKILL_PACKS = [
    ("coverage_clean", "Coverage Clean", 15, ["wheeled_amr", "quadruped", "mobile_manipulator"],
     "Full-room boustrophedon cleaning", {"pattern": "boustrophedon", "overlap": 0.15}),
    ("spot_clean", "Spot Clean", 10, ["wheeled_amr", "mobile_manipulator"],
     "Targets high-traffic and dirty spots", {"pattern": "spot", "dirt_detection": True}),
    ("facade_crawl", "Facade Crawl", 12, ["window_crawler"],
     "Panel-by-panel glass cleaning", {"pattern": "zigzag", "edge_squeegee": True}),
    ("lawn_coverage", "Lawn Coverage", 10, ["lawn_robot", "quadruped"],
     "Striped mowing inside a learned boundary", {"pattern": "stripes", "cut_height_mm": 40}),
    ("pool_coverage", "Pool Coverage", 10, ["pool_crawler"],
     "Floor and wall coverage", {"pattern": "random_walk", "wall_climb": True}),
    ("pick_and_place", "Pick & Place", 25, ["mobile_manipulator", "humanoid"],
     "Picks up loose items and returns them to set spots", {"grasp_policy": "diffusion_v2"}),
    ("declutter_sort", "Declutter & Sort", 35, ["mobile_manipulator", "humanoid"],
     "Sorts items by type into bins across rooms", {"grasp_policy": "diffusion_v2", "sorting": "by_type"}),
    ("companion_monitor", "Companion Monitor", 20, ["wheeled_amr", "mobile_manipulator", "humanoid"],
     "Check-ins, reminders and fall alerts", {"checkin_interval_min": 60, "fall_detection": True}),
    ("fetch_and_deliver", "Fetch & Deliver", 25, ["mobile_manipulator", "humanoid"],
     "Brings requested items to a person", {"grasp_policy": "diffusion_v2", "handover": "gentle"}),
    ("serve_and_navigate", "Serve & Navigate", 20, ["service_cart", "mobile_manipulator", "humanoid"],
     "Circulates through crowds with trays", {"crowd_nav": True, "max_tray_tilt_deg": 5}),
    ("patrol_route", "Patrol Route", 15, ["wheeled_amr", "quadruped"],
     "Waypoint patrol with anomaly alerts", {"loop_minutes": 30, "alert_on": ["person", "open_door"]}),
]


class Command(BaseCommand):
    help = "Seed demo catalogue, fleet, promo code and demo accounts"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **opts):
        if opts["reset"]:
            FleetUnit.objects.all().delete()
            SkillPack.objects.all().delete()
            AddOn.objects.all().delete()

        robots = {}
        for name, slug, plat, rate, indoor, outdoor, stairs, payload, batt, noise, tag in ROBOTS:
            r, _ = RobotModel.objects.update_or_create(slug=slug, defaults=dict(
                name=name, platform=plat, manufacturer="Botcierge Labs (fictional)", tagline=tag,
                description=tag + ".", daily_rate=Decimal(rate), indoor=indoor, outdoor=outdoor,
                can_climb_stairs=stairs, max_payload_kg=Decimal(payload), battery_hours=Decimal(batt),
                noise_db=noise))
            robots[slug] = r
            for i in range(1, 4):
                FleetUnit.objects.get_or_create(
                    serial_number=f"{slug.upper()}-{i:03d}",
                    defaults=dict(robot_model=r, last_serviced=date.today() - timedelta(days=10 * i)))

        for code, name, rate, plats in ADDONS:
            AddOn.objects.update_or_create(code=code, defaults=dict(
                name=name, daily_rate=Decimal(rate), compatible_platforms=plats))

        for code, name, fee, plats, summary, cond in SKILL_PACKS:
            sp, _ = SkillPack.objects.update_or_create(code=code, defaults=dict(
                name=name, flat_fee=Decimal(fee), summary=summary, default_conditioning=cond))
            sp.compatible_robots.set([r for r in robots.values() if r.platform in plats])

        PromoCode.objects.get_or_create(code="WELCOME10", defaults={"percent_off": 10})

        if not User.objects.filter(username="staff").exists():
            User.objects.create_user("staff", "staff@botcierge.test", "staffpass123",
                                     first_name="Sam", is_staff=True)
        if not User.objects.filter(username="demo").exists():
            u = User.objects.create_user("demo", "demo@botcierge.test", "demopass123", first_name="Dana")
            CustomerProfile.objects.create(user=u, housing_type="hdb", postal_code="640123")

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {RobotModel.objects.count()} robots, {FleetUnit.objects.count()} units, "
            f"{AddOn.objects.count()} add-ons, {SkillPack.objects.count()} skill packs. "
            "Logins: demo/demopass123 (customer), staff/staffpass123 (staff)."))
