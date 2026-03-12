from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.contrib import messages
from django.db.models import Sum, F,Q,Count,Max  # Add F here
from django.db.models.functions import TruncDate
from django.utils.timezone import now, timedelta
from datetime import datetime, timedelta
from decimal import Decimal
from .forms import OrderItemFormSet, SalesOrderForm, CustomerForm
from .models import SalesOrder, Customer, SalesOrderItem
from django.contrib.auth.decorators import login_required
from admin_panel.models import UserProfile
from accounts.decorators import staff_required
import json
from django.core.serializers.json import DjangoJSONEncoder
from .models import ORDER_STATUS_CHOICES
from django.http import JsonResponse
from inventory_manager.models import Product


def _apply_status_and_stock(order, new_status, old_status=None):
    """
    Central place to handle simple stock behaviour
    when an order's status changes.

    Rules:
    - Stock is reserved immediately when order items are created/updated.
    - When an order is cancelled, reserved stock is returned to inventory.
    - Other status changes do not touch inventory.
    """
    if old_status is None:
        old_status = order.status

    if old_status == new_status:
        return True, "Order status unchanged."

    # If order is being cancelled, return all reserved stock.
    if new_status == 'cancelled' and old_status != 'cancelled':
        for item in order.items.select_related('product'):
            product = item.product
            product.quantity += item.quantity
            product.save()
        order.status = 'cancelled'
        order.save()
        return True, "Order cancelled and stock restored."

    # All other transitions simply update the status without touching stock.
    order.status = new_status
    order.save()
    return True, "Order status updated."


