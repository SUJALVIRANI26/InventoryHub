from django.urls import path
from . import views
urlpatterns = [
    path('',views.dashboard,name= 'dashboard'),
    path('products/',views.products,name = 'products'),
    path('customers/',views.customer,name = 'customers'),
    path('customer_form/',views.customer_form,name = 'customer_form'),
    path('sales_order/',views.sales_order,name = 'sales_order'),
    path('sales_order_form/',views.sales_order_form,name='sales_order_form'),
    path('sales_order_detail/',views.sales_order_detail,name = 'sales_order_detail'),
    path('invoices/',views.invoices,name = 'invoices'),
    path('invoice_print/',views.invoice_print,name = 'invoice_print'),
    path('invoice_form',views.invoice_form,name = 'invoice_form'),
    path('settings/',views.setting,name = 'settings'),
    path('products_form/',views.product_form,name = 'product_form'),
]
