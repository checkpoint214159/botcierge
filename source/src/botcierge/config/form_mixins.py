from django import forms


class BootstrapFormMixin:
    """Adds Bootstrap 5 classes to every widget so templates can render fields with one include."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(w, forms.Select):
                css = "form-select"
            else:
                css = "form-control"
            w.attrs["class"] = (w.attrs.get("class", "") + " " + css).strip()
