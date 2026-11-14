from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from config.form_mixins import BootstrapFormMixin

from planner.pricing import zone_for

from .models import Address, CustomerProfile


class RegisterForm(BootstrapFormMixin, UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField()
    housing_type = forms.ChoiceField(choices=CustomerProfile.HOUSING_CHOICES)
    postal_code = forms.CharField(max_length=6, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "email"]

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            CustomerProfile.objects.create(
                user=user,
                housing_type=self.cleaned_data["housing_type"],
                postal_code=self.cleaned_data.get("postal_code", ""),
            )
        return user


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    """S01b: edit contact and housing details."""

    class Meta:
        model = CustomerProfile
        fields = ["phone", "housing_type", "household_size"]  # addresses have their own page (S19)


class AddressForm(BootstrapFormMixin, forms.ModelForm):
    """S19: add or edit a saved delivery address."""

    class Meta:
        model = Address
        fields = ["label", "line", "unit", "postal_code", "is_default"]
        labels = {"is_default": "Use as my default address"}

    def clean_postal_code(self):
        code = self.cleaned_data["postal_code"].strip()
        if zone_for(code) is None:
            raise forms.ValidationError("That isn't a Singapore postal code we deliver to.")
        return code
