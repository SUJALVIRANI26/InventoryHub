from django import forms
from django.contrib.auth.models import User
from .models import AdminUserProfile

class AdminUserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    contact = forms.CharField()
    role = forms.ChoiceField(choices=AdminUserProfile.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name']

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('confirm_password'):
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data
