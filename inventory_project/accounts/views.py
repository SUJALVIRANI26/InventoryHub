from django.shortcuts import render,redirect
from django.http import HttpResponse
from .forms import LoginForm
from django.contrib.auth import authenticate, login as auth_login, logout
from admin_panel.models import UserProfile
from django.contrib.auth import authenticate, login as auth_login
from django.contrib import messages

from django.contrib.auth.decorators import login_required

def login(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            role = form.cleaned_data["role"]

            # This will now use your EmailBackend automatically
            user = authenticate(request, username=email, password=password)

            if user is not None:
                # return redirect('admin_panel:user_list')
                 # Redirect to admin panel dashboard after successful login
                # IMPORTANT: Check if the user's Profile role matches the form choice
                if hasattr(user, 'userprofile') and user.userprofile.role.lower() == role.lower():
                    auth_login(request, user)
                    
                    # Redirect to admin_panel app -> user_list name
                    if role == 'ADMIN':
                        return redirect('admin-panel/users/')
                    elif role == 'MANAGER':
                        return redirect('inventory_manager/')
                    elif role == 'OWNER':
                        return redirect('owner/')
                    else:
                        return redirect('sales/')
                else:
                    messages.error(request, "Unauthorized: Role mismatch.")
            else:
                messages.error(request, "Invalid email or password.")
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})

@login_required
def logout_user(request):
    logout(request)
    return redirect('login')