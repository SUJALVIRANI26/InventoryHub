from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .views import (
    DashboardView,
    ProductListView, ProductCreateView, ProductDetailView,
    ProductUpdateView, ProductDeleteView, 
    PurchaseOrderListView, PurchaseOrderCreateView, PurchaseOrderDetailView,
    PurchaseOrderUpdateView, PurchaseOrderDeleteView,
    StockListView, StockUpdateView, StockAdjustmentView,
    StockMovementListView, StockAlertListView,
    SupplierListView, SupplierCreateView, SupplierDetailView, 
    SupplierUpdateView, SupplierHistoryView, SupplierDeleteView
)

app_name = 'inventory_manager'

urlpatterns = [
    # Dashboard
    path('', DashboardView.as_view(), name='dashboard'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    
    # Product URLs
    path('products/', ProductListView.as_view(), name='product_list'),
    path('products/add/', ProductCreateView.as_view(), name='product_add'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('products/<int:pk>/edit/', ProductUpdateView.as_view(), name='product_edit'),
    path('products/<int:pk>/delete/', ProductDeleteView.as_view(), name='product_delete'),
    path('products/export/template/', views.export_product_template, name='export_product_template'),
    
    # Purchase Order URLs
    path('purchases/', PurchaseOrderListView.as_view(), name='purchase_order_list'),
    path('purchases/create/', PurchaseOrderCreateView.as_view(), name='purchase_order_create'),
    path('purchases/<int:pk>/', PurchaseOrderDetailView.as_view(), name='purchase_order_detail'),
    path('purchases/<int:pk>/edit/', PurchaseOrderUpdateView.as_view(), name='purchase_order_edit'),
    path('purchases/<int:pk>/delete/', PurchaseOrderDeleteView.as_view(), name='purchase_order_delete'),
    path('purchases/<int:pk>/update-status/', views.update_order_status, name='update_order_status'),
    
    # Stock URLs
    path('stock/', StockListView.as_view(), name='stock_list'),
    path('stock/update/', StockUpdateView.as_view(), name='stock_update'),
    path('stock/adjustment/', StockAdjustmentView.as_view(), name='stock_adjustment'),
    path('stock/movement/', StockMovementListView.as_view(), name='stock_movement'),
    path('stock/alerts/', StockAlertListView.as_view(), name='stock_alerts'),
    path('stock/export/template/', views.export_adjustment_template, name='export_adjustment_template'),
    path('stock/export/movement/', views.export_stock_movement, name='export_stock_movement'),
    path('stock/save-settings/', views.save_alert_settings, name='save_alert_settings'),
    path('stock/get-product-info/', views.get_product_info, name='get_product_info'),
    
    # Supplier URLs
    path('suppliers/', SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/add/', SupplierCreateView.as_view(), name='supplier_add'),
    path('suppliers/<int:pk>/', SupplierDetailView.as_view(), name='supplier_detail'),
    path('suppliers/<int:pk>/edit/', SupplierUpdateView.as_view(), name='supplier_edit'),
    path('suppliers/<int:pk>/history/', SupplierHistoryView.as_view(), name='supplier_history'),
    path('suppliers/<int:pk>/export/', views.export_supplier_data, name='export_supplier_data'),
    path('suppliers/<int:pk>/delete/', SupplierDeleteView.as_view(), name='supplier_delete'),
    
    # Document URLs
    path('delete-document/<int:pk>/', views.delete_document, name='delete_document'),
    path('upload-document/<int:supplier_id>/', views.upload_document, name='upload_document'),
    
    # AJAX URLs
    path('ajax/get-product-info/', views.get_product_info, name='get_product_info'),
    path('ajax/resolve-alert/<int:pk>/', views.resolve_alert, name='resolve_alert'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)