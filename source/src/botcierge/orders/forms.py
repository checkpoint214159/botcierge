import json
import re
from datetime import timedelta

from django import forms
from django.utils import timezone

from accounts.models import Address
from catalog.models import AddOn, RobotModel, SkillPack
from config.form_mixins import BootstrapFormMixin
from planner.decomposer import eligible_robots


class BookingForm(BootstrapFormMixin, forms.Form):
    """S08 + S09: the customer adjusts the recommended setup and fills in the booking details."""

    robot = forms.ModelChoiceField(queryset=RobotModel.objects.none(), empty_label=None)
    addons = forms.ModelMultipleChoiceField(
        queryset=AddOn.objects.filter(is_active=True), required=False,
        widget=forms.CheckboxSelectMultiple, label="Attachments")
    skill_pack = forms.ModelChoiceField(
        queryset=SkillPack.objects.filter(is_active=True), required=False, empty_label="No skill pack")
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    address = forms.ModelChoiceField(queryset=Address.objects.none(), required=False,
                                     empty_label="Choose a saved address", label="Deliver to")
    floor_plan = forms.ImageField(required=False, label="Floor plan or photo of the space")
    # filled in by the zone editor on the page as JSON: [{"x":..,"y":..,"w":..,"h":..}, ...]
    keep_out_zones = forms.CharField(required=False, widget=forms.HiddenInput)

    MAX_ZONES = 20

    def __init__(self, *args, task_request, **kwargs):
        super().__init__(*args, **kwargs)
        # only robots and skill packs that suit this task type and meet its payload/stairs/outdoor needs
        self.fields["robot"].queryset = eligible_robots(task_request).order_by("daily_rate")
        category = task_request.spec.task_category
        suited = [p.pk for p in SkillPack.objects.filter(is_active=True) if category in p.category_list]
        self.fields["skill_pack"].queryset = SkillPack.objects.filter(pk__in=suited)
        self.fields["address"].queryset = Address.objects.filter(customer=task_request.customer)
        self.fields["start_date"].widget.attrs["min"] = timezone.localdate().isoformat()

    def clean_start_date(self):
        start = self.cleaned_data["start_date"]
        if start < timezone.localdate():
            raise forms.ValidationError("The start date can't be in the past.")
        return start

    def clean_keep_out_zones(self):
        """Never trust the browser: check the JSON is a short list of rectangles inside the image."""
        raw = self.cleaned_data.get("keep_out_zones") or "[]"
        try:
            zones = json.loads(raw)
        except json.JSONDecodeError:
            raise forms.ValidationError("The keep-out zones couldn't be read. Please redraw them.")
        if not isinstance(zones, list) or len(zones) > self.MAX_ZONES:
            raise forms.ValidationError(f"Draw at most {self.MAX_ZONES} keep-out zones.")
        clean = []
        for z in zones:
            try:
                x, y, w, h = (round(float(z[k]), 4) for k in ("x", "y", "w", "h"))
            except (KeyError, TypeError, ValueError):
                raise forms.ValidationError("The keep-out zones couldn't be read. Please redraw them.")
            if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 - x + 1e-4 and 0 < h <= 1 - y + 1e-4):
                raise forms.ValidationError("A keep-out zone is outside the floor plan. Please redraw it.")
            clean.append({"x": x, "y": y, "w": w, "h": h})
        return clean

    def clean(self):
        data = super().clean()
        robot = data.get("robot")
        if robot:
            bad = [a.name for a in data.get("addons") or [] if not a.fits(robot.platform)]
            if bad:
                self.add_error("addons", f"Not compatible with {robot.name}: {', '.join(bad)}.")
            pack = data.get("skill_pack")
            if pack and not pack.compatible_robots.filter(pk=robot.pk).exists():
                self.add_error("skill_pack", f"{pack.name} doesn't run on {robot.name}.")
        return data


class CheckoutForm(BootstrapFormMixin, forms.Form):
    """S10: mock payment. The address comes from the booking; the promo code from the Apply step."""

    promo_code = forms.CharField(max_length=20, required=False, widget=forms.HiddenInput)
    card_name = forms.CharField(max_length=100, label="Name on card")
    card_number = forms.CharField(max_length=19, label="Card number",
                                  help_text="Demo only: no real payment is taken. Use any 16 digits.")

    def clean_card_number(self):
        digits = re.sub(r"[\s-]", "", self.cleaned_data["card_number"])
        if not re.fullmatch(r"\d{16}", digits):
            raise forms.ValidationError("Enter 16 digits.")
        return digits


class RescheduleForm(BootstrapFormMixin, forms.Form):
    """S18: pick a new start date. The booking keeps its length and price."""

    start_date = forms.DateField(label="New start date", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, order, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order
        self.fields["start_date"].widget.attrs["min"] = self.earliest().isoformat()

    @staticmethod
    def earliest():
        # same rule as cancelling: nothing can be changed on or after the start day
        return timezone.localdate() + timedelta(days=1)

    def clean_start_date(self):
        start = self.cleaned_data["start_date"]
        if start < self.earliest():
            raise forms.ValidationError("Pick a date from tomorrow onwards.")
        if start == self.order.start_date:
            raise forms.ValidationError("That's already your start date.")
        return start