@login_required
@staff_required
def dashboard(request):
    # Get date filters from request
    period = request.GET.get('period', '7')
    
    # Calculate date ranges
    today = timezone.now().date()
    
    if period == '30':
        start_date = today - timedelta(days=30)
    elif period == '90':
        start_date = today - timedelta(days=90)
    else:  # 7 days default
        start_date = today - timedelta(days=7)
    
    # 1. STAT CARDS DATA
    # Total Revenue (all time from completed orders)
    total_revenue = SalesOrder.objects.filter(
        status='completed'
    ).aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    # Revenue growth (compare current period with previous period)
    if period == '7':
        prev_start_date = start_date - timedelta(days=7)
    elif period == '30':
        prev_start_date = start_date - timedelta(days=30)
    else:
        prev_start_date = start_date - timedelta(days=90)
    
    current_period_revenue = SalesOrder.objects.filter(
        status='completed',
        order_date__gte=start_date
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    previous_period_revenue = SalesOrder.objects.filter(
        status='completed',
        order_date__gte=prev_start_date,
        order_date__lt=start_date
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    revenue_growth = 0
    if previous_period_revenue > 0:
        revenue_growth = round(((current_period_revenue - previous_period_revenue) / previous_period_revenue) * 100)
    
    # Orders Today
    orders_today = SalesOrder.objects.filter(
        order_date=today
    ).count()
    
    # Orders growth
    yesterday = today - timedelta(days=1)
    orders_yesterday = SalesOrder.objects.filter(order_date=yesterday).count()
    
    orders_growth = 0
    if orders_yesterday > 0:
        orders_growth = round(((orders_today - orders_yesterday) / orders_yesterday) * 100)
    
    # Total Customers
    total_customers = Customer.objects.filter(status='active').count()
    
    # Customer growth
    last_month = today - timedelta(days=30)
    new_customers = Customer.objects.filter(customer_since__gte=last_month).count()
    customer_growth = round((new_customers / total_customers) * 100) if total_customers > 0 else 0
    
    # Products in Stock (using inventory_manager Product model)
    products_in_stock = Product.objects.filter(
        quantity__gt=0  # Using 'quantity' field from inventory_manager
    ).count()
    
    # Low stock items (using minimum_stock from inventory_manager)
    low_stock_items = Product.objects.filter(
        quantity__lte=F('minimum_stock'),
        quantity__gt=0
    ).count()
    
    # 2. SALES CHART DATA
    sales_orders = SalesOrder.objects.filter(
        status='completed',
        order_date__gte=start_date
    ).annotate(
        date=TruncDate('order_date')
    ).values('date').annotate(
        total=Sum('total_amount')
    ).order_by('date')
    
    # Create date range for missing dates
    date_range = []
    current_date = start_date
    while current_date <= today:
        date_range.append(current_date)
        current_date += timedelta(days=1)
    
    # Map sales data to dates
    sales_dict = {item['date']: float(item['total']) for item in sales_orders if item['date']}
    
    sales_chart_labels = []
    sales_chart_data = []
    
    for date in date_range:
        if period == '7':
            sales_chart_labels.append(date.strftime('%a'))
        else:
            sales_chart_labels.append(date.strftime('%b %d'))
        sales_chart_data.append(sales_dict.get(date, 0))
    
    # 3. PRODUCT CHART DATA (Top products by quantity sold from sales orders)
    top_products = SalesOrderItem.objects.filter(
        sales_order__status='completed',
        sales_order__order_date__gte=start_date
    ).values(
        'product__name'  # Product name from inventory_manager
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum(F('quantity') * F('unit_price'))
    ).order_by('-total_quantity')[:4]
    
    product_labels = [item['product__name'] for item in top_products]
    product_data = [float(item['total_quantity']) for item in top_products]
    
    # If no data, use products from inventory_manager as fallback
    if not product_labels:
        # Get top products by stock quantity as placeholder
        top_stocked_products = Product.objects.order_by('-quantity')[:4]
        product_labels = [p.name for p in top_stocked_products]
        product_data = [float(p.quantity) for p in top_stocked_products]
    
    # 4. RECENT ORDERS
    recent_orders = SalesOrder.objects.select_related('customer').order_by('-order_date', '-id')[:5]
    
    # 5. QUICK STATS
    pending_orders = SalesOrder.objects.filter(
        status__in=['pending', 'processing']
    ).count()
    
    completed_today = SalesOrder.objects.filter(
        status='completed',
        order_date=today
    ).count()
    
    # Get products that are out of stock from inventory_manager
    out_of_stock = Product.objects.filter(quantity=0).count()
    
    # Get critical stock items (below minimum_stock)
    critical_stock = Product.objects.filter(
        quantity__lte=F('minimum_stock') * 0.5,
        quantity__gt=0
    ).count()
    
    # 6. RECENT ACTIVITIES
    recent_activities = []
    
    # Recent orders
    recent_order_activities = SalesOrder.objects.select_related('customer').order_by('-order_date', '-id')[:3]
    for order in recent_order_activities:
        recent_activities.append({
            'type': 'order',
            'description': f"New order #{order.id} from {order.customer.name}",
            'time_ago': get_time_ago(order.order_date),
            'icon': 'fa-solid fa-cart-plus',
            'color': '#4e73df'
        })
    
    # Low stock alerts from inventory_manager
    low_stock_products = Product.objects.filter(
        quantity__lte=F('minimum_stock'),
        quantity__gt=0
    )[:3]
    for product in low_stock_products:
        recent_activities.append({
            'type': 'stock',
            'description': f"Low stock: {product.name} ({product.quantity} left, min: {product.minimum_stock})",
            'time_ago': 'Urgent',
            'icon': 'fa-solid fa-exclamation-triangle',
            'color': '#e74a3b'
        })
    
    # New customers
    new_customers = Customer.objects.order_by('-customer_since')[:2]
    for customer in new_customers:
        recent_activities.append({
            'type': 'customer',
            'description': f"New customer registered: {customer.name}",
            'time_ago': get_time_ago(customer.customer_since),
            'icon': 'fa-solid fa-user-plus',
            'color': '#1cc88a'
        })
    
    context = {
        # Stat cards
        'total_revenue': total_revenue,
        'revenue_growth': revenue_growth,
        'orders_today': orders_today,
        'orders_growth': orders_growth,
        'total_customers': total_customers,
        'customer_growth': customer_growth,
        'products_in_stock': products_in_stock,
        'low_stock_items': low_stock_items,
        'out_of_stock': out_of_stock,
        'critical_stock': critical_stock,
        
        # Chart data
        'sales_chart_labels': json.dumps(sales_chart_labels, cls=DjangoJSONEncoder),
        'sales_chart_data': json.dumps(sales_chart_data, cls=DjangoJSONEncoder),
        'product_chart_labels': json.dumps(product_labels, cls=DjangoJSONEncoder),
        'product_chart_data': json.dumps(product_data, cls=DjangoJSONEncoder),
        
        # Recent orders
        'recent_orders': recent_orders,
        
        # Quick stats
        'pending_orders': pending_orders,
        'completed_today': completed_today,
        
        # Recent activities
        'recent_activities': recent_activities,
        
        # Selected period
        'selected_period': period,
        'today': today,
    }
    
    return render(request, 'sales/dashboard.html', context)

def get_time_ago(date):
    """Helper function to get time ago string"""
    today = timezone.now().date()
    diff = (today - date).days
    
    if diff == 0:
        return 'Today'
    elif diff == 1:
        return 'Yesterday'
    elif diff < 7:
        return f'{diff} days ago'
    elif diff < 30:
        weeks = diff // 7
        return f'{weeks} week{"s" if weeks > 1 else ""} ago'
    else:
        return date.strftime('%b %d, %Y')


@login_required
@staff_required
def profile_view(request):
    # Get the current logged-in user
    user = request.user
    
    # Get the user's profile
    try:
        profile = UserProfile.objects.get(user=user)
        
    except UserProfile.DoesNotExist:
        # Create profile if it doesn't exist (just in case)
        profile = UserProfile.objects.create(
            user=user,
            contact="",
            role='STAFF' 
        )
    
    return render(request, 'sales/profile.html', {"profile": profile})
    

@login_required
@staff_required
def sales_order_form(request, pk=None):
    if pk:
        order = get_object_or_404(SalesOrder, pk=pk)
        old_status = order.status
    else:
        order = SalesOrder()   # ✅ create empty instance
        old_status = order.status

    if request.method == 'POST':
        form = SalesOrderForm(request.POST, instance=order)
        formset = OrderItemFormSet(request.POST, instance=order)

        if form.is_valid() and formset.is_valid():
            order = form.save(commit=False)
            order.subtotal = 0
            order.total_amount = order.shipping_cost or 0
            order.save()

            formset.instance = order
            formset.save()

            order.calculate_totals()
            order.save()

            # Enforce stock rules based on chosen status
            new_status = order.status
            success, msg = _apply_status_and_stock(order, new_status, old_status)
            if success:
                messages.success(request, msg)
            else:
                messages.warning(request, msg)

            # Update customer statistics
            if order.customer:
                order.customer.update_stats()

            return redirect('sales_order_detail', pk=order.pk)
    else:
        form = SalesOrderForm(instance=order)
        formset = OrderItemFormSet(instance=order)

    return render(request, 'sales/sales_order_form.html', {
        'form': form,
        'formset': formset
    })

@login_required
@staff_required
def get_product_details(request, product_id):
    """AJAX view to get product details including base price"""
    try:
        product = Product.objects.get(id=product_id)
        return JsonResponse({
            'success': True,
            'product_id': product.id,
            'product_name': product.name,
            'base_price': float(product.price),
            'sku': product.sku,
            'available_quantity': product.quantity,
            'minimum_stock': product.minimum_stock
        })
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found'
        }, status=404)

