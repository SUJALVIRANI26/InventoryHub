from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Sum, F
from .models import (
    Category, Supplier, Product,
    PurchaseOrder, PurchaseOrderItem, OrderHistory,
    StockMovement, ImportHistory, DashboardMetric, StockAlert
)

# ---------------------------
# Inline Admins
# ---------------------------
class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1
    readonly_fields = ['total_price', 'product_name', 'sku']
    fields = ['product', 'product_name', 'sku', 'quantity', 'unit_price', 'total_price', 'received_quantity', 'status']
    autocomplete_fields = ['product']


class OrderHistoryInline(admin.TabularInline):
    model = OrderHistory
    extra = 0
    readonly_fields = ['action', 'user', 'field_name', 'old_value', 'new_value', 'notes', 'created_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

# ---------------------------
# Model Admins
# ---------------------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'product_count', 'created_at', 'updated_at']
    search_fields = ['name']
    list_filter = ['created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Category Information', {
            'fields': ('name', 'description', 'parent')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'
    product_count.admin_order_field = 'products__count'


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['supplier_code', 'name', 'contact_person', 'email', 'phone', 'status', 'rating_display', 'total_spend']
    list_filter = ['status', 'category', 'is_verified', 'is_preferred', 'country']
    search_fields = ['name', 'supplier_code', 'email', 'contact_person', 'phone']
    readonly_fields = ['supplier_code', 'total_orders', 'total_spend', 'average_rating', 'last_order_date', 'created_at', 'updated_at']
    list_select_related = ['category']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'supplier_code', 'category', 'status', 'is_verified', 'is_preferred')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'contact_title', 'email', 'phone', 'website')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'zip_code', 'country')
        }),
        ('Business Terms', {
            'fields': ('payment_terms', 'credit_limit', 'tax_id', 'preferred_currency', 'min_order_value', 'lead_time_days')
        }),
        ('Performance Metrics', {
            'fields': ('total_orders', 'total_spend', 'average_rating', 'on_time_delivery_rate', 'last_order_date')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def rating_display(self, obj):
        stars = ''
        for i in range(1, 6):
            if i <= obj.average_rating:
                stars += '★'
            else:
                stars += '☆'
        return format_html('<span style="color: #f6c23e;">{}</span> ({})', stars, obj.average_rating)
    rating_display.short_description = 'Rating'

    actions = ['mark_as_verified', 'mark_as_preferred', 'mark_as_inactive']
    
    def mark_as_verified(self, request, queryset):
        queryset.update(is_verified=True)
    mark_as_verified.short_description = "Mark selected suppliers as verified"
    
    def mark_as_preferred(self, request, queryset):
        queryset.update(is_preferred=True)
    mark_as_preferred.short_description = "Mark selected suppliers as preferred"
    
    def mark_as_inactive(self, request, queryset):
        queryset.update(status='inactive')
    mark_as_inactive.short_description = "Mark selected suppliers as inactive"

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['sku', 'name', 'category', 'price', 'quantity', 'stock_status_display', 'status']
    list_filter = ['category', 'status', 'supplier', 'created_at']
    search_fields = ['name', 'sku', 'brand']
    readonly_fields = ['stock_value', 'profit_margin', 'created_at', 'updated_at']
    list_select_related = ['category', 'supplier']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'sku', 'category', 'brand', 'description', 'status')
        }),
        ('Pricing', {
            'fields': ('price', 'cost_price', 'stock_value', 'profit_margin')
        }),
        ('Inventory', {
            'fields': ('quantity', 'min_stock_level', 'reorder_point', 'supplier')
        }),
        ('Rating', {
            'fields': ('rating',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def stock_status_display(self, obj):
        status, color = obj.stock_status_display
        colors = {
            'success': '#1cc88a',
            'warning': '#f6c23e',
            'danger': '#e74a3b',
            'secondary': '#858796'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8rem;">{}</span>',
            colors.get(color, '#858796'),
            status
        )
    stock_status_display.short_description = 'Stock Status'
    
    actions = ['mark_as_active', 'mark_as_inactive', 'update_stock_from_purchases']
    
    def mark_as_active(self, request, queryset):
        queryset.update(status='active')
    mark_as_active.short_description = "Mark selected products as active"
    
    def mark_as_inactive(self, request, queryset):
        queryset.update(status='inactive')
    mark_as_inactive.short_description = "Mark selected products as inactive"
    
    def update_stock_from_purchases(self, request, queryset):
        for product in queryset:
            received_items = PurchaseOrderItem.objects.filter(
                product=product,
                status='received'
            ).aggregate(total=Sum('received_quantity'))['total'] or 0
            
            sold_items = StockMovement.objects.filter(
                product=product,
                movement_type='sale'
            ).aggregate(total=Sum('quantity_change'))['total'] or 0
            
            product.quantity = received_items - abs(sold_items)
            product.save()
        self.message_user(request, f"Updated stock for {queryset.count()} products")
    update_stock_from_purchases.short_description = "Update stock from purchase orders"

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'supplier_link', 'order_date', 'expected_delivery', 'total_amount', 'status_badge', 'item_count']
    list_filter = ['status', 'order_date', 'expected_delivery', 'shipping_method']
    search_fields = ['order_number', 'supplier__name', 'supplier__supplier_code', 'tracking_number']
    readonly_fields = ['order_number', 'subtotal', 'tax_amount', 'total_amount', 'created_at', 'updated_at']
    inlines = [PurchaseOrderItemInline, OrderHistoryInline]
    list_select_related = ['supplier', 'created_by']
    date_hierarchy = 'order_date'
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'supplier', 'status', 'order_date', 'expected_delivery', 'actual_delivery')
        }),
        ('Shipping & Payment', {
            'fields': ('shipping_method', 'payment_terms', 'shipping_cost', 'tax_rate', 'tracking_number')
        }),
        ('Financial Summary', {
            'fields': ('subtotal', 'tax_amount', 'total_amount')
        }),
        ('Notes', {
            'fields': ('notes', 'internal_notes')
        }),
        ('Rating', {
            'fields': ('rating',)
        }),
        ('Audit', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def supplier_link(self, obj):
        return format_html('<a href="/admin/inventory_manager/supplier/{}/change/">{}</a>', obj.supplier.id, obj.supplier.name)
    supplier_link.short_description = 'Supplier'
    supplier_link.admin_order_field = 'supplier__name'
    
    def status_badge(self, obj):
        colors = {
            'draft': '#858796',
            'pending': '#f6c23e',
            'approved': '#4e73df',
            'ordered': '#4e73df',
            'shipped': '#36b9cc',
            'delivered': '#1cc88a',
            'cancelled': '#e74a3b'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8rem;">{}</span>',
            colors.get(obj.status, '#858796'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Items'
    
    actions = ['mark_as_approved', 'mark_as_shipped', 'mark_as_delivered', 'mark_as_cancelled']
    
    def mark_as_approved(self, request, queryset):
        queryset.update(status='approved')
        for po in queryset:
            OrderHistory.objects.create(
                purchase_order=po,
                action='status_changed',
                user=request.user,
                field_name='status',
                old_value='pending',
                new_value='approved',
                notes='Bulk approved via admin'
            )
    mark_as_approved.short_description = "Mark selected orders as approved"
    
    def mark_as_shipped(self, request, queryset):
        queryset.update(status='shipped')
    mark_as_shipped.short_description = "Mark selected orders as shipped"
    
    def mark_as_delivered(self, request, queryset):
        queryset.update(status='delivered', actual_delivery=timezone.now().date())
    mark_as_delivered.short_description = "Mark selected orders as delivered"
    
    def mark_as_cancelled(self, request, queryset):
        queryset.update(status='cancelled')
    mark_as_cancelled.short_description = "Mark selected orders as cancelled"
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ['purchase_order', 'product', 'sku', 'quantity', 'unit_price', 'total_price', 'received_quantity', 'status']
    list_filter = ['status', 'purchase_order__status']
    search_fields = ['purchase_order__order_number', 'product__name', 'sku']
    readonly_fields = ['total_price', 'product_name', 'sku']
    autocomplete_fields = ['product']
    
    actions = ['mark_as_received', 'mark_as_partial']
    
    def mark_as_received(self, request, queryset):
        for item in queryset:
            old_status = item.status
            item.status = 'received'
            item.received_quantity = item.quantity
            item.save()
            
            # Update product quantity
            product = item.product
            old_qty = product.quantity
            product.quantity += item.quantity
            product.save()
            
            # Create stock movement
            StockMovement.objects.create(
                product=product,
                movement_type='purchase',
                quantity_change=item.quantity,
                previous_quantity=old_qty,
                new_quantity=product.quantity,
                reference_number=item.purchase_order.order_number,
                notes=f"Received from PO {item.purchase_order.order_number}",
                created_by=request.user
            )
    mark_as_received.short_description = "Mark selected items as received"
    
    def mark_as_partial(self, request, queryset):
        queryset.update(status='partial')
    mark_as_partial.short_description = "Mark selected items as partially received"


@admin.register(OrderHistory)
class OrderHistoryAdmin(admin.ModelAdmin):
    list_display = ['purchase_order', 'action', 'user', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['purchase_order__order_number', 'notes']
    readonly_fields = ['purchase_order', 'action', 'user', 'field_name', 'old_value', 'new_value', 'notes', 'created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'product_link', 'movement_type', 'quantity_change_display', 'previous_quantity', 'new_quantity', 'created_at']
    list_filter = ['movement_type', 'is_manual', 'created_at', 'adjustment_reason']
    search_fields = ['product__name', 'product__sku', 'reference_number', 'transaction_id', 'notes']
    readonly_fields = ['transaction_id', 'created_at']
    list_select_related = ['product', 'created_by']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('transaction_id', 'product', 'movement_type', 'adjustment_reason')
        }),
        ('Quantity Details', {
            'fields': ('quantity_change', 'previous_quantity', 'new_quantity')
        }),
        ('Reference', {
            'fields': ('reference_number', 'notes', 'is_manual')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def product_link(self, obj):
        return format_html('<a href="/admin/inventory_manager/product/{}/change/">{}</a>', obj.product.id, obj.product.name)
    product_link.short_description = 'Product'
    product_link.admin_order_field = 'product__name'
    
    def quantity_change_display(self, obj):
        color = 'green' if obj.quantity_change > 0 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{}{}</span>', 
                          color, '+' if obj.quantity_change > 0 else '', obj.quantity_change)
    quantity_change_display.short_description = 'Change'


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ['product', 'alert_type_badge', 'current_stock', 'threshold', 'status_badge', 'created_at']
    list_filter = ['alert_type', 'status', 'created_at']
    search_fields = ['product__name', 'product__sku', 'message']
    readonly_fields = ['created_at']
    list_select_related = ['product', 'resolved_by']
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('product', 'alert_type', 'message', 'status')
        }),
        ('Stock Details', {
            'fields': ('current_stock', 'threshold')
        }),
        ('Resolution', {
            'fields': ('resolved_at', 'resolved_by')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def alert_type_badge(self, obj):
        colors = {
            'critical': '#e74a3b',
            'warning': '#f6c23e',
            'info': '#36b9cc'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8rem;">{}</span>',
            colors.get(obj.alert_type, '#858796'),
            obj.get_alert_type_display()
        )
    alert_type_badge.short_description = 'Alert Type'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#f6c23e',
            'resolved': '#1cc88a',
            'ignored': '#858796'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8rem;">{}</span>',
            colors.get(obj.status, '#858796'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    actions = ['mark_as_resolved', 'mark_as_ignored']
    
    def mark_as_resolved(self, request, queryset):
        queryset.update(status='resolved', resolved_at=timezone.now(), resolved_by=request.user)
    mark_as_resolved.short_description = "Mark selected alerts as resolved"
    
    def mark_as_ignored(self, request, queryset):
        queryset.update(status='ignored', resolved_at=timezone.now(), resolved_by=request.user)
    mark_as_ignored.short_description = "Mark selected alerts as ignored"


@admin.register(ImportHistory)
class ImportHistoryAdmin(admin.ModelAdmin):
    list_display = ['import_type', 'file_name', 'records_summary', 'status_badge', 'created_at', 'completed_at']
    list_filter = ['import_type', 'status', 'created_at']
    search_fields = ['file_name']
    readonly_fields = ['created_at', 'completed_at']
    
    fieldsets = (
        ('Import Information', {
            'fields': ('import_type', 'file_name', 'file_size', 'status')
        }),
        ('Records', {
            'fields': ('records_total', 'records_success', 'records_failed')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at', 'created_by')
        }),
        ('Errors', {
            'fields': ('error_log',),
            'classes': ('collapse',)
        }),
    )
    
    def records_summary(self, obj):
        return f"{obj.records_success}/{obj.records_total} successful"
    records_summary.short_description = 'Records'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#f6c23e',
            'processing': '#4e73df',
            'completed': '#1cc88a',
            'failed': '#e74a3b'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8rem;">{}</span>',
            colors.get(obj.status, '#858796'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def has_add_permission(self, request):
        return False


@admin.register(DashboardMetric)
class DashboardMetricAdmin(admin.ModelAdmin):
    list_display = ['metric_type', 'value', 'date', 'category', 'change_percentage']
    list_filter = ['metric_type', 'date', 'category']
    search_fields = ['metric_type', 'category']
    date_hierarchy = 'date'
    readonly_fields = ['month', 'year']
    
    fieldsets = (
        ('Metric Information', {
            'fields': ('metric_type', 'value', 'change_percentage', 'date', 'category')
        }),
        ('Derived Fields', {
            'fields': ('month', 'year'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['metric_type', 'date', 'category']
        return self.readonly_fields