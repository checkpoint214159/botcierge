from django import forms
from django.db.models import Q

from config.form_mixins import BootstrapFormMixin

from catalog.models import AddOn, RobotModel

from .models import TaskRequest


class TaskRequestForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaskRequest
        fields = [
            "title", "description", "category_hint",
            "floor_plan", "housing_type", "area_m2", "num_rooms", "floor_type",
            "has_stairs", "is_outdoor", "has_pets", "has_children", "fragile_items", "payload_kg",
            "budget_sgd", "start_date", "deadline_date", "hours_per_day", "quiet_hours", "special_notes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "e.g. Mop and vacuum my 4-room flat before we hand over the keys next Friday. "
                               "We have a cat and some glass shelves."}),
            "special_notes": forms.Textarea(attrs={"rows": 2}),
            "housing_type": forms.Select(choices=[
                ("hdb", "HDB flat"), ("condo", "Condominium"),
                ("landed", "Landed property"), ("shophouse", "Shophouse / small shop")]),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "deadline_date": forms.DateInput(attrs={"type": "date"}),
        }
        # model help_text is written for developers; hide it from customers
        help_texts = {"description": "", "category_hint": "", "payload_kg": "",
                      "floor_plan": "A photo or sketch is fine. Mark rooms you want skipped."}
        labels = {
            "category_hint": "Task type (optional, we'll work it out if blank)",
            "area_m2": "Area (m²)",
            "budget_sgd": "Budget (S$)",
            "payload_kg": "Heaviest item to carry (kg)",
            "deadline_date": "Must be done by",
        }

    def clean(self):
        data = super().clean()
        start, end = data.get("start_date"), data.get("deadline_date")
        if start and end and end < start:
            self.add_error("deadline_date", "Deadline cannot be before the start date.")
        hours = data.get("hours_per_day")
        if hours is not None and not 1 <= hours <= 24:
            self.add_error("hours_per_day", "Hours per day must be between 1 and 24.")
        return data


class SwapForm(BootstrapFormMixin, forms.Form):
    """S08: let the customer change the robot or attachments of a recommendation."""

    robot = forms.ModelChoiceField(queryset=RobotModel.objects.none(), empty_label=None)
    addons = forms.ModelMultipleChoiceField(
        queryset=AddOn.objects.filter(is_active=True), required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, task_request, **kwargs):
        super().__init__(*args, **kwargs)
        # same hard constraints as choose_robot(), so a swap can never break safety rules
        robots = RobotModel.objects.filter(is_active=True, max_payload_kg__gte=task_request.payload_kg)
        if task_request.has_stairs:
            robots = robots.filter(
                Q(can_climb_stairs=True) | Q(platform__in=["wheeled_amr", "mobile_manipulator"]))
        if task_request.is_outdoor:
            robots = robots.filter(outdoor=True)
        self.fields["robot"].queryset = robots

    def clean(self):
        data = super().clean()
        robot, addons = data.get("robot"), data.get("addons") or []
        if robot:
            bad = [a.name for a in addons if not a.fits(robot.platform)]
            if bad:
                self.add_error("addons", f"Not compatible with {robot.name}: {', '.join(bad)}.")
        return data
