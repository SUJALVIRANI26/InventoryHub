from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, F, Q
from .models import StockAlert, Product, PurchaseOrder, Supplier, DashboardMetric
import csv
import io
from datetime import datetime, timedelta
import uuid

def generate_supplier_code():
    """Generate a unique supplier code"""
    from .models import Supplier
    last_supplier = Supplier.objects.order_by('-id').first()
    if last_supplier and last_supplier.supplier_code:
        try:
            # Try to extract number from existing code (e.g., SUP-001)
            if '-' in last_supplier.supplier_code:
                last_num = int(last_supplier.supplier_code.split('-')[1])
                return f"SUP-{last_num + 1:03d}"
            else:
                return "SUP-001"
        except (ValueError, IndexError):
            return "SUP-001"
    return "SUP-001"


def generate_po_number():
    """Generate a unique purchase order number"""
    from .models import PurchaseOrder
    year = datetime.now().year
    last_po = PurchaseOrder.objects.filter(
        order_number__startswith=f'PO-{year}'
    ).order_by('-order_number').first()
    
    if last_po and last_po.order_number:
        try:
            # Extract number from PO-YYYY-NNN format
            parts = last_po.order_number.split('-')
            if len(parts) >= 3:
                last_num = int(parts[2])
                return f"PO-{year}-{last_num + 1:03d}"
            else:
                return f"PO-{year}-001"
        except (ValueError, IndexError):
            return f"PO-{year}-001"
    return f"PO-{year}-001"


def generate_transaction_id():
    """Generate a unique stock movement transaction ID"""
    return f"STK-{datetime.now().year}-{uuid.uuid4().hex[:8].upper()}"


def send_stock_alert_notification(alert):
    """Send email notification for stock alerts"""
    if not settings.EMAIL_HOST_USER:
        # Email not configured, just log
        print(f"Stock Alert: {alert.product.name} - {alert.get_alert_type_display()}")
        return
    
    subject = f"Stock Alert: {alert.product.name} - {alert.get_alert_type_display()}"
    
    context = {
        'alert': alert,
        'product': alert.product,
        'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
        'alert_date': timezone.now().strftime('%Y-%m-%d %H:%M'),
    }
    
    try:
        html_message = render_to_string('inventory_manager/emails/stock_alert.html', context)
        plain_message = strip_tags(html_message)
        
        # Get admin emails
        from django.contrib.auth.models import User
        admin_emails = User.objects.filter(
            is_staff=True, 
            is_active=True
        ).exclude(email='').values_list('email', flat=True)
        
        if admin_emails:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL or 'noreply@example.com',
                list(admin_emails),
                html_message=html_message,
                fail_silently=True,
            )
    except Exception as e:
        print(f"Error sending email: {e}")


def generate_product_csv_template():
    """Generate CSV template for product import"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow([
        'product_name', 'sku', 'category', 'brand', 'price',
        'cost_price', 'quantity', 'min_stock_level', 'reorder_point',
        'supplier', 'description'
    ])
    
    # Write sample row
    writer.writerow([
        'Wireless Headphones Pro', 'SKU-001', 'Electronics', 'AudioTech',
        '199.99', '120.50', '45', '10', '15', 'Tech Supplies Inc.',
        'Premium wireless headphones with noise cancellation'
    ])
    
    # Write another sample row
    writer.writerow([
        'Gaming Keyboard', 'SKU-002', 'Electronics', 'GameTech',
        '89.99', '55.00', '30', '5', '8', 'Tech Supplies Inc.',
        'Mechanical gaming keyboard with RGB lighting'
    ])
    
    output.seek(0)
    return output


def generate_stock_adjustment_template():
    """Generate CSV template for stock adjustment"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['SKU', 'Adjustment_Quantity', 'Reason', 'Notes'])
    
    # Write sample rows
    writer.writerow(['SKU-001', '5', 'count', 'Physical count adjustment - found extra units'])
    writer.writerow(['SKU-002', '-2', 'damage', 'Damaged during handling'])
    writer.writerow(['SKU-003', '10', 'return', 'Customer returns processed'])
    
    output.seek(0)
    return output


def check_all_stock_alerts():
    """Check all products and create alerts if needed"""
    alerts_created = []
    
    for product in Product.objects.filter(status='active'):
        # Resolve existing pending alerts
        StockAlert.objects.filter(
            product=product,
            status='pending'
        ).update(status='resolved', resolved_at=timezone.now())
        
        # Create new alerts if needed
        if product.quantity <= 0:
            alert = StockAlert.objects.create(
                product=product,
                alert_type='critical',
                message=f'{product.name} is out of stock!',
                current_stock=product.quantity,
                threshold=product.min_stock_level
            )
            alerts_created.append(alert)
            send_stock_alert_notification(alert)
            
        elif product.quantity <= product.min_stock_level:
            alert = StockAlert.objects.create(
                product=product,
                alert_type='warning',
                message=f'{product.name} is below minimum stock level ({product.min_stock_level}).',
                current_stock=product.quantity,
                threshold=product.min_stock_level
            )
            alerts_created.append(alert)
            if product.quantity == 0:
                send_stock_alert_notification(alert)
            
        elif product.quantity <= product.reorder_point:
            alert = StockAlert.objects.create(
                product=product,
                alert_type='warning',
                message=f'{product.name} is approaching minimum stock level.',
                current_stock=product.quantity,
                threshold=product.reorder_point
            )
            alerts_created.append(alert)
    
    return alerts_created


