from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from aegis.models import DefaultAuthUserExtend


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = DefaultAuthUserExtend
        fields = ["username", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super(RegisterForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Register'))

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if DefaultAuthUserExtend.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Login'))


class PasswordResetForm(forms.Form):
    email = forms.EmailField()
    new_password1 = forms.CharField(widget=forms.PasswordInput)
    new_password2 = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data

