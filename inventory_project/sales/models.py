from datetime import date
from decimal import Decimal
from django.db import models
from inventory_manager.models import Product
from django.db.models import Sum

STATUS_CHOICES = [
    ('active', 'Active'),
    ('inactive', 'Inactive'),
]

CUSTOMER_TYPE_CHOICES = [
    ('individual', 'Individual'),
    ('business', 'Business'),
]

ORDER_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('processing', 'Processing'),
    ('shipped', 'Shipped'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]

PAYMENT_METHOD_CHOICES = [
    ('credit_card', 'Credit Card'),
    ('debit_card', 'Debit Card'),
    ('cash', 'Cash'),
    ('bank_transfer', 'Bank Transfer'),
    ('paypal', 'PayPal'),
    ('check', 'Check'),
]

SHIPPING_CHOICES = [
    ('standard', 'Standard Shipping'),
    ('express', 'Express Shipping'),
    ('pickup', 'Store Pickup'),
]

class Customer(models.Model):
    name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    company = models.CharField(max_length=50, blank=True, null=True)

    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True) 
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)

    customer_since = models.DateField(default=date.today)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='individual')
    tax_id = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
   
    # additional
    total_orders = models.IntegerField(default=0)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    last_order_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ['-customer_since']
    
    def update_stats(self):
        """Update customer statistics based on their orders"""
        from .models import SalesOrder  # Import here to avoid circular import
        
        # Get all completed orders for this customer
        completed_orders = SalesOrder.objects.filter(
            customer=self,
            status='completed'
        )
        
        # Update total orders count (all orders, not just completed)
        self.total_orders = SalesOrder.objects.filter(customer=self).count()
        
        # Update total spent (only from completed orders)
        self.total_spent = completed_orders.aggregate(
            total= Sum('total_amount')
        )['total'] or Decimal('0.00')
        
        # Update last order date
        last_order = SalesOrder.objects.filter(
            customer=self
        ).order_by('-order_date').first()
        
        if last_order:
            self.last_order_date = last_order.order_date
        
        self.save()

    def __str__(self):
        return self.name

class SalesOrder(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    order_date = models.DateField(default=date.today)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, default='credit_card')
    shipping_method = models.CharField(max_length=50, choices=SHIPPING_CHOICES, default='standard')
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)
    
    # Financials
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=8.00) 
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    def __str__(self):
        return f"Order #{self.id} - {self.customer.name}"
    
    def calculate_totals(self):
        # Get all order items
        items = self.items.all()
        
        if items.exists():
            # Calculate subtotal - sum of item totals
            subtotal = Decimal('0')
            for item in items:
                # Assuming each OrderItem has a 'total_price' field
                subtotal += item.total_price if hasattr(item, 'total_price') else Decimal('0')
            
            self.subtotal = subtotal
            
            # Calculate total with tax and shipping
            total = self.subtotal
            
            if self.tax_rate:
                tax_rate = self.tax_rate if isinstance(self.tax_rate, Decimal) else Decimal(str(self.tax_rate))
                total += self.subtotal * (tax_rate / Decimal('100'))
            
            # Add shipping cost
            if self.shipping_cost:
                shipping = self.shipping_cost if isinstance(self.shipping_cost, Decimal) else Decimal(str(self.shipping_cost))
                total += shipping
            
            self.total_amount = total
        else:
            self.subtotal = Decimal('0')
            self.total_amount = self.shipping_cost or Decimal('0')
    
    def save(self, *args, **kwargs):
        if not self.pk:  # save 
            super().save(*args, **kwargs)
        else:
            self.calculate_totals()
            super().save(*args, **kwargs)

    @property
    def tax_amount(self):
        if self.tax_rate and self.subtotal:
            tax_rate = self.tax_rate if isinstance(self.tax_rate, Decimal) else Decimal(str(self.tax_rate))
            return self.subtotal * (tax_rate / Decimal('100'))
        return Decimal('0.00')

class SalesOrderItem(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    def save(self, *args, **kwargs):
        # Ensure price is stored as Decimal even if float is provided
        if not isinstance(self.unit_price, Decimal):
            self.unit_price = Decimal(str(self.unit_price))
        if not isinstance(self.quantity, Decimal):
            self.quantity = Decimal(str(self.quantity))
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    