def get_dashboard_metrics():
    """Calculate and store dashboard metrics"""
    from .models import DashboardMetric, PurchaseOrderItem
    from django.db.models import Sum, F
    from django.utils import timezone
    
    now = timezone.now()
    metrics = []
    
    # Monthly revenue
    revenue = PurchaseOrderItem.objects.filter(
        purchase_order__order_date__month=now.month,
        purchase_order__order_date__year=now.year,
        purchase_order__status='delivered'
    ).aggregate(total=Sum(F('quantity') * F('unit_price')))['total'] or 0
    
    metric, created = DashboardMetric.objects.update_or_create(
        metric_type='revenue',
        date=now.date(),
        defaults={'value': revenue}
    )
    metrics.append(metric)
    
    # Monthly profit
    revenue_total = PurchaseOrderItem.objects.filter(
        purchase_order__order_date__month=now.month,
        purchase_order__order_date__year=now.year,
        purchase_order__status='delivered'
    ).aggregate(total=Sum(F('quantity') * F('unit_price')))['total'] or 0
    
    cost_total = PurchaseOrderItem.objects.filter(
        purchase_order__order_date__month=now.month,
        purchase_order__order_date__year=now.year,
        purchase_order__status='delivered'
    ).aggregate(total=Sum(F('quantity') * F('product__cost_price')))['total'] or 0
    
    profit = revenue_total - cost_total
    
    metric, created = DashboardMetric.objects.update_or_create(
        metric_type='profit',
        date=now.date(),
        defaults={'value': profit}
    )
    metrics.append(metric)
    
    # Monthly orders
    orders_count = PurchaseOrder.objects.filter(
        order_date__month=now.month,
        order_date__year=now.year
    ).count()
    
    metric, created = DashboardMetric.objects.update_or_create(
        metric_type='orders',
        date=now.date(),
        defaults={'value': orders_count}
    )
    metrics.append(metric)
    
    # Stock value
    stock_value = Product.objects.aggregate(
        total=Sum(F('quantity') * F('cost_price'))
    )['total'] or 0
    
    metric, created = DashboardMetric.objects.update_or_create(
        metric_type='stock_value',
        date=now.date(),
        defaults={'value': stock_value}
    )
    metrics.append(metric)
    
    return metrics


def parse_csv_file(csv_file, expected_columns):
    """
    Parse a CSV file and return list of dictionaries
    Raises appropriate exceptions for invalid format
    """
    try:
        csv_file.seek(0)
        reader = csv.DictReader(io.TextIOWrapper(csv_file, encoding='utf-8'))
        
        # Check headers
        headers = reader.fieldnames
        if not headers:
            raise ValueError("CSV file has no headers")
        
        # Check for required columns
        missing_columns = [col for col in expected_columns if col not in headers]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
        
        # Read all rows
        rows = list(reader)
        if not rows:
            raise ValueError("CSV file is empty")
        
        return rows
        
    except Exception as e:
        raise ValueError(f"Error parsing CSV: {str(e)}")


def format_currency(amount):
    """Format amount as currency string"""
    try:
        return f"${amount:,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def calculate_growth_percentage(current, previous):
    """Calculate growth percentage between two values"""
    if previous == 0:
        return 100 if current > 0 else 0
    return ((current - previous) / previous) * 100


def get_date_range_options():
    """Return common date range options for filters"""
    today = timezone.now().date()
    return [
        ('today', 'Today', today),
        ('yesterday', 'Yesterday', today - timedelta(days=1)),
        ('this_week', 'This Week', today - timedelta(days=today.weekday())),
        ('last_week', 'Last Week', today - timedelta(days=today.weekday() + 7)),
        ('this_month', 'This Month', today.replace(day=1)),
        ('last_month', 'Last Month', (today.replace(day=1) - timedelta(days=1)).replace(day=1)),
        ('this_quarter', 'This Quarter', get_quarter_start(today)),
        ('this_year', 'This Year', today.replace(month=1, day=1)),
    ]


def get_quarter_start(date):
    """Get the start date of the quarter for a given date"""
    quarter_months = [1, 4, 7, 10]
    quarter_start_month = quarter_months[(date.month - 1) // 3]
    return date.replace(month=quarter_start_month, day=1)


def send_order_notification(order, notification_type='created'):
    """Send notification for purchase order events"""
    if not settings.EMAIL_HOST_USER:
        return
    
    subject_map = {
        'created': f'New Purchase Order: {order.order_number}',
        'shipped': f'Order Shipped: {order.order_number}',
        'delivered': f'Order Delivered: {order.order_number}',
        'cancelled': f'Order Cancelled: {order.order_number}',
    }
    
    subject = subject_map.get(notification_type, f'Order Update: {order.order_number}')
    
    context = {
        'order': order,
        'notification_type': notification_type,
        'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
    }
    
    try:
        html_message = render_to_string('inventory_manager/emails/order_notification.html', context)
        plain_message = strip_tags(html_message)
        
        # Send to relevant users
        recipients = []
        if order.created_by and order.created_by.email:
            recipients.append(order.created_by.email)
        
        # Add admin emails
        from django.contrib.auth.models import User
        admin_emails = User.objects.filter(
            is_staff=True, 
            is_active=True
        ).exclude(email='').values_list('email', flat=True)
        recipients.extend(admin_emails)
        
        if recipients:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL or 'noreply@example.com',
                list(set(recipients)),  # Remove duplicates
                html_message=html_message,
                fail_silently=True,
            )
    except Exception as e:
        print(f"Error sending order notification: {e}")