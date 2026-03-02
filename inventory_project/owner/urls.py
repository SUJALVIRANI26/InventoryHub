from django.urls import path
from . import views

app_name = 'owner'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('reports/daily/', views.daily_report, name='daily_report'),
    path('reports/weekly/', views.weekly_report, name='weekly_report'),
    path('reports/monthly/', views.monthly_report, name='monthly_report'),
    path('reports/yearly/', views.yearly_report, name='yearly_report'),
    path('reports/profit-loss/', views.profit_loss_report, name='profit_loss_report'),
    path('reports/stock/', views.stock_report, name='stock_report'),
    path('reports/sales/', views.sales_report, name='sales_report'),
    path('reports/purchase/', views.purchase_report, name='purchase_report'),
    path('reports/top-products/', views.top_products_report, name='top_products_report'),
]
