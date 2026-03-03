from django import forms
ROLE_CHOICES = [
    ("MANAGER", "Inventory Manager"),
    ("STAFF", "Staff"),
    ("ADMIN", "Admin"),
    ("OWNER", "Owner"),
   ]

class LoginForm(forms.Form):
    email = forms.EmailField(
        required=True,
    )

    password = forms.CharField(
        required=True,
        min_length=6,
       
    )

    role = forms.ChoiceField(
        required=True,
        choices=ROLE_CHOICES,
       
    )

    remember_me = forms.BooleanField(
        required=False
    )


        
    
    

    

    
