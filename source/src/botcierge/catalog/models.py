from django.core.validators import RegexValidator
from django.db import models
from django.templatetags.static import static

from .taxonomy import PLATFORM_CHOICES

# Add-on and skill pack codes are what the ML models predict, so they are short fixed strings.
# Staff can create new ones (A05); the models only learn a new code after retraining.
code_validator = RegexValidator(r"^[a-z][a-z0-9_]*$", "Lower-case letters, digits and underscores, e.g. mop_module.")


def split_codes(value: str) -> list[str]:
    """Comma-separated codes stored in a CharField -> list (empty string = empty list)."""
    return [c for c in value.split(",") if c]


class RobotModel(models.Model):
    """A rentable robot product line (the catalogue entry, not a physical unit)."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    platform = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    manufacturer = models.CharField(max_length=100, blank=True)
    tagline = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="robots/", blank=True, help_text="Uploaded by staff; overrides stock_image")
    stock_image = models.CharField(max_length=200, blank=True,
                                   help_text="Path under static/, e.g. img/robots/spot.jpg (seeded photos)")
    image_credit = models.CharField(max_length=255, blank=True, help_text="Photographer and licence, shown under the photo")
    image_credit_url = models.URLField(blank=True)
    daily_rate = models.DecimalField(max_digits=8, decimal_places=2, help_text="SGD per robot-day")
    indoor = models.BooleanField(default=True)
    outdoor = models.BooleanField(default=False)
    can_climb_stairs = models.BooleanField(default=False)
    max_payload_kg = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    battery_hours = models.DecimalField(max_digits=4, decimal_places=1, default=4)
    noise_db = models.PositiveSmallIntegerField(default=55)
    task_categories = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated task category codes this robot can be booked for.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["platform", "daily_rate"]

    def __str__(self):
        return self.name

    @property
    def image_url(self) -> str:
        """Staff upload if there is one, else the seeded static photo, else empty (template shows a placeholder)."""
        if self.image:
            return self.image.url
        if self.stock_image:
            return static(self.stock_image)
        return ""

    @property
    def category_list(self) -> list[str]:
        return split_codes(self.task_categories)

    @property
    def available_units(self):
        return self.units.filter(status=FleetUnit.Status.AVAILABLE).count()


class AddOn(models.Model):
    """Hardware extension attached to a robot for a job (mop module, stair kit, ...)."""

    code = models.CharField(max_length=30, unique=True, validators=[code_validator])
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    daily_rate = models.DecimalField(max_digits=7, decimal_places=2)
    compatible_platforms = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated platform codes. Blank means compatible with all.")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @property
    def platform_list(self) -> list[str]:
        return split_codes(self.compatible_platforms)

    def fits(self, platform: str) -> bool:
        return not self.compatible_platforms or platform in self.platform_list


class SkillPack(models.Model):
    """A trained robot policy offered as a product. `default_conditioning` holds the policy's
    tunable parameters; the planner fills in per-job values on top of these defaults."""

    code = models.CharField(max_length=30, unique=True, validators=[code_validator])
    name = models.CharField(max_length=100)
    version = models.CharField(max_length=20, default="1.0")
    summary = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    flat_fee = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    compatible_robots = models.ManyToManyField(RobotModel, related_name="skill_packs", blank=True)
    task_categories = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated task category codes this pack is offered for on the booking page.")
    default_conditioning = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} v{self.version}"

    @property
    def category_list(self) -> list[str]:
        return split_codes(self.task_categories)


class FleetUnit(models.Model):
    """A physical robot in the fleet. This is the 'inventory' the staff panel manages."""

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        DEPLOYED = "deployed", "Deployed"
        MAINTENANCE = "maintenance", "Maintenance"
        RETIRED = "retired", "Retired"

    robot_model = models.ForeignKey(RobotModel, on_delete=models.PROTECT, related_name="units")
    serial_number = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    depot = models.CharField(max_length=60, default="Jurong West")
    last_serviced = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["robot_model", "serial_number"]

    def __str__(self):
        return f"{self.robot_model.name} #{self.serial_number}"
