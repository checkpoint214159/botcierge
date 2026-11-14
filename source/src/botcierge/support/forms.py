from django import forms

from config.form_mixins import BootstrapFormMixin

from .models import Review, SupportTicket


class SupportTicketForm(BootstrapFormMixin, forms.ModelForm):
    """S14: the customer's side of a ticket. Order, status and priority are set by the view."""

    class Meta:
        model = SupportTicket
        fields = ["category", "subject", "description"]
        labels = {"category": "What is it about?", "subject": "Short summary",
                  "description": "What happened?"}
        widgets = {"description": forms.Textarea(attrs={
            "rows": 6, "placeholder": "When did it start, what did the robot do, and what would you like us to do?"})}

    def __init__(self, *args, submitting=False, **kwargs):
        super().__init__(*args, **kwargs)
        # a draft can be half-written; a submitted ticket needs the details staff will act on
        self.fields["description"].required = submitting


class ReviewForm(BootstrapFormMixin, forms.ModelForm):
    """S13: star rating and an optional comment. Order, robot and skill pack are set by the view."""

    RATINGS = [(5, "★★★★★ Excellent"), (4, "★★★★ Good"), (3, "★★★ OK"), (2, "★★ Poor"), (1, "★ Bad")]

    rating = forms.TypedChoiceField(choices=RATINGS, coerce=int, widget=forms.RadioSelect,
                                    label="How did the job go?")

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        labels = {"comment": "Anything others should know? (optional)"}
        widgets = {"comment": forms.Textarea(attrs={
            "rows": 4, "placeholder": "Did it finish on time? How did it handle your pets, stairs or tight corners?"})}
