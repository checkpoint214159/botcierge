"""Staff catalogue forms (A03 robots, A04 fleet units, A05 add-ons and skill packs)."""
import json

from django import forms
from django.utils import timezone
from django.utils.text import slugify

from catalog.models import AddOn, FleetUnit, RobotModel, SkillPack
from catalog.taxonomy import PLATFORM_CHOICES, TASK_CATEGORY_CHOICES
from config.form_mixins import BootstrapFormMixin
from orders.forms import check_setup, skill_packs_for
from orders.models import OrderItem
from planner.decomposer import eligible_robots
from support.models import SupportTicket
from orders.services import ONGOING  # orders that still hold their robot (until it's collected)


def chips(placeholder):
    """A plain multi-select that static/js/chip_select.js turns into removable chips with a search box.
    Without JavaScript it still works as a normal multi-select."""
    return forms.SelectMultiple(attrs={"data-chips": placeholder})


class RobotChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, robot):
        # platform in the label so staff can search by it ("mobile manip...")
        hidden = "" if robot.is_active else ", unlisted"
        return f"{robot.name} ({robot.get_platform_display()}{hidden})"


class CodeLockMixin:
    """Codes are what past recommendations and the ML models refer to, so they can't change
    after creation. On an edit form the field is shown but disabled (Django then ignores posted values)."""

    def lock_code(self):
        if self.instance.pk:
            self.fields["code"].disabled = True
            self.fields["code"].help_text = "Fixed once created: past bookings and the ML models use it."


class RobotModelForm(BootstrapFormMixin, forms.ModelForm):
    """A03. task_categories is stored comma-separated; staff pick chips."""

    categories = forms.MultipleChoiceField(
        choices=TASK_CATEGORY_CHOICES, required=False, widget=chips("Add a task type…"),
        label="Task types it can be booked for",
        help_text="Customers can pick it for these jobs. The recommender only suggests the platforms it "
                  "was trained on for each job, so new pairings are offered but not suggested until retrained.")

    class Meta:
        model = RobotModel
        fields = ["name", "slug", "manufacturer", "platform", "tagline", "description", "daily_rate",
                  "indoor", "outdoor", "can_climb_stairs", "max_payload_kg", "battery_hours", "noise_db",
                  "image", "image_credit", "image_credit_url", "is_active"]
        labels = {"daily_rate": "Daily rate (S$)", "max_payload_kg": "Max payload (kg)",
                  "noise_db": "Noise (dB)", "is_active": "Listed in the catalogue"}
        help_texts = {"slug": "Used in the robot's web address. Leave blank to make one from the name.",
                      "platform": "Decides which task types and attachments the robot is offered for."}
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["categories"].initial = self.instance.category_list
        self.order_fields(["name", "slug", "manufacturer", "platform", "categories"])

    def clean_slug(self):
        slug = self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("name", ""))
        if RobotModel.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another robot already uses this web address.")
        return slug

    def clean(self):
        data = super().clean()
        if data.get("indoor") is False and data.get("outdoor") is False:
            raise forms.ValidationError("A robot has to work indoors, outdoors or both.")
        if data.get("is_active") and not data.get("categories"):
            self.add_error("categories", "Pick at least one task type, or customers can never book it.")
        return data

    def save(self, commit=True):
        self.instance.task_categories = ",".join(self.cleaned_data["categories"])
        return super().save(commit)


