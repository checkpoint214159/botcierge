from django import forms


class BootstrapFormMixin:
    """Adds Bootstrap 5 classes to every widget so templates can render fields with one include."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            # checkbox/radio lists (CheckboxSelectMultiple, RadioSelect) are not Select subclasses,
            # so without this they fell through to "form-control" and rendered as text-box bars
            if isinstance(w, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
                css = "form-check-input"
            elif isinstance(w, forms.Select):
                css = "form-select"
            else:
                css = "form-control"
            w.attrs["class"] = (w.attrs.get("class", "") + " " + css).strip()
