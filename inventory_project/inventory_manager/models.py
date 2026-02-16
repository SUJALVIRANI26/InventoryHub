from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Sum, F
import uuid

# ---------------------------
# Base Abstract Model
# ---------------------------
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="%(class)s_created")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="%(class)s_updated")

    class Meta:
        abstract = True


# ---------------------------
# Category Model
# ---------------------------
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    def product_count(self):
        return self.products.count()


# ---------------------------
# Supplier Model
# ---------------------------
class Supplier(TimeStampedModel):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending Approval'),
        ('limited', 'Limited'),
    ]
    
    PAYMENT_TERMS_CHOICES = [
        ('net30', 'Net 30 Days'),
        ('net45', 'Net 45 Days'),
        ('net60', 'Net 60 Days'),
        ('cod', 'Cash on Delivery'),
        ('advance', 'Advance Payment'),
        ('custom', 'Custom Terms'),
    ]

    CURRENCY_CHOICES = [
        ('USD', 'USD - US Dollar'),
        ('EUR', 'EUR - Euro'),
        ('GBP', 'GBP - British Pound'),
        ('CAD', 'CAD - Canadian Dollar'),
        ('AUD', 'AUD - Australian Dollar'),
    ]

    # Basic Information
    name = models.CharField(max_length=200)
    supplier_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='suppliers')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Contact Information
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_title = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    
    # Address
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True, default='United States')
    
    # Business Terms
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS_CHOICES, default='net30')
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tax_id = models.CharField(max_length=100, blank=True, null=True)
    preferred_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    min_order_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    lead_time_days = models.IntegerField(null=True, blank=True, help_text="Average lead time in days")
    
    # Performance Metrics
    total_orders = models.IntegerField(default=0)
    total_spend = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    on_time_delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    last_order_date = models.DateField(null=True, blank=True)
    
    # Additional
    notes = models.TextField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    is_preferred = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.supplier_code})"

    def save(self, *args, **kwargs):
        if not self.supplier_code:
            last_supplier = Supplier.objects.order_by('-id').first()
            if last_supplier and last_supplier.supplier_code:
                try:
                    last_num = int(last_supplier.supplier_code.split('-')[1])
                    self.supplier_code = f"SUP-{last_num + 1:03d}"
                except:
                    self.supplier_code = "SUP-001"
            else:
                self.supplier_code = "SUP-001"
        super().save(*args, **kwargs)

# ---------------------------
# Product Model
# ---------------------------
class Product(TimeStampedModel):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('draft', 'Draft'),
        ('discontinued', 'Discontinued'),
    ]

    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU (Stock Keeping Unit)")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    brand = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    # Pricing
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    
    # Stock
    quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    min_stock_level = models.IntegerField(default=5, help_text="Minimum stock level before alert")
    reorder_point = models.IntegerField(default=10, help_text="Stock level at which to reorder")
    
    # Supplier
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Rating
    rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        null=True,
        blank=True,
        help_text="Rating from 1-5"
    )
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def stock_value(self):
        return self.quantity * (self.cost_price or 0)

    @property
    def profit_margin(self):
        if self.price and self.cost_price:
            return ((self.price - self.cost_price) / self.price) * 100
        return 0

    @property
    def stock_status(self):
        if self.quantity <= 0:
            return 'out_of_stock'
        elif self.quantity <= self.min_stock_level:
            return 'low_stock'
        elif self.quantity <= self.reorder_point:
            return 'reorder'
        else:
            return 'in_stock'

    @property
    def stock_status_display(self):
        status_map = {
            'out_of_stock': ('Out of Stock', 'danger'),
            'low_stock': ('Low Stock', 'warning'),
            'reorder': ('Reorder', 'warning'),
            'in_stock': ('In Stock', 'success'),
        }
        return status_map.get(self.stock_status, ('Unknown', 'secondary'))

    def get_stock_status_display(self):
        if self.quantity <= 0:
            return 'Out of Stock'
        elif self.quantity <= self.min_stock_level:
            return 'Low Stock'
        else:
            return 'In Stock'

