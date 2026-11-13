"""Populate the database with a demo catalogue, fleet and accounts.

    python manage.py seed_demo          # add data (idempotent)
    python manage.py seed_demo --reset  # wipe catalogue/fleet first

The catalogue lists real, commercially available robots. Specs are approximate,
taken from public product information, and should be checked against the
manufacturers' spec sheets before the demo. Daily rates are Botcierge's own
rental pricing. Photos are freely licensed from Wikimedia Commons and credited
on each robot page (see PHOTO_CREDITS and docs/image_credits.md).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import CustomerProfile
from catalog.models import AddOn, FleetUnit, RobotModel, SkillPack
from orders.models import PromoCode

# name, slug, platform, manufacturer, rate (S$/day), indoor, outdoor, stairs, payload kg, battery h, noise dB, tagline
ROBOTS = [
    ("Roomba i7+", "roomba-i7-plus", "wheeled_amr", "iRobot", 29, True, False, False, 0, 1.2, 62,
     "Robot vacuum that maps your rooms and empties itself"),
    ("PUDU CC1", "pudu-cc1", "wheeled_amr", "Pudu Robotics", 89, True, False, False, 0, 4, 60,
     "Scrub, sweep, vacuum and mop in one pass, built for shops and big homes"),
    ("TIAGo", "tiago", "mobile_manipulator", "PAL Robotics", 169, True, False, False, 3, 4, 50,
     "Mobile base with a 7-DoF arm and gripper for picking things up"),
    ("TIAGo++", "tiago-plus-plus", "mobile_manipulator", "PAL Robotics", 249, True, False, False, 4, 4, 50,
     "Two-armed TIAGo for tidying and two-handed tasks"),
    ("Go2", "unitree-go2", "quadruped", "Unitree Robotics", 119, True, True, True, 7, 2, 55,
     "Agile robot dog for patrols, stairs and rough ground"),
    ("Spot", "spot", "quadruped", "Boston Dynamics", 549, True, True, True, 14, 1.5, 60,
     "Rugged, weather-resistant quadruped with a 14 kg payload"),
    ("G1", "unitree-g1", "humanoid", "Unitree Robotics", 389, True, False, True, 2, 2, 55,
     "Compact humanoid with dexterous hands for complex homes"),
    ("Automower 430X", "automower-430x", "lawn_robot", "Husqvarna", 39, False, True, False, 0, 2.4, 58,
     "Robotic mower for lawns up to about 3,200 m², handles slopes"),
    ("Winbot W930", "winbot-w930", "window_crawler", "Ecovacs Robotics", 25, True, True, False, 0, 0.3, 55,
     "Suction window cleaner with a safety tether, runs on mains power"),
    ("Scuba N1 Pro", "aiper-scuba-n1-pro", "pool_crawler", "Aiper", 35, False, True, False, 0, 2.5, 40,
     "Cordless pool robot that cleans the floor, walls and waterline"),
    ("BellaBot", "bellabot", "service_cart", "Pudu Robotics", 69, True, False, False, 40, 10, 45,
     "Four-tray serving robot for parties and small eateries"),
]

# slug -> (author, licence, Wikimedia Commons file page)
PHOTO_CREDITS = {
    "roomba-i7-plus": ("Auledas", "CC BY-SA 4.0", "https://commons.wikimedia.org/wiki/File:IRobot_Roomba_i7%2B.jpg"),
    "pudu-cc1": ("Retired electrician", "CC0", "https://commons.wikimedia.org/wiki/File:Moscow,_PUDU_CC1_cleaning_bot_at_Perekryostok_shop,_June_2025_01.jpg"),
    "tiago": ("ubahnverleih", "CC0", "https://commons.wikimedia.org/wiki/File:RoboCup_2016_Leipzig_-_TIAGo.jpg"),
    "tiago-plus-plus": ("PAL Robotics", "CC BY-SA 4.0", "https://commons.wikimedia.org/wiki/File:TIAGo%2B%2B_side.jpg"),
    "unitree-go2": ("HotNews Romania - Adi Iacob, Ovidiu Popica", "CC BY 3.0", "https://commons.wikimedia.org/wiki/File:Unitree_Go2_of_Salvamont_side_view.jpg"),
    "spot": ("Jonte", "CC BY-SA 4.0", "https://commons.wikimedia.org/wiki/File:Spot_by_Boston_Dynamics.jpg"),
    "unitree-g1": ("Sayanesy", "CC0", "https://commons.wikimedia.org/wiki/File:Unitree_G1.jpg"),
    "automower-430x": ("Syced", "CC0", "https://commons.wikimedia.org/wiki/File:Husqvarna_automower_430X.jpg"),
    "winbot-w930": ("Michael Kramer", "CC BY-SA 3.0", "https://commons.wikimedia.org/wiki/File:Winbot_W930_Fensterputzroboter_oben.jpg"),
    "aiper-scuba-n1-pro": ("TaurusEmerald", "CC BY-SA 4.0", "https://commons.wikimedia.org/wiki/File:Aiper_Scuba_N1_Pro_Robotic_Pool_Cleaner.jpg"),
    "bellabot": ("MIKI Yoshihito", "CC BY 2.0", "https://commons.wikimedia.org/wiki/File:Serving_robots_%22BellaBot%22_(52139754346).jpg"),
}

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

        # Older databases were seeded with a fictional catalogue. Hide those robots rather than
        # delete them, because existing plans and fleet units still point at them (on_delete=PROTECT).
        RobotModel.objects.filter(manufacturer="Botcierge Labs (fictional)").update(is_active=False)

        robots = {}
        for name, slug, plat, maker, rate, indoor, outdoor, stairs, payload, batt, noise, tag in ROBOTS:
            author, licence, credit_url = PHOTO_CREDITS[slug]
            r, _ = RobotModel.objects.update_or_create(slug=slug, defaults=dict(
                name=name, platform=plat, manufacturer=maker, tagline=tag,
                description=tag + ".", daily_rate=Decimal(rate), indoor=indoor, outdoor=outdoor,
                can_climb_stairs=stairs, max_payload_kg=Decimal(payload), battery_hours=Decimal(str(batt)),
                noise_db=noise, is_active=True, stock_image=f"img/robots/{slug}.jpg",
                image_credit=f"Photo: {author}, {licence}, via Wikimedia Commons",
                image_credit_url=credit_url))
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
            f"Seeded {RobotModel.objects.filter(is_active=True).count()} robots, "
            f"{FleetUnit.objects.filter(robot_model__is_active=True).count()} units, "
            f"{AddOn.objects.count()} add-ons, {SkillPack.objects.count()} skill packs. "
            "Logins: demo/demopass123 (customer), staff/staffpass123 (staff)."))
