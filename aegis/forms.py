# aegis/forms.py

from django import forms
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.utils.translation import gettext_lazy as _

from .models import DefaultAuthUserExtend
from .utils.validators import validate_password


class UserRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={
            "class": "form-floating form-floating-custom mb-3 textinput form-control",
            "placeholder": "First Name (Optional)"
        }),
        label="",
        max_length=150,
        required=False,
    )

    last_name = forms.CharField(
        widget=forms.TextInput(attrs={
            "class": "form-floating form-floating-custom mb-3 textinput form-control",
            "placeholder": "Last Name (Optional)"
        }),
        label="",
        max_length=150,
        required=False,
    )

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            "class": "form-floating form-floating-custom mb-3 textinput form-control",
            "placeholder": "Username (Required)"
        }),
        label="",
        help_text="",
        max_length=150,
        validators=[UnicodeUsernameValidator()],
        error_messages={
            "unique": _("A user with that username already exists."),
        },
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "form-floating form-floating-custom mb-3 emailinput form-control",
            "placeholder": "Email (Required)"
        }),
        label="",
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-floating form-floating-custom mb-3 passwordinput form-control",
            "placeholder": "Password (Required)"
        }),
        validators=[validate_password],
        label="",
        help_text="",
    )

    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-floating form-floating-custom mb-3 passwordinput form-control",
            "placeholder": "Confirm Password (Required)"
        }),
        label="",
        help_text="",
    )

    # service_name = forms.ChoiceField(
    #     widget=forms.Select(attrs={
    #         "class": "form-floating form-floating-custom mb-3 select form-control",
    #     }),
    #     choices=[('', 'Please select service type (Required)')] + DefaultAuthUserExtend.SERVICE_NAME_CHOICES,
    #     label="",
    #     required=True,
    # )

    class Meta:
        model = DefaultAuthUserExtend
        fields = ["first_name", "last_name", "username", "email", "password", "password_confirm"]

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if DefaultAuthUserExtend.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Passwords do not match.")
        return cleaned_data


class UserLoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            "class": "form-floating form-floating-custom mb-3 textinput form-control",
            "placeholder": "Username or Email (Required)"
        }),
        label="",
        help_text="",
        max_length=150,
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-floating form-floating-custom mb-3 passwordinput form-control",
            "placeholder": "Password (Required)"
        }),
        label=""
    )

    # service_name = forms.ChoiceField(
    #     widget=forms.Select(attrs={
    #         "class": "form-floating form-floating-custom mb-3 select form-control",
    #     }),
    #     choices=[('', 'Please select service type (Required)')] + DefaultAuthUserExtend.SERVICE_NAME_CHOICES,
    #     label="",
    #     required=True,
    # )