@login_required
@staff_required
def update_order_status(request, pk, status):
    """Update the status of a sales order"""
    order = get_object_or_404(SalesOrder, pk=pk)
    
    # Validate status
    valid_statuses = [choice[0] for choice in ORDER_STATUS_CHOICES]
    if status in valid_statuses:
        old_status = order.status
        success, msg = _apply_status_and_stock(order, status, old_status)

        # Update customer stats if status changed to/from completed
        if old_status != order.status and (order.status == 'completed' or old_status == 'completed'):
            if order.customer:
                order.customer.update_stats()

        if success:
            messages.success(request, msg)
        else:
            messages.warning(request, msg)
    else:
        messages.error(request, 'Invalid status')
    
    return redirect('sales_order_detail', pk=order.pk)

@login_required
@staff_required
def sales_order(request):
    orders = SalesOrder.objects.all().order_by('-order_date')
    
    # Calculate statistics
    total_orders = orders.count()
    
    # Total revenue from completed orders
    total_revenue = SalesOrder.objects.filter(
        status='completed'
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Revenue growth (compare with last month)
    today = timezone.now().date()
    last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_month_end = today.replace(day=1) - timedelta(days=1)
    
    current_month_revenue = SalesOrder.objects.filter(
        status='completed',
        order_date__gte=today.replace(day=1)
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    last_month_revenue = SalesOrder.objects.filter(
        status='completed',
        order_date__gte=last_month_start,
        order_date__lte=last_month_end
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    revenue_growth = 0
    if last_month_revenue > 0:
        revenue_growth = round(((current_month_revenue - last_month_revenue) / last_month_revenue) * 100)
    
    # Average order value
    completed_orders = SalesOrder.objects.filter(status='completed')
    if completed_orders.exists():
        avg_order_value = completed_orders.aggregate(
            avg=Sum('total_amount') / Count('id')
        )['avg'] or 0
    else:
        avg_order_value = 0
    
    # Average items per order
    total_items = SalesOrderItem.objects.filter(
        sales_order__in=orders
    ).count()
    avg_items_per_order = round(total_items / total_orders, 1) if total_orders > 0 else 0
    
    # Highest order
    highest_order = orders.order_by('-total_amount').first()
    
    # Orders today
    orders_today = orders.filter(order_date=today).count()
    
    # Pending orders
    pending_orders = orders.filter(status__in=['pending', 'processing']).count()
    
    # Completed today
    completed_today = orders.filter(status='completed', order_date=today).count()
    
    # Status counts for distribution
    status_counts = {}
    for status, _ in ORDER_STATUS_CHOICES:
        count = orders.filter(status=status).count()
        if count > 0:
            status_counts[status] = count
    
    context = {
        'orders': orders,
        'total_revenue': total_revenue,
        'revenue_growth': revenue_growth,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value,
        'avg_items_per_order': avg_items_per_order,
        'highest_order': highest_order,
        'orders_today': orders_today,
        'pending_orders': pending_orders,
        'completed_today': completed_today,
        'status_counts': status_counts,
    }
    
    return render(request, 'sales/sales_order_list.html', context)

@login_required
@staff_required
def sales_order_detail(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    
    # Handle status update via POST
    if request.method == 'POST' and 'update_status' in request.POST:
        new_status = request.POST.get('status')
        if new_status in dict(ORDER_STATUS_CHOICES):
            old_status = order.status
            success, msg = _apply_status_and_stock(order, new_status, old_status)

            # Update customer stats when order status changes
            if old_status != order.status and (order.status == 'completed' or old_status == 'completed'):
                if order.customer:
                    order.customer.update_stats()

            if success:
                messages.success(request, msg)
            else:
                messages.warning(request, msg)

            return redirect('sales_order_detail', pk=order.pk)
    
    return render(request, 'sales/sales_order_detail.html', {'order': order})


@login_required
@staff_required
def customer(request):
    # Get all customers
    customers = Customer.objects.all().order_by('-customer_since')
    
    # Annotate each customer with real-time order data
    
    customers = customers.annotate(
        order_count=Count('salesorder'),
        total_spent_calc=Sum('salesorder__total_amount', filter=Q(salesorder__status='completed')),
        last_order_date_calc=Max('salesorder__order_date')
    )
    
    # Calculate statistics
    total_customers = customers.count()
    active_customers = customers.filter(status='active').count()
    
    # Total orders and revenue from all customers
    from .models import SalesOrder, SalesOrderItem
    
    total_orders = SalesOrder.objects.count()
    total_revenue = SalesOrder.objects.filter(
        status='completed'
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    context = {
        'customers': customers,
        'total_customers': total_customers,
        'active_customers': active_customers,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
    }
    
    return render(request, 'sales/customer.html', context)

@login_required
@staff_required
def customer_form(request, pk=None):
    if pk:
        customer = get_object_or_404(Customer, pk=pk)
        form = CustomerForm(instance=customer)
    else:
        form = CustomerForm()
    
    if request.method == 'POST':
        if pk:
            form = CustomerForm(request.POST, instance=customer)
        else:
            form = CustomerForm(request.POST)
        
        if form.is_valid():
            form.save()
            return redirect('customers')
    
    today = timezone.now().date()
    return render(request, 'sales/customer_form.html', {
        'form': form,
        'today': today
    })


