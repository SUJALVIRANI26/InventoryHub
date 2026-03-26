from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(allowed_roles):
    """Restrict a view to users whose UserProfile.role is in allowed_roles."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            profile = getattr(request.user, 'userprofile', None)
            if profile and profile.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, "You don't have permission to access this page.")
            return redirect('login')
        return wrapper
    return decorator


# Convenience decorators
admin_required   = role_required(['ADMIN'])
manager_required = role_required(['MANAGER'])
owner_required   = role_required(['OWNER'])
staff_required   = role_required(['ADMIN', 'MANAGER', 'OWNER', 'STAFF'])