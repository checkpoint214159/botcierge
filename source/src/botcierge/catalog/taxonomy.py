"""Label vocabulary shared by the Django models and the ML pipeline.

Codes must match source/ml/taxonomy.py, because the joblib models
predict these exact strings.
"""

TASK_CATEGORY_CHOICES = [
    ("floor_cleaning", "Floor cleaning"),
    ("window_cleaning", "Window & glass cleaning"),
    ("lawn_care", "Lawn care"),
    ("pool_cleaning", "Pool cleaning"),
    ("tidying", "Tidying & decluttering"),
    ("elder_care", "Elder companionship"),
    ("event_serving", "Event serving"),
    ("home_patrol", "Home patrol"),
]

PLATFORM_CHOICES = [
    ("wheeled_amr", "Wheeled base"),
    ("mobile_manipulator", "Mobile manipulator"),
    ("quadruped", "Quadruped"),
    ("humanoid", "Humanoid"),
    ("lawn_robot", "Lawn robot"),
    ("window_crawler", "Window crawler"),
    ("pool_crawler", "Pool crawler"),
    ("service_cart", "Service cart"),
]

ADDON_CHOICES = [
    ("vacuum_module", "Vacuum module"),
    ("mop_module", "Mop module"),
    ("gripper", "Gripper"),
    ("stair_kit", "Stair kit"),
    ("outdoor_kit", "Outdoor weatherproofing kit"),
    ("camera_mast", "Camera mast"),
    ("tray_rack", "Tray rack"),
    ("extra_battery", "Extra battery"),
    ("pet_safe_bumper", "Pet-safe bumper"),
    ("voice_interface", "Voice interface"),
]

SKILL_PACK_CHOICES = [
    ("coverage_clean", "Coverage Clean"),
    ("spot_clean", "Spot Clean"),
    ("facade_crawl", "Facade Crawl"),
    ("lawn_coverage", "Lawn Coverage"),
    ("pool_coverage", "Pool Coverage"),
    ("pick_and_place", "Pick & Place"),
    ("declutter_sort", "Declutter & Sort"),
    ("companion_monitor", "Companion Monitor"),
    ("fetch_and_deliver", "Fetch & Deliver"),
    ("serve_and_navigate", "Serve & Navigate"),
    ("patrol_route", "Patrol Route"),
]

FLOOR_TYPE_CHOICES = [
    ("tile", "Tile"),
    ("wood", "Wood / parquet"),
    ("carpet", "Carpet"),
    ("mixed", "Mixed"),
    ("grass", "Grass"),
    ("concrete", "Concrete"),
    ("glass", "Glass (windows)"),
    ("water", "Water (pool)"),
]


# Starting values: seed_demo (and migration catalog 0004) copy these onto each robot as
# RobotModel.task_categories, by platform; after that staff edit them per robot (A03).
# They also mirror the ML labelling rules, i.e. what the recommender (M2) learned.
# Which platforms (and, initially, skill packs) make sense for each task type. Mirrors the labelling rules
# in source/ml/generate_data.py (label_platform / label_skill_pack), so the booking page only offers
# what the models could have recommended. Update both together.
TASK_PLATFORMS = {
    "floor_cleaning": ["wheeled_amr", "quadruped"],
    "window_cleaning": ["window_crawler"],
    "lawn_care": ["lawn_robot", "quadruped"],
    "pool_cleaning": ["pool_crawler"],
    "tidying": ["mobile_manipulator", "humanoid"],
    "elder_care": ["wheeled_amr", "mobile_manipulator", "humanoid"],
    "event_serving": ["service_cart", "mobile_manipulator"],
    "home_patrol": ["wheeled_amr", "quadruped"],
}

# Starting values only: seed_demo copies these into SkillPack.task_categories, and from then on
# the database is the source of truth (staff edit it in A05).
TASK_SKILL_PACKS = {
    "floor_cleaning": ["coverage_clean", "spot_clean"],
    "window_cleaning": ["facade_crawl"],
    "lawn_care": ["lawn_coverage"],
    "pool_cleaning": ["pool_coverage"],
    "tidying": ["declutter_sort", "pick_and_place"],
    "elder_care": ["companion_monitor", "fetch_and_deliver"],
    "event_serving": ["serve_and_navigate"],
    "home_patrol": ["patrol_route"],
}
