from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    # path('products/', views.products, name='products'),
    path('customers/', views.customer, name='customers'),
    path('customer_form/', views.customer_form, name='customer_form'),
    path('customer_form/<int:pk>/', views.customer_form, name='customer_edit'),


    path('sales_order/', views.sales_order, name='sales_order'),
    path('sales_order_form/', views.sales_order_form, name='sales_order_form'),
    path('sales_order_form/<int:pk>/', views.sales_order_form, name='sales_order_edit'),
    path('sales_order_detail/<int:pk>/', views.sales_order_detail, name='sales_order_detail'),
    path('order/<int:pk>/status/<str:status>/', views.update_order_status, name='sales_order_update_status'),
    
    path('profile_view/',views.profile_view,name = 'profile'),
    
   
]