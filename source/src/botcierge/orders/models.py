from django.conf import settings
from django.db import models

from catalog.models import AddOn, FleetUnit, RobotModel, SkillPack
from planner.models import Recommendation


class PromoCode(models.Model):
    code = models.CharField(max_length=20, unique=True)
    percent_off = models.PositiveSmallIntegerField()
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} (-{self.percent_off}%)"


class Order(models.Model):
    """A confirmed rental booking. Status moves forward through the deployment lifecycle."""

    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        CONFIRMED = "confirmed", "Confirmed"
        DISPATCHED = "dispatched", "Dispatched"
        ON_SITE = "on_site", "On site, mapping"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        COLLECTED = "collected", "Robot collected"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    recommendation = models.ForeignKey(Recommendation, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)
    start_date = models.DateField()
    end_date = models.DateField()
    delivery_address = models.CharField(max_length=255)
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True)
    subtotal = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Review(models.TextChoices):
        """A08: staff check every paid order's plan before the robot is dispatched."""
        PENDING = "pending", "To review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Needs follow-up"

    review_status = models.CharField(max_length=20, choices=Review.choices, default=Review.PENDING)
    review_note = models.TextField(blank=True, help_text="Staff only. Why it needs follow-up, or what was changed.")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="reviewed_orders")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk}"


class OrderItem(models.Model):
    """One line on an order. Exactly one of robot_model / addon / skill_pack is set."""

    class Kind(models.TextChoices):
        ROBOT = "robot", "Robot rental"
        ADDON = "addon", "Add-on"
        SKILL_PACK = "skill_pack", "Skill pack"
        SERVICE = "service", "Delivery & setup"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    robot_model = models.ForeignKey(RobotModel, on_delete=models.PROTECT, null=True, blank=True)
    fleet_unit = models.ForeignKey(FleetUnit, on_delete=models.SET_NULL, null=True, blank=True,
                                   help_text="Assigned by staff before dispatch")
    addon = models.ForeignKey(AddOn, on_delete=models.PROTECT, null=True, blank=True)
    skill_pack = models.ForeignKey(SkillPack, on_delete=models.PROTECT, null=True, blank=True)
    description = models.CharField(max_length=160)
    quantity = models.PositiveSmallIntegerField(default=1, help_text="Days for rentals")
    unit_price = models.DecimalField(max_digits=9, decimal_places=2)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return self.description


class OrderStatusEvent(models.Model):
    """Timeline entry shown on the customer's order tracking page."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Payment(models.Model):
    """Mock payment record. No real gateway is called."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    method = models.CharField(max_length=20, default="card")
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reference = models.CharField(max_length=40, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
