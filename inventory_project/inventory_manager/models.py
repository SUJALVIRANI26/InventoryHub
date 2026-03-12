from django.db import models
from django.utils import timezone
from datetime import timedelta


# ================= CATEGORY =================
class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# ================= SUPPLIER =================
class Supplier(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('limited', 'Limited'),
        ('inactive', 'Inactive'),
    )

    name = models.CharField(max_length=200)
    supplier_code = models.CharField(max_length=50, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    contact_person = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)

    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return self.name


# ================= PRODUCT =================
class Product(models.Model):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)

    quantity = models.IntegerField(default=0)
    minimum_stock = models.IntegerField(default=5)

    def is_low_stock(self):
        return self.quantity < self.minimum_stock

    def _create_low_stock_purchase_order_if_needed(self):
        """
        Automatically create a pending purchase order when this product is low on stock.
        """
        if not self.is_low_stock() or not self.supplier:
            return
        if self.supplier.status != "active":
            return

        # If there's already an ORDERED PO for this product, don't create/update pending ones
        has_ordered_po = PurchaseOrderItem.objects.filter(
            product=self,
            purchase_order__status="ordered",
        ).exists()
        if has_ordered_po:
            return

        # If there's already a PENDING PO item for this product, update it
        pending_item = (
            PurchaseOrderItem.objects.filter(
                product=self,
                purchase_order__status="pending",
            )
            .select_related("purchase_order")
            .order_by("-id")
            .first()
        )

        order_qty = max(self.minimum_stock - self.quantity, 1)

        if pending_item:
            pending_item.quantity = order_qty
            pending_item.unit_price = self.price
            pending_item.save()

            po = pending_item.purchase_order
            if po.supplier_id != self.supplier_id:
                po.supplier = self.supplier
            if not po.expected_delivery:
                po.expected_delivery = timezone.now().date() + timedelta(days=5)
            po.save()
            return

        # Otherwise create a new pending purchase order with 5 days lead time
        po = PurchaseOrder.objects.create(
            supplier=self.supplier,
            status="pending",
            order_date=timezone.now().date(),
            expected_delivery=timezone.now().date() + timedelta(days=5),
        )
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            product=self,
            quantity=order_qty,
            unit_price=self.price,
        )

    def save(self, *args, **kwargs):
        previous_quantity = None
        if self.pk:
            previous_quantity = Product.objects.filter(pk=self.pk).values_list("quantity", flat=True).first()

        super().save(*args, **kwargs)

        # Create automatic low-stock PO only when quantity changes
        if previous_quantity is None or previous_quantity != self.quantity:
            self._create_low_stock_purchase_order_if_needed()

    def __str__(self):
        return self.name


# ================= PURCHASE ORDER =================
class PurchaseOrder(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('ordered', 'Ordered'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    order_date = models.DateField(default=timezone.now)
    expected_delivery = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    @property
    def total_amount(self):
        return sum(item.total_price() for item in self.items.all())

    def __str__(self):
        return f"PO-{self.id}"


# ================= PURCHASE ORDER ITEM =================
class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        related_name="items",
        on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def total_price(self):
        return self.quantity * self.unit_price
