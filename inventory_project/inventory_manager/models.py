from django.db import models
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


# ─────────────────────────────────────────────
# CATEGORY
# ─────────────────────────────────────────────
class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
# SUPPLIER
# ─────────────────────────────────────────────
class Supplier(models.Model):
    STATUS_CHOICES = (
        ('active',   'Active'),
        ('limited',  'Limited'),
        ('inactive', 'Inactive'),
    )

    name           = models.CharField(max_length=200)
    supplier_code  = models.CharField(max_length=50, blank=True, null=True)
    category       = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    contact_person = models.CharField(max_length=150, blank=True)
    email          = models.EmailField(blank=True)
    phone          = models.CharField(max_length=50, blank=True)
    address        = models.TextField(blank=True)
    city           = models.CharField(max_length=100, blank=True)
    state          = models.CharField(max_length=100, blank=True)
    zip_code       = models.CharField(max_length=20, blank=True)
    country        = models.CharField(max_length=100, blank=True)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
# PRODUCT
# Stock never goes negative.
# When a sale deducts more than available, a BacklogEntry is created
# for the shortfall and only available stock is deducted.
# ─────────────────────────────────────────────
class Product(models.Model):
    name          = models.CharField(max_length=200)
    sku           = models.CharField(max_length=100, unique=True)
    category      = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    supplier      = models.ForeignKey(Supplier, on_delete=models.SET_NULL,
                                      null=True, blank=True)
    price         = models.DecimalField(max_digits=10, decimal_places=2)
    quantity      = models.IntegerField(default=0)   # never goes below 0
    minimum_stock = models.IntegerField(default=5)

    # ── helpers ──────────────────────────────────────────────
    def is_low_stock(self):
        return self.quantity < self.minimum_stock

    def _fulfil_open_backlog_from_stock(self):
        """
        Fulfil backlog FIFO from the product's current on-hand stock.

        Source of truth:
        - `SalesOrderItem.backordered_qty`

        Why item-level backlog is primary:
        - the sales UI renders backlog from `SalesOrderItem.backordered_qty`
        - older `BacklogEntry` rows can be stale after historical bugs
        - delivered stock must never be consumed by hidden orphan backlog rows

        Called by `Product.save()` after any stock increase. This means backlog
        is consumed automatically no matter where the stock came from:
        - purchase order delivery
        - manual quantity edits in inventory manager
        - any other backend flow that adds units and saves the product

        After item-level backlog is fulfilled, related `BacklogEntry` rows are
        synced back to match the remaining backlog visible on the order.
        """
        from sales.models import SalesOrder, SalesOrderItem

        available = max(self.quantity, 0)
        if not self.pk or available <= 0:
            return

        affected_order_ids = set()
        backlog_items = (
            SalesOrderItem.objects
            .filter(product=self, backordered_qty__gt=0)
            .select_related('sales_order')
            .order_by('sales_order__order_date', 'sales_order_id', 'id')
        )

        for item in backlog_items:
            if available <= 0:
                break

            fulfilled_units = min(item.backordered_qty, available)
            if fulfilled_units <= 0:
                continue

            affected_order_ids.add(item.sales_order_id)
            available -= fulfilled_units

            new_backordered_qty = max(0, item.backordered_qty - fulfilled_units)
            new_deducted_qty = min(item.quantity, item.deducted_qty + fulfilled_units)

            SalesOrderItem.objects.filter(pk=item.pk).update(
                backordered_qty=new_backordered_qty,
                deducted_qty=new_deducted_qty,
            )

            # Keep backlog rows aligned with the order item so manager/sales
            # pages see the same remaining backlog after stock allocation.
            self._sync_backlog_rows_to_sales_item(item, new_backordered_qty)

        if available != self.quantity:
            Product.objects.filter(pk=self.pk).update(quantity=available)
            self.quantity = available

        # Any stale backlog rows that no longer match a live sales-order item
        # must not keep consuming future delivered stock invisibly.
        self._close_orphan_backlog_rows()

        if affected_order_ids:
            for order in SalesOrder.objects.filter(pk__in=affected_order_ids):
                has_item_backlog = order.items.filter(backordered_qty__gt=0).exists()
                has_backlog_rows = BacklogEntry.objects.filter(
                    sales_order_id=order.pk,
                    quantity_on_backlog__gt=0,
                ).exists()
                if not has_item_backlog and not has_backlog_rows:
                    continue

    def _sync_backlog_rows_to_sales_item(self, item, remaining_backordered_qty):
        """
        Mirror an order item's remaining backlog back onto its BacklogEntry rows.

        Called only from `_fulfil_open_backlog_from_stock()`. Backend stock
        allocation happens in Python here; the sales/inventory templates only
        display the resulting values.
        """
        backlog_rows = (
            BacklogEntry.objects
            .filter(product=self, sales_order_id=item.sales_order_id)
            .order_by('created_at', 'pk')
        )

        remaining = max(remaining_backordered_qty, 0)
        matched_row = False
        for backlog in backlog_rows:
            # Ignore stale rows that point at a different order item for the
            # same product/order combination. They are cleaned up later.
            if backlog.sales_order_item_id not in (0, item.pk):
                continue

            matched_row = True
            row_backlog = min(backlog.quantity_ordered, remaining)
            backlog.quantity_on_backlog = row_backlog
            backlog.sales_order_item_id = item.pk
            remaining -= row_backlog

            if row_backlog <= 0:
                backlog.fulfilled_at = timezone.now()
            else:
                backlog.fulfilled_at = None

            backlog.save(update_fields=['sales_order_item_id', 'quantity_on_backlog', 'fulfilled_at'])

        if not matched_row and remaining_backordered_qty > 0:
            BacklogEntry.objects.create(
                product=self,
                sales_order_item_id=item.pk,
                sales_order_id=item.sales_order_id,
                quantity_ordered=item.quantity,
                quantity_on_backlog=remaining_backordered_qty,
            )

    def _close_orphan_backlog_rows(self):
        """
        Close stale backlog rows that no longer belong to a live open order item.

        This prevents hidden historical rows from consuming delivered stock
        before the visible active order backlog is fulfilled.
        """
        from sales.models import SalesOrderItem

        open_item_ids = set(
            SalesOrderItem.objects
            .filter(product=self, backordered_qty__gt=0)
            .values_list('id', flat=True)
        )

        stale_rows = BacklogEntry.objects.filter(product=self, quantity_on_backlog__gt=0)
        for backlog in stale_rows:
            if backlog.sales_order_item_id in open_item_ids:
                continue

            item = SalesOrderItem.objects.filter(pk=backlog.sales_order_item_id, product=self).first()
            if item is not None and item.backordered_qty > 0:
                continue

            backlog.quantity_on_backlog = 0
            backlog.fulfilled_at = timezone.now()
            backlog.save(update_fields=['quantity_on_backlog', 'fulfilled_at'])

    def _create_low_stock_purchase_order_if_needed(self):
        """
        Create or update a pending PO whenever stock falls below minimum_stock.
        Also called when backlog exists (qty needed = minimum_stock - current qty
        + total open backlog for this product).
        """
        if not self.supplier or self.supplier.status != 'active':
            return

        # Total open backlog units for this product across all sales orders
        open_backlog_qty = BacklogEntry.objects.filter(
            product=self,
            quantity_on_backlog__gt=0,
        ).aggregate(total=models.Sum('quantity_on_backlog'))['total'] or 0

        # Units needed: bring stock to minimum_stock AND cover open backlog
        units_needed = max(self.minimum_stock - self.quantity, 0) + open_backlog_qty
        if units_needed <= 0:
            return

        # Don't create/update pending PO if one is already ordered
        has_ordered_po = PurchaseOrderItem.objects.filter(
            product=self,
            purchase_order__status='ordered',
        ).exists()
        if has_ordered_po:
            return

        # Update existing pending PO item if one exists
        pending_item = (
            PurchaseOrderItem.objects
            .filter(product=self, purchase_order__status='pending')
            .select_related('purchase_order')
            .order_by('-id')
            .first()
        )

        if pending_item:
            pending_item.quantity   = units_needed
            pending_item.unit_price = self.price
            pending_item.save()
            po = pending_item.purchase_order
            if po.supplier_id != self.supplier_id:
                po.supplier = self.supplier
            if not po.expected_delivery:
                po.expected_delivery = timezone.now().date() + timedelta(days=5)
            po.save()
            return

        # Create a brand-new pending PO
        po = PurchaseOrder.objects.create(
            supplier=self.supplier,
            status='pending',
            order_date=timezone.now().date(),
            expected_delivery=timezone.now().date() + timedelta(days=5),
            auto_generated=True,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            product=self,
            quantity=units_needed,
            unit_price=self.price,
        )

    def save(self, *args, **kwargs):
        prev_qty = None
        if self.pk:
            prev_qty = (
                Product.objects
                .filter(pk=self.pk)
                .values_list('quantity', flat=True)
                .first()
            )

        super().save(*args, **kwargs)

        # Any stock increase should first be allocated to the oldest backlog
        # entries. This immediately turns backlog into normal allocated stock
        # and also deducts those fulfilled units from `product.quantity`.
        stock_increased = (prev_qty is None and self.quantity > 0) or (
            prev_qty is not None and self.quantity > prev_qty
        )
        if stock_increased:
            self._fulfil_open_backlog_from_stock()

        # Trigger auto-PO whenever the final quantity changes and stock is
        # still below minimum after backlog fulfilment.
        if prev_qty is None or prev_qty != self.quantity:
            if self.is_low_stock():
                self._create_low_stock_purchase_order_if_needed()

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
# PURCHASE ORDER
# ─────────────────────────────────────────────
class PurchaseOrder(models.Model):
    STATUS_CHOICES = (
        ('pending',   'Pending'),
        ('ordered',   'Ordered'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )

    supplier          = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    order_date        = models.DateField(default=timezone.now)
    expected_delivery = models.DateField(blank=True, null=True)
    status            = models.CharField(max_length=20,
                                         choices=STATUS_CHOICES, default='pending')
    # True when this PO was auto-created due to low/backlog stock
    auto_generated    = models.BooleanField(default=False)

    @property
    def total_amount(self):
        return sum(item.total_price() for item in self.items.all())

    def __str__(self):
        tag = ' [AUTO]' if self.auto_generated else ''
        return f"PO-{self.id}{tag}"


# ─────────────────────────────────────────────
# PURCHASE ORDER ITEM
# ─────────────────────────────────────────────
class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, related_name='items',
                                       on_delete=models.CASCADE)
    product        = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity       = models.IntegerField()
    unit_price     = models.DecimalField(max_digits=10, decimal_places=2)

    def total_price(self):
        return self.quantity * self.unit_price


# ─────────────────────────────────────────────
# BACKLOG ENTRY
# Created by sales/models.py → SalesOrderItem.save() when the
# requested quantity exceeds available stock.
#
# quantity_on_backlog = units still waiting to be fulfilled.
# Automatically reduced when a PO is delivered (inventory_manager/views.py).
# When quantity_on_backlog reaches 0, the sales order's backlog is cleared.
# ─────────────────────────────────────────────
class BacklogEntry(models.Model):
    product             = models.ForeignKey(Product, on_delete=models.CASCADE,
                                            related_name='backlogs')
    # FK to sales.SalesOrderItem (int to avoid circular import)
    sales_order_item_id = models.IntegerField()
    # FK to sales.SalesOrder for easy lookup
    sales_order_id      = models.IntegerField(default=0)
    quantity_ordered    = models.IntegerField()   # original qty customer ordered
    quantity_on_backlog = models.IntegerField()   # units still owed
    created_at          = models.DateTimeField(auto_now_add=True)
    fulfilled_at        = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def is_fulfilled(self):
        return self.quantity_on_backlog <= 0

    def __str__(self):
        return (f"Backlog #{self.pk} – {self.product.name} "
                f"x{self.quantity_on_backlog}")
