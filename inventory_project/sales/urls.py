from django.urls import path
from . import views
urlpatterns = [
    path('',views.dashboard,name= 'dashboard'),
    path('products/',views.products,name = 'products'),
    path('customers/',views.customer,name = 'customers'),
    path('sales_order/',views.sales_order,name = 'sales_order'),
    path('invoices/',views.invoices,name = 'invoices'),
    path('settings/',views.setting,name = 'settings'),

]
