"""Shared label vocabulary for the Botcierge decomposition pipeline.

These codes are also used as `choices` in the Django models (catalog/planner),
so keep the two in sync if you add a category, platform, add-on or skill pack.
"""

TASK_CATEGORIES = [
    "floor_cleaning",
    "window_cleaning",
    "lawn_care",
    "pool_cleaning",
    "tidying",
    "elder_care",
    "event_serving",
    "home_patrol",
]

PLATFORMS = [
    "wheeled_amr",          # vacuum/mop style base, cheap, flat floors only
    "mobile_manipulator",   # wheeled base + arm, can grasp
    "quadruped",            # legged, stairs and rough outdoor ground
    "humanoid",             # most capable, most expensive
    "lawn_robot",
    "window_crawler",
    "pool_crawler",
    "service_cart",         # tray carrier for serving
]

ADDONS = [
    "vacuum_module",
    "mop_module",
    "gripper",
    "stair_kit",
    "outdoor_kit",
    "camera_mast",
    "tray_rack",
    "extra_battery",
    "pet_safe_bumper",
    "voice_interface",
]

SKILL_PACKS = [
    "coverage_clean",
    "spot_clean",
    "facade_crawl",
    "lawn_coverage",
    "pool_coverage",
    "pick_and_place",
    "declutter_sort",
    "companion_monitor",
    "fetch_and_deliver",
    "serve_and_navigate",
    "patrol_route",
]

FLOOR_TYPES = ["tile", "wood", "carpet", "mixed", "grass", "concrete", "glass", "water"]
HOUSING_TYPES = ["hdb", "condo", "landed", "shophouse"]

# Feature columns fed to the structured models (M2-M5). M1 uses `description` only.
NUMERIC_FEATURES = [
    "area_m2", "num_rooms", "payload_kg", "budget_sgd", "duration_days", "hours_per_day",
]
BOOLEAN_FEATURES = [
    "has_stairs", "is_outdoor", "has_pets", "has_children", "fragile_items",
]
CATEGORICAL_FEATURES = ["task_category", "floor_type", "housing_type"]
STRUCTURED_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES + BOOLEAN_FEATURES
