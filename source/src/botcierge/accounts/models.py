from django.conf import settings
from django.db import models


class CustomerProfile(models.Model):
    """Extra details for a storefront customer. Staff accounts use User.is_staff and have no profile."""

    HOUSING_CHOICES = [
        ("hdb", "HDB flat"),
        ("condo", "Condominium"),
        ("landed", "Landed property"),
        ("shophouse", "Shophouse / small shop"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    postal_code = models.CharField(max_length=6, blank=True)
    housing_type = models.CharField(max_length=20, choices=HOUSING_CHOICES, default="hdb")
    household_size = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_housing_type_display()})"
