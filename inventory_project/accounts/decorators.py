# admin_panel/decorators.py
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def role_required(allowed_roles = []):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            
            
            # Check if user has a profile and role
            if hasattr(request.user, 'userprofile'):
                user_role = request.user.userprofile.role
                
                # Check if user's role is in allowed roles
                if user_role in allowed_roles :
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, "You don't have permission to access this page.")
                    return redirect('login')
            else:
                messages.error(request, "User profile not found.")
                return redirect('login')
        
        return wrapper
    return decorator

# Specific role decorators for convenience
def admin_required(view_func):
    return role_required(['ADMIN'])(view_func)

def manager_required(view_func):
    return role_required(['MANAGER'])(view_func)

def owner_required(view_func):
    return role_required(['OWNER'])(view_func)

def staff_required(view_func):
    return role_required(['STAFF'])(view_func)