from django.conf import settings
from django.db import models

from catalog.models import AddOn, RobotModel, SkillPack
from catalog.taxonomy import FLOOR_TYPE_CHOICES, TASK_CATEGORY_CHOICES


class TaskRequest(models.Model):
    """What the customer typed in: the chore, the space, and the constraints."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PLANNED = "planned", "Planned"
        BOOKED = "booked", "Booked"

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_requests")
    title = models.CharField(max_length=120, blank=True)
    description = models.TextField(help_text="The chore in the customer's own words")
    category_hint = models.CharField(max_length=30, choices=TASK_CATEGORY_CHOICES, blank=True,
                                     help_text="Optional. Overrides M1 when the customer picks one.")

    # space
    floor_plan = models.ImageField(upload_to="floorplans/", blank=True)
    address = models.ForeignKey("accounts.Address", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="task_requests", help_text="Where the robot is delivered (set on the booking page)")
    housing_type = models.CharField(max_length=20, default="hdb")
    area_m2 = models.DecimalField(max_digits=7, decimal_places=1)
    num_rooms = models.PositiveSmallIntegerField(default=1)
    floor_type = models.CharField(max_length=20, choices=FLOOR_TYPE_CHOICES, default="tile")
    has_stairs = models.BooleanField(default=False)
    is_outdoor = models.BooleanField(default=False)
    has_pets = models.BooleanField(default=False)
    has_children = models.BooleanField(default=False)
    fragile_items = models.BooleanField(default=False)
    payload_kg = models.DecimalField(max_digits=5, decimal_places=1, default=0,
                                     help_text="Heaviest item the robot must carry")

    # constraints
    budget_sgd = models.DecimalField(max_digits=9, decimal_places=2)
    start_date = models.DateField()
    deadline_date = models.DateField()
    hours_per_day = models.PositiveSmallIntegerField(default=4)
    quiet_hours = models.CharField(max_length=40, blank=True, help_text="e.g. 22:00-08:00")
    special_notes = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or self.description[:40]

    @property
    def duration_days(self) -> int:
        return max(1, (self.deadline_date - self.start_date).days + 1)


class TaskSpec(models.Model):
    """The decomposition of a TaskRequest into a serviceable spec (output of M1 + M5 + rules)."""

    task_request = models.OneToOneField(TaskRequest, on_delete=models.CASCADE, related_name="spec")
    task_category = models.CharField(max_length=30, choices=TASK_CATEGORY_CHOICES)
    category_confidence = models.FloatField(default=0)
    subtasks = models.JSONField(default=list)
    edge_cases = models.JSONField(default=list)
    est_robot_hours = models.FloatField()
    est_days_needed = models.PositiveSmallIntegerField()
    feasible_in_time = models.BooleanField(default=True)
    within_budget = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Spec for {self.task_request}"


class Recommendation(models.Model):
    """Robot + add-ons + skill pack + policy conditioning + quote for a TaskRequest.

    The ML output is stored with source=ML. If the customer swaps items (or staff override
    before dispatch) a new row is saved with source=CUSTOMER/STAFF, which gives us
    acceptance-rate data to monitor and retrain the models.
    """

    class Source(models.TextChoices):
        ML = "ml", "Model"
        CUSTOMER = "customer", "Customer edit"
        STAFF = "staff", "Staff override"

    task_request = models.ForeignKey(TaskRequest, on_delete=models.CASCADE, related_name="recommendations")
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.ML)
    robot_model = models.ForeignKey(RobotModel, on_delete=models.PROTECT, null=True)
    predicted_platform = models.CharField(max_length=30, blank=True)
    platform_confidence = models.FloatField(default=0)
    addons = models.ManyToManyField(AddOn, blank=True)
    skill_pack = models.ForeignKey(SkillPack, on_delete=models.PROTECT, null=True)
    policy_conditioning = models.JSONField(default=dict, help_text="Staff-facing deployment config")
    quoted_price = models.DecimalField(max_digits=9, decimal_places=2)
    price_breakdown = models.JSONField(default=dict)
    is_selected = models.BooleanField(default=False, help_text="The version that went to checkout")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_source_display()} rec for {self.task_request}"
