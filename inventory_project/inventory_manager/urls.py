from django.urls import path
from . import views

app_name = "inventory_manager"

urlpatterns = [

    path('', views.dashboard, name='dashboard'),

    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_add, name='product_add'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),

    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.supplier_add, name='supplier_add'),
    path('suppliers/<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('suppliers/<int:pk>/edit/', views.supplier_edit, name='supplier_edit'),
    path('suppliers/<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),

    path('purchase/', views.purchase_order_list, name='purchase_order_list'),
    path('purchase/create/', views.purchase_order_create, name='purchase_order_create'),
    path('purchase/<int:pk>/', views.purchase_order_detail, name='purchase_order_detail'),
    path('purchase/<int:pk>/edit/', views.purchase_order_edit, name='purchase_order_edit'),
    path('purchase/<int:pk>/delete/', views.purchase_order_delete, name='purchase_order_delete'),
]