# ---------------------------
# PurchaseOrder Model
# ---------------------------
class PurchaseOrder(TimeStampedModel):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('ordered', 'Ordered'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    SHIPPING_METHOD_CHOICES = [
        ('standard', 'Standard Shipping'),
        ('express', 'Express Shipping'),
        ('priority', 'Priority Shipping'),
        ('pickup', 'Supplier Pickup'),
    ]

    PAYMENT_TERMS_CHOICES = [
        ('net30', 'Net 30 Days'),
        ('net45', 'Net 45 Days'),
        ('net60', 'Net 60 Days'),
        ('cod', 'Cash on Delivery'),
        ('advance', 'Advance Payment'),
    ]

    order_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    
    # Dates
    order_date = models.DateField(default=timezone.now)
    expected_delivery = models.DateField()
    actual_delivery = models.DateField(null=True, blank=True)
    
    # Shipping & Payment
    shipping_method = models.CharField(max_length=20, choices=SHIPPING_METHOD_CHOICES, default='standard')
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS_CHOICES, default='net30')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Financial
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Additional
    notes = models.TextField(blank=True, null=True)
    internal_notes = models.TextField(blank=True, null=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    
    # Rating for supplier performance
    rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        null=True,
        blank=True,
        help_text="Rate this order (1-5)"
    )

    class Meta:
        ordering = ['-order_date', '-created_at']

    def __str__(self):
        return f"{self.order_number} - {self.supplier.name}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            year = timezone.now().year
            last_po = PurchaseOrder.objects.filter(order_number__startswith=f'PO-{year}').order_by('-order_number').first()
            if last_po:
                try:
                    last_num = int(last_po.order_number.split('-')[2])
                    self.order_number = f"PO-{year}-{last_num + 1:03d}"
                except:
                    self.order_number = f"PO-{year}-001"
            else:
                self.order_number = f"PO-{year}-001"
        
        # Calculate subtotal from items if not set
        if hasattr(self, '_items_calculated') and self.pk:
            self.subtotal = self.items.aggregate(total=Sum(F('quantity') * F('unit_price')))['total'] or 0
        
        self.tax_amount = (self.subtotal + self.shipping_cost) * (self.tax_rate / 100)
        self.total_amount = self.subtotal + self.shipping_cost + self.tax_amount
        super().save(*args, **kwargs)


# ---------------------------
# PurchaseOrderItem Model
# ---------------------------
class PurchaseOrderItem(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partially Received'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='purchase_order_items')
    
    # Snapshot of product details at order time
    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50)
    
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    received_quantity = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.purchase_order.order_number} - {self.product_name}"

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        
        # Update purchase order subtotal
        if self.purchase_order:
            self.purchase_order._items_calculated = True
            self.purchase_order.save()


# ---------------------------
# OrderHistory Model
# ---------------------------
class OrderHistory(models.Model):
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('status_changed', 'Status Changed'),
        ('item_added', 'Item Added'),
        ('item_removed', 'Item Removed'),
        ('item_updated', 'Item Updated'),
        ('note_added', 'Note Added'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    field_name = models.CharField(max_length=100, null=True, blank=True)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Order histories"

    def __str__(self):
        return f"{self.purchase_order.order_number} - {self.get_action_display()} - {self.created_at}"


# ---------------------------
# StockMovement Model
# ---------------------------
class StockMovement(TimeStampedModel):
    MOVEMENT_TYPES = [
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('adjustment', 'Adjustment'),
        ('return', 'Return'),
        ('damage', 'Damage'),
        ('theft', 'Theft/Loss'),
        ('transfer', 'Transfer'),
    ]

    ADJUSTMENT_REASONS = [
        ('count', 'Physical Count'),
        ('damage', 'Damaged Goods'),
        ('theft', 'Theft/Loss'),
        ('other', 'Other'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    adjustment_reason = models.CharField(max_length=20, choices=ADJUSTMENT_REASONS, null=True, blank=True)
    
    quantity_change = models.IntegerField(help_text="Positive for stock in, negative for stock out")
    previous_quantity = models.IntegerField()
    new_quantity = models.IntegerField()
    
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    # For audit trail
    is_manual = models.BooleanField(default=False)
    transaction_id = models.CharField(max_length=50, unique=True, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.sku} - {self.get_movement_type_display()} - {self.quantity_change}"

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = f"STK-{timezone.now().year}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


# ---------------------------
# ImportHistory Model
# ---------------------------
class ImportHistory(models.Model):
    IMPORT_TYPES = [
        ('product', 'Product Import'),
        ('stock', 'Stock Adjustment'),
        ('supplier', 'Supplier Import'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    import_type = models.CharField(max_length=20, choices=IMPORT_TYPES)
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="File size in bytes", null=True, blank=True)
    
    records_total = models.IntegerField(default=0)
    records_success = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_log = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Import histories"

    def __str__(self):
        return f"{self.get_import_type_display()} - {self.file_name} - {self.created_at}"


# ---------------------------
# DashboardMetric Model
# ---------------------------
class DashboardMetric(models.Model):
    METRIC_TYPES = [
        ('revenue', 'Revenue'),
        ('profit', 'Profit'),
        ('orders', 'Orders'),
        ('customers', 'Customers'),
        ('stock_value', 'Stock Value'),
        ('purchase_orders', 'Purchase Orders'),
    ]

    metric_type = models.CharField(max_length=50, choices=METRIC_TYPES)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    change_percentage = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    date = models.DateField(default=timezone.now)
    
    # For chart data
    category = models.CharField(max_length=100, null=True, blank=True)
    month = models.IntegerField(null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-date', 'metric_type']
        unique_together = [['metric_type', 'date', 'category']]

    def __str__(self):
        return f"{self.get_metric_type_display()} - {self.date} - {self.value}"

    def save(self, *args, **kwargs):
        if not self.month:
            self.month = self.date.month
        if not self.year:
            self.year = self.date.year
        super().save(*args, **kwargs)


# ---------------------------
# StockAlert Model
# ---------------------------
class StockAlert(models.Model):
    ALERT_TYPES = [
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Information'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.TextField()
    current_stock = models.IntegerField()
    threshold = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alerts')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} - {self.get_alert_type_display()} - {self.status}"