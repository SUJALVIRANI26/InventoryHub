from django import forms

ROLE_CHOICES = [
    ('MANAGER', 'Inventory Manager'),
    ('STAFF',   'Staff'),
    ('ADMIN',   'Admin'),
    ('OWNER',   'Owner'),
]


class LoginForm(forms.Form):
    email    = forms.EmailField()
    password = forms.CharField(min_length=6)
    role     = forms.ChoiceField(choices=ROLE_CHOICES)


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(label='Registered Email')


class OTPForm(forms.Form):
    otp = forms.CharField(
        label='One-Time Password',
        min_length=6, max_length=6,
        widget=forms.TextInput(attrs={'autocomplete': 'one-time-code'}),
    )


class ResetPasswordForm(forms.Form):
    new_password     = forms.CharField(min_length=6, widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        if data.get('new_password') != data.get('confirm_password'):
            raise forms.ValidationError('Passwords do not match.')
        return data