class FleetUnitForm(BootstrapFormMixin, forms.ModelForm):
    """A04. Reserved and deployed are set by the order flow (checkout, A07), not by hand."""

    MANUAL = [FleetUnit.Status.AVAILABLE, FleetUnit.Status.MAINTENANCE, FleetUnit.Status.RETIRED]

    class Meta:
        model = FleetUnit
        fields = ["robot_model", "serial_number", "status", "depot", "last_serviced", "notes"]
        labels = {"robot_model": "Robot"}
        widgets = {"last_serviced": forms.DateInput(attrs={"type": "date"}),
                   "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # a physical unit doesn't turn into another model
            self.fields["robot_model"].disabled = True
        if self.instance.pk and self.instance.status not in self.MANUAL:
            self.fields["status"].disabled = True
            self.fields["status"].help_text = "Set by its order. It changes back when the robot is collected."
        else:
            self.fields["status"].choices = [(s.value, s.label) for s in self.MANUAL]

    def clean_last_serviced(self):
        d = self.cleaned_data.get("last_serviced")
        if d and d > timezone.localdate():
            raise forms.ValidationError("The service date can't be in the future.")
        return d

    def clean_status(self):
        status = self.cleaned_data["status"]
        if self.instance.pk and status in (FleetUnit.Status.MAINTENANCE, FleetUnit.Status.RETIRED):
            booked = (OrderItem.objects.filter(fleet_unit=self.instance, order__status__in=ONGOING)
                      .values_list("order_id", flat=True))
            if booked:
                nums = ", ".join(f"#{n}" for n in booked)
                raise forms.ValidationError(f"This unit is booked for order {nums}. "
                                            "Assign another unit to the order first.")
        return status


class AddOnForm(CodeLockMixin, BootstrapFormMixin, forms.ModelForm):
    """A05. compatible_platforms is stored comma-separated; staff tick boxes instead."""

    platforms = forms.MultipleChoiceField(
        choices=PLATFORM_CHOICES, required=False, widget=chips("Add a platform…"),
        label="Fits these platforms", help_text="Leave empty if it fits every platform.")

    class Meta:
        model = AddOn
        fields = ["code", "name", "description", "daily_rate", "is_active"]
        labels = {"daily_rate": "Daily rate (S$)", "is_active": "Offered to customers"}
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock_code()
        self.fields["platforms"].initial = self.instance.platform_list

    def save(self, commit=True):
        self.instance.compatible_platforms = ",".join(self.cleaned_data["platforms"])
        return super().save(commit)


class SkillPackForm(CodeLockMixin, BootstrapFormMixin, forms.ModelForm):
    """A05: what the pack is for (task types), what runs it (robots) and its default settings."""

    categories = forms.MultipleChoiceField(
        choices=TASK_CATEGORY_CHOICES, required=False, widget=chips("Add a task type…"),
        label="Offered for these task types")
    compatible_robots = RobotChoiceField(
        queryset=RobotModel.objects.order_by("platform", "name"), required=False,
        widget=chips("Add a robot…"), label="Robots that can run it")
    conditioning = forms.CharField(
        required=False, label="Default settings (JSON)",
        widget=forms.Textarea(attrs={"rows": 6, "class": "font-monospace"}),
        help_text='Starting values for the robot\'s config, e.g. {"passes": 2, "edge_mode": true}. '
                  "The planner adds each job's details on top.")

    class Meta:
        model = SkillPack
        fields = ["code", "name", "version", "summary", "description", "flat_fee", "compatible_robots", "is_active"]
        labels = {"flat_fee": "Flat fee (S$)", "summary": "Customer-facing summary",
                  "is_active": "Offered to customers"}
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock_code()
        self.fields["categories"].initial = self.instance.category_list
        self.fields["conditioning"].initial = json.dumps(self.instance.default_conditioning or {}, indent=2)

    def clean_conditioning(self):
        raw = (self.cleaned_data.get("conditioning") or "").strip() or "{}"
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f"That isn't valid JSON ({e.msg}, line {e.lineno}).")
        if not isinstance(value, dict):
            raise forms.ValidationError('Use an object with named settings, e.g. {"passes": 2}.')
        return value

    def clean(self):
        data = super().clean()
        if data.get("is_active") and not data.get("categories"):
            self.add_error("categories", "Pick at least one task type, or the pack is never offered.")
        return data

    def save(self, commit=True):
        self.instance.task_categories = ",".join(self.cleaned_data["categories"])
        self.instance.default_conditioning = self.cleaned_data["conditioning"]
        return super().save(commit)


class SetupOverrideForm(BootstrapFormMixin, forms.Form):
    """A08: staff change the robot, attachments or skill pack of a paid order before dispatch.
    Same choices and compatibility rules as the customer's booking page."""

    robot = forms.ModelChoiceField(queryset=RobotModel.objects.none(), empty_label=None)
    addons = forms.ModelMultipleChoiceField(queryset=AddOn.objects.filter(is_active=True), required=False,
                                            widget=chips("Add an attachment…"), label="Attachments")
    skill_pack = forms.ModelChoiceField(queryset=SkillPack.objects.none(), required=False, empty_label="No skill pack")

    def __init__(self, *args, task_request, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["robot"].queryset = eligible_robots(task_request).order_by("daily_rate")
        self.fields["skill_pack"].queryset = skill_packs_for(task_request.spec.task_category)

    def clean(self):
        return check_setup(self, super().clean())


# ---------------------------------------------------------------- A09 support tickets

class TicketReplyForm(BootstrapFormMixin, forms.Form):
    """Staff reply. Like the customer's ticket form, a draft may be empty or half-written;
    the text is only required when it is actually sent."""

    body = forms.CharField(label="Reply to the customer", required=False, widget=forms.Textarea(attrs={
        "rows": 6, "placeholder": "What we found, what we'll do, and by when."}))

    def __init__(self, *args, sending=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].required = sending


class TicketStatusForm(BootstrapFormMixin, forms.ModelForm):
    """Staff can move a ticket between states or change its priority. Never back to draft."""

    class Meta:
        model = SupportTicket
        fields = ["status", "priority"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [c for c in self.fields["status"].choices if c[0] != "draft"]
