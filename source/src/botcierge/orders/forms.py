import re

from django import forms

from config.form_mixins import BootstrapFormMixin


class CheckoutForm(BootstrapFormMixin, forms.Form):
    delivery_address = forms.CharField(max_length=255)
    promo_code = forms.CharField(max_length=20, required=False)
    card_name = forms.CharField(max_length=100, label="Name on card")
    card_number = forms.CharField(max_length=19, label="Card number",
                                  help_text="Demo only: no real payment is taken. Use any 16 digits.")

    def clean_card_number(self):
        digits = re.sub(r"[\s-]", "", self.cleaned_data["card_number"])
        if not re.fullmatch(r"\d{16}", digits):
            raise forms.ValidationError("Enter 16 digits.")
        return digits
