from django.urls import path
from . import views

urlpatterns = [
    path('',                 views.login,            name='login'),
    path('logout/',          views.logout_user,       name='logout'),
    path('forgot-password/', views.forgot_password,   name='forgot_password'),
    path('verify-otp/',      views.verify_otp,        name='verify_otp'),
    path('reset-password/',  views.reset_password,    name='reset_password'),
    path('password-changed/',views.password_changed,  name='password_changed'),
]