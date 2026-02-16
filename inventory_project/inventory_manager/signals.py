from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Sum, F
from .models import (
    Product, StockMovement, PurchaseOrder, PurchaseOrderItem,
    OrderHistory, StockAlert, Supplier
)

@receiver(post_save, sender=Product)
def product_saved_handler(sender, instance, created, **kwargs):
    """Handle product save events"""
    if created:
        # New product created - create stock movement if quantity > 0
        if instance.quantity > 0:
            StockMovement.objects.create(
                product=instance,
                movement_type='adjustment',
                quantity_change=instance.quantity,
                previous_quantity=0,
                new_quantity=instance.quantity,
                notes='Initial stock setup',
                is_manual=False,
                created_by=instance.created_by
            )
        
        # Check if stock alert needed
        check_product_stock_alerts(instance)
    
    else:
        # Product updated - check if quantity changed
        try:
            old_instance = Product.objects.get(pk=instance.pk)
            if old_instance.quantity != instance.quantity:
                # Quantity changed but no stock movement recorded
                # This can happen if updated directly in admin
                quantity_change = instance.quantity - old_instance.quantity
                if quantity_change != 0:
                    StockMovement.objects.create(
                        product=instance,
                        movement_type='adjustment',
                        quantity_change=quantity_change,
                        previous_quantity=old_instance.quantity,
                        new_quantity=instance.quantity,
                        notes='Manual adjustment via product edit',
                        is_manual=True,
                        created_by=instance.updated_by
                    )
            
            # Check stock alerts regardless
            check_product_stock_alerts(instance)
            
        except Product.DoesNotExist:
            pass


@receiver(pre_save, sender=PurchaseOrder)
def purchase_order_pre_save_handler(sender, instance, **kwargs):
    """Handle purchase order status changes before save"""
    if instance.pk:
        try:
            old_instance = PurchaseOrder.objects.get(pk=instance.pk)
            
            # Check if status changed
            if old_instance.status != instance.status:
                # Create order history for status change
                OrderHistory.objects.create(
                    purchase_order=instance,
                    action='status_changed',
                    user=instance.updated_by if hasattr(instance, 'updated_by') else None,
                    field_name='status',
                    old_value=old_instance.get_status_display(),
                    new_value=instance.get_status_display(),
                    notes=f'Status changed from {old_instance.status} to {instance.status}'
                )
                
                # If delivered, update stock
                if instance.status == 'delivered' and old_instance.status != 'delivered':
                    instance.actual_delivery = timezone.now().date()
                    
                    # We'll update stock in post_save to ensure instance is saved first
                    instance._stock_update_pending = True
                
                # If cancelled, handle any special logic
                elif instance.status == 'cancelled' and old_instance.status != 'cancelled':
                    # Mark all items as cancelled
                    instance.items.update(status='cancelled')
            
            # Check if tracking number added
            if not old_instance.tracking_number and instance.tracking_number:
                OrderHistory.objects.create(
                    purchase_order=instance,
                    action='shipped',
                    user=instance.updated_by if hasattr(instance, 'updated_by') else None,
                    notes=f'Tracking number added: {instance.tracking_number}'
                )
                
        except PurchaseOrder.DoesNotExist:
            pass


@receiver(post_save, sender=PurchaseOrder)
def purchase_order_post_save_handler(sender, instance, created, **kwargs):
    """Handle purchase order post-save events"""
    if created:
        # New purchase order created
        OrderHistory.objects.create(
            purchase_order=instance,
            action='created',
            user=instance.created_by if hasattr(instance, 'created_by') else None,
            notes=f'Purchase order created with status {instance.get_status_display()}'
        )
    
    else:
        # Check if we need to update stock for delivered orders
        if hasattr(instance, '_stock_update_pending') and instance._stock_update_pending:
            for item in instance.items.filter(status='pending'):
                product = item.product
                old_quantity = product.quantity
                product.quantity += item.quantity
                if hasattr(instance, 'updated_by'):
                    product.updated_by = instance.updated_by
                product.save(update_fields=['quantity', 'updated_at', 'updated_by'])
                
                StockMovement.objects.create(
                    product=product,
                    movement_type='purchase',
                    quantity_change=item.quantity,
                    previous_quantity=old_quantity,
                    new_quantity=product.quantity,
                    reference_number=instance.order_number,
                    notes=f"Purchase Order {instance.order_number} delivered",
                    created_by=instance.updated_by if hasattr(instance, 'updated_by') else None
                )
                
                # Update item status
                item.status = 'received'
                item.received_quantity = item.quantity
                item.save(update_fields=['status', 'received_quantity'])
            
            # Update supplier metrics
            update_supplier_metrics(instance.supplier)
            
            # Remove the pending flag
            del instance._stock_update_pending


