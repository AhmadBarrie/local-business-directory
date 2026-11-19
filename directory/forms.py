from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Business, Review

User = get_user_model()

RATING_CHOICES = [
    (5, "5 - Excellent"),
    (4, "4 - Good"),
    (3, "3 - Average"),
    (2, "2 - Poor"),
    (1, "1 - Terrible"),
]


class BootstrapMixin:
    """Gives every form field Bootstrap styling."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            is_select = isinstance(field.widget, forms.Select)
            field.widget.attrs["class"] = "form-select" if is_select else "form-control"


class RegisterForm(BootstrapMixin, UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class BusinessForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Business
        fields = [
            "name",
            "category",
            "area",
            "address",
            "phone",
            "opening_hours",
            "description",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class ReviewForm(BootstrapMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(choices=RATING_CHOICES, coerce=int)

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 3})}