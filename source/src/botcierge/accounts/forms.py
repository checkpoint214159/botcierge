from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from config.form_mixins import BootstrapFormMixin

from .models import CustomerProfile


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
