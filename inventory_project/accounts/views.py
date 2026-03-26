import random
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings

from .forms import LoginForm, ForgotPasswordForm, OTPForm, ResetPasswordForm


# ─────────────────────────────────────────────
# LOGIN / LOGOUT
# ─────────────────────────────────────────────

def login(request):
    # Flush stale messages so they don't bleed in from previous requests
    list(messages.get_messages(request))

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email    = form.cleaned_data['email']
            password = form.cleaned_data['password']
            role     = form.cleaned_data['role']

            user = authenticate(request, username=email, password=password)

            if user is None:
                form.add_error(None, 'Invalid email or password.')
            elif not hasattr(user, 'userprofile') or user.userprofile.role.upper() != role.upper():
                form.add_error(None, 'Unauthorized: role mismatch.')
            else:
                auth_login(request, user)
                destinations = {
                    'ADMIN':   'admin-panel/users/',
                    'MANAGER': 'inventory_manager/',
                    'OWNER':   'owner/',
                }
                return redirect(destinations.get(role, 'sales/'))
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_user(request):
    logout(request)
    return redirect('login')


# ─────────────────────────────────────────────
# FORGOT PASSWORD – Step 1: collect email & send OTP
# ─────────────────────────────────────────────

def forgot_password(request):
    error = None

    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            if not User.objects.filter(email=email).exists():
                error = 'No account found with that email address.'
            else:
                # Generate & store 6-digit OTP in session
                otp = str(random.randint(100000, 999999))
                request.session['fp_otp']   = otp
                request.session['fp_email'] = email
                request.session['fp_verified'] = False

                # Send OTP email
                send_mail(
                    subject='Smart Inventory – Password Reset OTP',
                    message=(
                        f'Your one-time password (OTP) for resetting your Smart Inventory '
                        f'account is:\n\n{otp}\n\n'
                        f'This code is valid for 10 minutes. Do not share it with anyone.'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                return redirect('verify_otp')
    else:
        form = ForgotPasswordForm()

    return render(request, 'accounts/forgot_password.html', {'error': error})


# ─────────────────────────────────────────────
# FORGOT PASSWORD – Step 2: verify OTP
# ─────────────────────────────────────────────

def verify_otp(request):
    # Guard: must have started the flow
    if not request.session.get('fp_email'):
        return redirect('forgot_password')

    error = None
    email = request.session['fp_email']

    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            entered = form.cleaned_data['otp']
            if entered == request.session.get('fp_otp'):
                request.session['fp_verified'] = True
                return redirect('reset_password')
            else:
                error = 'Incorrect OTP. Please try again.'
    else:
        form = OTPForm()

    return render(request, 'accounts/verify_otp.html', {'email': email, 'error': error})


# ─────────────────────────────────────────────
# FORGOT PASSWORD – Step 3: set new password
# ─────────────────────────────────────────────

def reset_password(request):
    # Guard: OTP must have been verified
    if not request.session.get('fp_verified'):
        return redirect('forgot_password')

    error = None

    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            user = User.objects.get(email=request.session['fp_email'])
            user.set_password(form.cleaned_data['new_password'])
            user.save()

            # Clear all forgot-password session keys
            for key in ('fp_otp', 'fp_email', 'fp_verified'):
                request.session.pop(key, None)

            return redirect('password_changed')
        else:
            error = form.errors.get('__all__', [''])[0]
    else:
        form = ResetPasswordForm()

    return render(request, 'accounts/reset_password.html', {'error': error})


# ─────────────────────────────────────────────
# FORGOT PASSWORD – Success screen
# ─────────────────────────────────────────────

def password_changed(request):
    return render(request, 'accounts/password_changed.html')