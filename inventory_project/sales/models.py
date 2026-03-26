from datetime import date
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.db.models import Sum


# ── Import Product here; BacklogEntry imported inside methods
#    to avoid circular imports at module load time.
from inventory_manager.models import Product


SALES_PRICE_MULTIPLIER = Decimal('1.05')


def get_sales_unit_price(product_price):
    """
    Return the sales-side unit price for an order item.

    This keeps a 5% markup on top of the base product price without mutating
    the product itself. Both backend form validation and model save logic use
    this helper so the price shown in the UI matches the final persisted price.
    """
    return (Decimal(str(product_price)) * SALES_PRICE_MULTIPLIER).quantize(Decimal('0.01'))

STATUS_CHOICES = [
    ('active',   'Active'),
    ('inactive', 'Inactive'),
]

CUSTOMER_TYPE_CHOICES = [
    ('individual', 'Individual'),
    ('business',   'Business'),
]

ORDER_STATUS_CHOICES = [
    ('pending',    'Pending'),
    ('processing', 'Processing'),
    ('shipped',    'Shipped'),
    ('completed',  'Completed'),
    ('cancelled',  'Cancelled'),
]

PAYMENT_METHOD_CHOICES = [
    ('credit_card',   'Credit Card'),
    ('debit_card',    'Debit Card'),
    ('cash',          'Cash'),
    ('bank_transfer', 'Bank Transfer'),
    ('paypal',        'PayPal'),
    ('check',         'Check'),
]

SHIPPING_CHOICES = [
    ('standard', 'Standard Shipping'),
    ('express',  'Express Shipping'),
    ('pickup',   'Store Pickup'),
]


# ─────────────────────────────────────────────
# CUSTOMER
# ─────────────────────────────────────────────
class Customer(models.Model):
    name           = models.CharField(max_length=50)
    email          = models.EmailField(unique=True)
    phone          = models.CharField(max_length=20)
    company        = models.CharField(max_length=50, blank=True, null=True)
    address_line1  = models.CharField(max_length=255, blank=True, null=True)
    address_line2  = models.CharField(max_length=255, blank=True, null=True)
    city           = models.CharField(max_length=100, blank=True, null=True)
    state          = models.CharField(max_length=100, blank=True, null=True)
    zip_code       = models.CharField(max_length=20,  blank=True, null=True)
    country        = models.CharField(max_length=100, blank=True, null=True)
    customer_since = models.DateField(default=date.today)
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                      default='active')
    customer_type  = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES,
                                      default='individual')
    tax_id         = models.CharField(max_length=50, blank=True, null=True)
    notes          = models.TextField(blank=True, null=True)
    total_orders   = models.IntegerField(default=0)
    total_spent    = models.DecimalField(max_digits=10, decimal_places=2,
                                         default=Decimal('0.00'))
    last_order_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ['-customer_since']

    def update_stats(self):
        completed = SalesOrder.objects.filter(customer=self, status='completed')
        self.total_orders   = SalesOrder.objects.filter(customer=self).count()
        self.total_spent    = (
            completed.aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')
        )
        last = (
            SalesOrder.objects.filter(customer=self)
            .order_by('-order_date').first()
        )
        self.last_order_date = last.order_date if last else None
        self.save()

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
# SALES ORDER
# ─────────────────────────────────────────────
class SalesOrder(models.Model):
    customer        = models.ForeignKey(Customer, on_delete=models.CASCADE)
    order_date      = models.DateField(default=date.today)
    payment_method  = models.CharField(max_length=50,
                                        choices=PAYMENT_METHOD_CHOICES,
                                        default='credit_card')
    shipping_method = models.CharField(max_length=50, choices=SHIPPING_CHOICES,
                                        default='standard')
    status          = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES,
                                        default='pending')
    notes           = models.TextField(blank=True, null=True)
    subtotal        = models.DecimalField(max_digits=10, decimal_places=2,
                                          default=Decimal('0.00'))
    tax_rate        = models.DecimalField(max_digits=5,  decimal_places=2,
                                          default=Decimal('8.00'))
    shipping_cost   = models.DecimalField(max_digits=10, decimal_places=2,
                                          default=Decimal('0.00'))
    total_amount    = models.DecimalField(max_digits=10, decimal_places=2,
                                          default=Decimal('0.00'))

    def calculate_totals(self):
        subtotal = sum(
            (item.total_price for item in self.items.all()),
            Decimal('0.00'),
        )
        self.subtotal     = subtotal
        tax               = subtotal * (Decimal(str(self.tax_rate)) / Decimal('100'))
        self.total_amount = subtotal + tax + (self.shipping_cost or Decimal('0'))

    def save(self, *args, **kwargs):
        if self.pk:
            self.calculate_totals()
        super().save(*args, **kwargs)

    @property
    def tax_amount(self):
        return self.subtotal * (Decimal(str(self.tax_rate)) / Decimal('100'))

    def __str__(self):
        return f"Order #{self.id} – {self.customer.name}"