@receiver(post_save, sender=PurchaseOrderItem)
def purchase_order_item_saved_handler(sender, instance, created, **kwargs):
    """Handle purchase order item save events"""
    if created:
        # Snapshot product details at order time
        instance.product_name = instance.product.name
        instance.sku = instance.product.sku
        instance.save(update_fields=['product_name', 'sku'])
    
    # Update purchase order subtotal
    purchase_order = instance.purchase_order
    subtotal = purchase_order.items.aggregate(
        total=Sum(F('quantity') * F('unit_price'))
    )['total'] or 0
    purchase_order.subtotal = subtotal
    purchase_order.save(update_fields=['subtotal'])


@receiver(post_delete, sender=PurchaseOrderItem)
def purchase_order_item_deleted_handler(sender, instance, **kwargs):
    """Handle purchase order item deletion"""
    # Update purchase order subtotal
    purchase_order = instance.purchase_order
    subtotal = purchase_order.items.aggregate(
        total=Sum(F('quantity') * F('unit_price'))
    )['total'] or 0
    purchase_order.subtotal = subtotal
    purchase_order.save(update_fields=['subtotal'])


@receiver(post_save, sender=Supplier)
def supplier_saved_handler(sender, instance, created, **kwargs):
    """Handle supplier save events"""
    if created:
        # New supplier created
        pass
    else:
        # Supplier updated - check if status changed
        try:
            old_instance = Supplier.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Status changed - could send notification
                pass
        except Supplier.DoesNotExist:
            pass


@receiver(post_save, sender=StockMovement)
def stock_movement_saved_handler(sender, instance, created, **kwargs):
    """Handle stock movement save events"""
    if created:
        # Check if we need to create stock alerts
        check_product_stock_alerts(instance.product)


def check_product_stock_alerts(product):
    """Check product stock levels and create/resolve alerts"""
    # Resolve existing pending alerts for this product
    StockAlert.objects.filter(
        product=product,
        status='pending'
    ).update(status='resolved', resolved_at=timezone.now())
    
    # Create new alerts based on current stock level
    if product.quantity <= 0:
        StockAlert.objects.create(
            product=product,
            alert_type='critical',
            message=f'{product.name} is out of stock!',
            current_stock=product.quantity,
            threshold=product.min_stock_level
        )
    elif product.quantity <= product.min_stock_level:
        StockAlert.objects.create(
            product=product,
            alert_type='warning',
            message=f'{product.name} is below minimum stock level ({product.min_stock_level}).',
            current_stock=product.quantity,
            threshold=product.min_stock_level
        )
    elif product.quantity <= product.reorder_point:
        StockAlert.objects.create(
            product=product,
            alert_type='warning',
            message=f'{product.name} is approaching minimum stock level.',
            current_stock=product.quantity,
            threshold=product.reorder_point
        )


def update_supplier_metrics(supplier):
    """Update supplier performance metrics based on purchase orders"""
    from django.db.models import Avg, Count, Q
    
    # Get all delivered orders for this supplier
    delivered_orders = supplier.purchase_orders.filter(status='delivered')
    
    # Update total orders and spend
    supplier.total_orders = delivered_orders.count()
    supplier.total_spend = delivered_orders.aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    # Calculate on-time delivery rate
    on_time_orders = delivered_orders.filter(
        actual_delivery__lte=F('expected_delivery')
    ).count()
    
    if supplier.total_orders > 0:
        supplier.on_time_delivery_rate = (on_time_orders / supplier.total_orders) * 100
    
    # Calculate average rating
    avg_rating = delivered_orders.exclude(
        rating__isnull=True
    ).aggregate(avg=Avg('rating'))['avg']
    
    if avg_rating:
        supplier.average_rating = avg_rating
    
    # Update last order date
    last_order = delivered_orders.order_by('-order_date').first()
    if last_order:
        supplier.last_order_date = last_order.order_date
    
    supplier.save(update_fields=[
        'total_orders', 'total_spend', 'on_time_delivery_rate',
        'average_rating', 'last_order_date'
    ])


# Connect signals for all models
@receiver(post_save, sender=Product)
def product_stock_alert_check(sender, instance, **kwargs):
    """Check stock alerts whenever product quantity changes"""
    if hasattr(instance, '_quantity_changed') and instance._quantity_changed:
        check_product_stock_alerts(instance)


@receiver(pre_save, sender=Product)
def product_pre_save_check(sender, instance, **kwargs):
    """Check if quantity is changing before save"""
    if instance.pk:
        try:
            old_instance = Product.objects.get(pk=instance.pk)
            instance._quantity_changed = old_instance.quantity != instance.quantity
        except Product.DoesNotExist:
            instance._quantity_changed = False
    else:
        instance._quantity_changed = True