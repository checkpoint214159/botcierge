from django import forms

from config.form_mixins import BootstrapFormMixin

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