# ─────────────────────────────────────────────
# SALES ORDER ITEM
#
# Stock behaviour (NEVER goes negative):
#   • When saved: deduct min(requested, available) from product.quantity
#     If requested > available → create BacklogEntry for the shortfall
#     AND trigger auto-PO via product.save()
#   • When deleted / order cancelled: return only the
#     actually-deducted units (not the backordered ones) to stock
#   • backordered_qty field records how many units are on backlog
# ─────────────────────────────────────────────
class SalesOrderItem(models.Model):
    sales_order     = models.ForeignKey(SalesOrder, on_delete=models.CASCADE,
                                         related_name='items')
    product         = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity        = models.PositiveIntegerField()
    unit_price      = models.DecimalField(max_digits=10, decimal_places=2)
    total_price     = models.DecimalField(max_digits=10, decimal_places=2,
                                          default=Decimal('0.00'))

    # Units that could NOT be fulfilled from stock (on backlog)
    backordered_qty = models.IntegerField(default=0)
    # Units actually deducted from stock
    deducted_qty    = models.IntegerField(default=0)

    # ── save ─────────────────────────────────────────────────
    def save(self, *args, **kwargs):
        from inventory_manager.models import BacklogEntry

        # Always lock price to the sales price, which is 5% above the product's
        # stored base price. The product record itself is not modified.
        self.unit_price = get_sales_unit_price(self.product.price)
        self.total_price = Decimal(str(self.quantity)) * self.unit_price

        if self.pk:
            # ── Editing an existing item ──────────────────────
            original = SalesOrderItem.objects.get(pk=self.pk)
            old_qty  = original.quantity
            new_qty  = self.quantity

            if original.product_id != self.product_id:
                # Product changed: fully undo old, redo new
                self._return_stock(original.product, original.deducted_qty)
                self._clear_backlog(original.product)
                self.deducted_qty    = 0
                self.backordered_qty = 0
                self._charge_stock(self.product, new_qty)
            else:
                # Same product, quantity changed
                delta = new_qty - old_qty
                if delta > 0:
                    # Need more units
                    self._charge_stock(self.product, delta)
                elif delta < 0:
                    # Returning units
                    self._return_stock(self.product, abs(delta))
        else:
            # ── New item ──────────────────────────────────────
            self.deducted_qty    = 0
            self.backordered_qty = 0
            self._charge_stock(self.product, self.quantity)

        super().save(*args, **kwargs)

        # Update any backlog rows created before this item had a real primary
        # key. New order items can create backlog while `self.pk` is still
        # unset, so those rows are first written with `sales_order_item_id=0`.
        # Once the item is saved we relink them to the real order item id so
        # order-level backlog detection can never miss them.
        if self.backordered_qty > 0 and self.sales_order_id:
            from inventory_manager.models import BacklogEntry
            BacklogEntry.objects.filter(
                sales_order_item_id=0,
                sales_order_id=self.sales_order_id,
                product=self.product,
                quantity_on_backlog__gt=0,
            ).update(
                sales_order_item_id=self.pk,
                sales_order_id=self.sales_order_id,
            )

    # ── delete ────────────────────────────────────────────────
    def delete(self, *args, **kwargs):
        # Return only actually-deducted units (backlogged units were never taken)
        self._return_stock(self.product, self.deducted_qty)
        self._clear_backlog(self.product)
        super().delete(*args, **kwargs)

    # ── internal helpers ──────────────────────────────────────

    def _charge_stock(self, product, qty):
        """
        Deduct up to qty from product.quantity (never below 0).
        Any shortfall creates / updates a BacklogEntry and
        triggers auto-PO via product.save().
        """
        from inventory_manager.models import BacklogEntry

        available    = max(product.quantity, 0)
        can_deduct   = min(qty, available)
        shortfall    = qty - can_deduct         # units that go to backlog

        # Deduct what we can
        if can_deduct > 0:
            product.quantity -= can_deduct
            product.save()                      # may trigger auto-PO if low

        self.deducted_qty    = getattr(self, 'deducted_qty', 0) + can_deduct
        self.backordered_qty = getattr(self, 'backordered_qty', 0) + shortfall

        if shortfall > 0:
            # Create or update backlog entry for this item
            existing = BacklogEntry.objects.filter(
                sales_order_item_id=self.pk or 0,
                product=product,
            ).first()

            if existing:
                existing.quantity_on_backlog += shortfall
                existing.quantity_ordered    += qty
                existing.fulfilled_at         = None
                existing.save()
            else:
                BacklogEntry.objects.create(
                    product=product,
                    sales_order_item_id=self.pk or 0,
                    sales_order_id=self.sales_order_id or 0,
                    quantity_ordered=qty,
                    quantity_on_backlog=shortfall,
                )
            # Trigger auto-PO to cover the backlog
            product.refresh_from_db()
            product._create_low_stock_purchase_order_if_needed()

    def _return_stock(self, product, qty):
        """Add qty back to product.quantity."""
        if qty <= 0:
            return
        product.quantity += qty
        product.save()
        self.deducted_qty = max(0, getattr(self, 'deducted_qty', qty) - qty)

    def _clear_backlog(self, product):
        """Zero out any open backlog entries for this item."""
        from inventory_manager.models import BacklogEntry
        BacklogEntry.objects.filter(
            sales_order_item_id=self.pk,
            product=product,
        ).update(quantity_on_backlog=0, fulfilled_at=timezone.now())
        self.backordered_qty = 0

    def __str__(self):
        return f"{self.quantity} × {self.product.name}"
