from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from catalog.models import RobotModel, SkillPack
from orders.models import Order


class Review(models.Model):
    """Customer rating of a completed job. One review per order."""

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="review")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    robot_model = models.ForeignKey(RobotModel, on_delete=models.CASCADE, related_name="reviews")
    skill_pack = models.ForeignKey(SkillPack, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    is_visible = models.BooleanField(default=True, help_text="Staff can hide abusive reviews")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class SupportTicket(models.Model):
    """S14: one ticket per order. The customer can save it as a draft and edit it until they
    submit; after that it is read-only for them (changes go by email) and staff take over (A09)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft (not sent)"
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        URGENT = "urgent", "Urgent (robot on site)"

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets")
    class Category(models.TextChoices):
        ROBOT = "robot", "The robot isn't working properly"
        SAFETY = "safety", "Damage or a safety concern"
        SCHEDULE = "schedule", "Delivery, timing or collection"
        BILLING = "billing", "Billing or refund"
        OTHER = "other", "Something else"

    subject = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    description = models.TextField(blank=True, help_text="What happened, in the customer's words")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    # A09: staff can save a reply before sending it, the same way customers save a ticket as a draft.
    # It lives on the ticket, not as a TicketMessage, so the customer's page can never show it.
    reply_draft = models.TextField(blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.subject

    @property
    def is_draft(self) -> bool:
        return self.status == self.Status.DRAFT


class TicketMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
