from django import forms
from django.contrib.auth.forms import AuthenticationForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Login'))