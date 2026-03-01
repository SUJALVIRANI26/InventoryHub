from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import PurchaseOrder


@receiver(pre_save, sender=PurchaseOrder)
def update_stock_on_status_change(sender, instance, **kwargs):

    # If this is a new object, skip (no previous state)
    if not instance.pk:
        return

    try:
        previous = PurchaseOrder.objects.get(pk=instance.pk)
    except PurchaseOrder.DoesNotExist:
        return

    # If status changed TO delivered
    if previous.status != "delivered" and instance.status == "delivered":

        for item in instance.items.all():
            product = item.product
            product.quantity += item.quantity
            product.save()
