from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .models import UserProfile


@login_required
def user_list(request):
    profiles = UserProfile.objects.select_related('user').all()
    return render(request, 'admin_panel/user_list.html', {
        'profiles': profiles
    })


@login_required
def add_user(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        contact = request.POST.get('contact')
        role = request.POST.get('role')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password == confirm_password:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=name
            )

            UserProfile.objects.create(
                user=user,
                contact=contact,
                role=role
            )

            return redirect('user_list')

    return render(request, 'admin_panel/user_add.html')


@login_required
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(UserProfile, user=user)

    if request.method == 'POST':
        user.first_name = request.POST.get('name')
        user.email = request.POST.get('email')
        profile.contact = request.POST.get('contact')
        profile.role = request.POST.get('role')

        user.save()
        profile.save()

        return redirect('user_list')

    return render(request, 'admin_panel/user_edit.html', {
        'user_obj': user,
        'profile': profile
    })


@login_required
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.delete()
    return redirect('user_list')
