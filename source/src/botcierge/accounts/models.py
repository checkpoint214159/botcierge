from django.conf import settings
from django.core.validators import RegexValidator
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


postal_code_validator = RegexValidator(r"^\d{6}$", "Enter a 6-digit Singapore postal code.")


class Address(models.Model):
    """A saved delivery address (S19). A customer can keep several and pick one per booking.
    Orders copy the address text at checkout, so editing or deleting one never changes past orders."""

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=40, help_text='e.g. "Home" or "Mum\'s place"')
    line = models.CharField("Street / block", max_length=160)
    unit = models.CharField("Unit", max_length=20, blank=True, help_text="e.g. #08-123")
    postal_code = models.CharField(max_length=6, validators=[postal_code_validator])
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "label"]
        verbose_name_plural = "addresses"

    def __str__(self):
        return f"{self.label}: {self.one_line()}"

    def one_line(self) -> str:
        unit = f" {self.unit}" if self.unit else ""
        return f"{self.line}{unit}, Singapore {self.postal_code}"

    def save(self, *args, **kwargs):
        if not Address.objects.filter(customer=self.customer).exclude(pk=self.pk).exists():
            self.is_default = True  # the first address is always the default
        super().save(*args, **kwargs)
        if self.is_default:
            # built after saving: before it, self.pk was None and this query would match this row too
            (Address.objects.filter(customer=self.customer, is_default=True)
             .exclude(pk=self.pk).update(is_default=False))
