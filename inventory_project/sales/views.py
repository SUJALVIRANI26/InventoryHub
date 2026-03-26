from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.contrib import messages
from django.db.models import Sum, Q, Count, Max
from datetime import timedelta, date as date_type
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
from decimal import Decimal

from .forms import OrderItemFormSet, SalesOrderForm, CustomerForm
from .models import SalesOrder, Customer, SalesOrderItem, ORDER_STATUS_CHOICES
from admin_panel.models import UserProfile
from accounts.decorators import staff_required
from inventory_manager.models import Product, BacklogEntry


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_time_ago(d):
    diff = (timezone.now().date() - d).days
    if diff == 0:  return 'Today'
    if diff == 1:  return 'Yesterday'
    if diff < 7:   return f'{diff} days ago'
    if diff < 30:
        w = diff // 7
        return f'{w} week{"s" if w > 1 else ""} ago'
    return d.strftime('%b %d, %Y')


def _revenue_growth(current, previous):
    if not previous:
        return 0
    return round(((float(current) - float(previous)) / float(previous)) * 100)


def _order_has_open_backlog(order):
    # Backend-only helper. No direct frontend or JS call reaches this.
    #
    # Used by:
    # - `_normalize_backlog_status()`
    # - `_apply_status_and_stock()`
    # - `sales_order_detail()`
    #
    # Frontend file that consumes the final result:
    # - `templates/sales/sales_order_detail.html`
    #
    # This only returns a boolean; it does not render a response itself.
    if not order.pk:
        return False

    # Primary backlog check uses the sales order items directly because
    # `backordered_qty` is the closest source of truth for what the order still
    # has outstanding.
    if order.items.filter(backordered_qty__gt=0).exists():
        return True

    # Keep a fallback on BacklogEntry rows as well, using `sales_order_id`
    # instead of only `sales_order_item_id`, so older rows cannot slip past the
    # status guard.
    return BacklogEntry.objects.filter(
        sales_order_id=order.pk,
        quantity_on_backlog__gt=0,
    ).exists()


def _normalize_backlog_status(order):
    # Safety net for old/bad data.
    #
    # Called from:
    # - `sales_order_detail()`
    # - `sales_order_form()`
    # - `update_order_status()`
    #
    # If an order already has backlog but was somehow saved as
    # processing/shipped/completed earlier, this helper pushes it back to
    # `pending` before the frontend is rendered again.
    if (
        order.pk
        and order.status not in ('pending', 'cancelled')
        and _order_has_open_backlog(order)
    ):
        order.status = 'pending'
        order.save(update_fields=['status'])
        return True
    return False


def _apply_status_and_stock(order, new_status, old_status=None):
    """
    Handle order status transitions.
    - orders with open backlog must remain pending
    - cancelled returns only deducted stock and clears backlog
    Returns (success: bool, message: str)
    """
    # Central backend gate for order status changes.
    #
    # Called from:
    # - `sales_order_form()` after create/edit submit
    # - `sales_order_detail()` on POST
    # - `update_order_status()` from action links
    #
    # Frontend files affected by the result:
    # - `templates/sales/sales_order_form.html`
    # - `templates/sales/sales_order_detail.html`
    # - `templates/sales/sales_order_list.html`
    #
    # This returns a `(success, message)` tuple. The message is passed to the
    # frontend through Django messages, not through fetch/AJAX.
    old_status = old_status or order.status
    has_backlog = _order_has_open_backlog(order)

    if has_backlog and new_status not in ('pending', 'cancelled'):
        # This is the actual business rule: backlog means the order cannot move
        # beyond pending until stock is fulfilled.
        if order.status != 'pending':
            order.status = 'pending'
            order.save(update_fields=['status'])
        return False, (
            "This order has items on backlog, so it must remain in Pending status "
            "until all backlog quantities are fulfilled."
        )

    if old_status == new_status:
        return True, "Order status unchanged."

    if new_status == 'cancelled' and old_status != 'cancelled':
        for item in order.items.select_related('product').all():
            if item.deducted_qty > 0:
                item.product.quantity += item.deducted_qty
                item.product.save()
            BacklogEntry.objects.filter(
                sales_order_item_id=item.pk,
                quantity_on_backlog__gt=0,
            ).update(quantity_on_backlog=0, fulfilled_at=timezone.now())
            SalesOrderItem.objects.filter(pk=item.pk).update(
                backordered_qty=0, deducted_qty=0,
            )
        order.status = 'cancelled'
        order.save()
        return True, "Order cancelled and stock restored."

    order.status = new_status
    order.save()
    return True, "Order status updated."


# ─────────────────────────────────────────────
# DASHBOARD
# All calculations done in pure Python — avoids TruncDate / Sum
# annotations that crash SQLite on Python 3.14.
# ─────────────────────────────────────────────

@login_required
@staff_required
def dashboard(request):
    period = request.GET.get('period', '7')
    today  = timezone.now().date()
    days   = {'30': 30, '90': 90}.get(period, 7)
    start  = today - timedelta(days=days)
    prev_start = start - timedelta(days=days)
    yesterday  = today - timedelta(days=1)

    # ── Pull raw order data once ──────────────────────────────
    # Using values() returns dicts – no custom DB functions involved
    all_orders = list(
        SalesOrder.objects.values(
            'id', 'status', 'order_date', 'total_amount', 'customer_id'
        )
    )

    # ── Revenue ───────────────────────────────────────────────
    def _sum_amount(rows):
        return sum(float(r['total_amount'] or 0) for r in rows)

    completed_orders = [o for o in all_orders if o['status'] == 'completed']
    total_revenue    = _sum_amount(completed_orders)
    cur_rev  = _sum_amount(
        o for o in completed_orders if o['order_date'] >= start
    )
    prev_rev = _sum_amount(
        o for o in completed_orders
        if prev_start <= o['order_date'] < start
    )

    # ── Order counts ──────────────────────────────────────────
    orders_today     = sum(1 for o in all_orders if o['order_date'] == today)
    orders_yesterday = sum(1 for o in all_orders if o['order_date'] == yesterday)

    # ── Customers ─────────────────────────────────────────────
    thirty_days_ago = today - timedelta(days=30)
    all_customers   = list(Customer.objects.values('id', 'status', 'customer_since'))
    total_customers = sum(1 for c in all_customers if c['status'] == 'active')
    new_customers   = sum(1 for c in all_customers
                          if c['customer_since'] >= thirty_days_ago)

    # ── Product stock counts (pure Python, no F()) ────────────
    all_products = list(Product.objects.values('id', 'quantity', 'minimum_stock'))
    products_in_stock = sum(1 for p in all_products if p['quantity'] > 0)
    low_stock_items   = sum(1 for p in all_products
                            if 0 < p['quantity'] <= p['minimum_stock'])
    out_of_stock      = sum(1 for p in all_products if p['quantity'] == 0)

    # Products with open backlog entries
    backlog_product_ids = set(
        BacklogEntry.objects.filter(quantity_on_backlog__gt=0)
        .values_list('product_id', flat=True)
    )
    backlog_items  = len(backlog_product_ids)

    low_list_ids   = [p['id'] for p in all_products
                      if p['quantity'] < p['minimum_stock']]
    low_stock_list = Product.objects.filter(id__in=low_list_ids)

    # ── Sales chart – grouped by date in Python ───────────────
    fmt          = '%a' if period == '7' else '%b %d'
    date_range   = [start + timedelta(days=i) for i in range(days + 1)]
    sales_dict   = {}  # date → float amount

    for o in completed_orders:
        d = o['order_date']
        if d >= start:
            sales_dict[d] = sales_dict.get(d, 0.0) + float(o['total_amount'] or 0)

    sales_chart_labels = [d.strftime(fmt) for d in date_range]
    sales_chart_data   = [round(sales_dict.get(d, 0.0), 2) for d in date_range]

    # ── Product chart – top 4 by units sold ───────────────────
    # Pull order-item quantities in Python to avoid Sum annotation crash
    sold_items = list(
        SalesOrderItem.objects.filter(
            sales_order__status='completed',
            sales_order__order_date__gte=start,
        ).values('product__name', 'quantity')
    )

    product_qty: dict = {}
    for si in sold_items:
        name = si['product__name']
        product_qty[name] = product_qty.get(name, 0) + (si['quantity'] or 0)

    top4 = sorted(product_qty.items(), key=lambda x: x[1], reverse=True)[:4]

    if top4:
        product_labels = [item[0] for item in top4]
        product_data   = [float(item[1]) for item in top4]
    else:
        fb = Product.objects.order_by('-quantity')[:4]
        product_labels = [p.name for p in fb]
        product_data   = [float(max(p.quantity, 0)) for p in fb]

    # ── Recent orders ─────────────────────────────────────────
    recent_orders = (
        SalesOrder.objects.select_related('customer')
        .order_by('-order_date', '-id')[:5]
    )

    # ── Recent activities ─────────────────────────────────────
    recent_activities = []
    for order in SalesOrder.objects.select_related('customer').order_by(
            '-order_date', '-id')[:3]:
        recent_activities.append({
            'description': f"New order #{order.id} from {order.customer.name}",
            'time_ago':    get_time_ago(order.order_date),
            'icon':        'fa-solid fa-cart-plus',
            'color':       '#4e73df',
        })
    for bl in BacklogEntry.objects.filter(
            quantity_on_backlog__gt=0).select_related('product')[:3]:
        recent_activities.append({
            'description': (f"Backlog: {bl.product.name} – "
                            f"{bl.quantity_on_backlog} units owed"),
            'time_ago':    'Backlog',
            'icon':        'fa-solid fa-triangle-exclamation',
            'color':       '#e74a3b',
        })

    # ── Pending / completed today ─────────────────────────────
    pending_orders  = sum(1 for o in all_orders
                          if o['status'] in ('pending', 'processing'))
    completed_today = sum(1 for o in all_orders
                          if o['status'] == 'completed' and o['order_date'] == today)

    context = {
        'total_revenue':      round(total_revenue, 2),
        'revenue_growth':     _revenue_growth(cur_rev, prev_rev),
        'orders_today':       orders_today,
        'orders_growth':      _revenue_growth(orders_today, orders_yesterday),
        'total_customers':    total_customers,
        'customer_growth':    (round((new_customers / total_customers) * 100)
                               if total_customers else 0),
        'products_in_stock':  products_in_stock,
        'low_stock_items':    low_stock_items,
        'backlog_items':      backlog_items,
        'out_of_stock':       out_of_stock,
        'low_stock_list':     low_stock_list,
        'sales_chart_labels': json.dumps(sales_chart_labels),
        'sales_chart_data':   json.dumps(sales_chart_data),
        'product_chart_labels': json.dumps(product_labels),
        'product_chart_data':   json.dumps(product_data),
        'recent_orders':      recent_orders,
        'recent_activities':  recent_activities,
        'pending_orders':     pending_orders,
        'completed_today':    completed_today,
        'selected_period':    period,
        'today':              today,
        'yesterday':          yesterday,
    }
    return render(request, 'sales/dashboard.html', context)


# ─────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────

@login_required
@staff_required
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(
        user=request.user, defaults={'contact': '', 'role': 'STAFF'}
    )
    return render(request, 'sales/profile.html', {'profile': profile})


# ─────────────────────────────────────────────
# CUSTOMERS
# ─────────────────────────────────────────────

@login_required
@staff_required
def customer(request):
    customers = Customer.objects.annotate(
        order_count=Count('salesorder'),
        total_spent_calc=Sum('salesorder__total_amount',
                             filter=Q(salesorder__status='completed')),
        last_order_date_calc=Max('salesorder__order_date'),
    ).order_by('-customer_since')

    # Revenue in Python to avoid SQLite crash
    all_completed = list(
        SalesOrder.objects.filter(status='completed').values('total_amount')
    )
    total_revenue = sum(float(o['total_amount'] or 0) for o in all_completed)

    context = {
        'customers':        customers,
        'total_customers':  customers.count(),
        'active_customers': customers.filter(status='active').count(),
        'total_orders':     SalesOrder.objects.count(),
        'total_revenue':    round(total_revenue, 2),
    }
    return render(request, 'sales/customer.html', context)


@login_required
@staff_required
def customer_form(request, pk=None):
    instance = get_object_or_404(Customer, pk=pk) if pk else None
    form = CustomerForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('customers')
    return render(request, 'sales/customer_form.html', {'form': form})


# ─────────────────────────────────────────────
# SALES ORDERS — LIST
# ─────────────────────────────────────────────

@login_required
@staff_required
def sales_order(request):
    today  = timezone.now().date()
    orders = SalesOrder.objects.all().order_by('-order_date')

    # All amounts in Python to avoid SQLite crash
    all_orders_data = list(orders.values(
        'id', 'status', 'order_date', 'total_amount', 'customer_id'
    ))

    month_start      = today.replace(day=1)
    last_month_end   = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    completed_data = [o for o in all_orders_data if o['status'] == 'completed']
    total_revenue  = sum(float(o['total_amount'] or 0) for o in completed_data)

    cur_rev  = sum(float(o['total_amount'] or 0) for o in completed_data
                   if o['order_date'] >= month_start)
    prev_rev = sum(float(o['total_amount'] or 0) for o in completed_data
                   if last_month_start <= o['order_date'] <= last_month_end)

    total_orders  = len(all_orders_data)
    total_items   = SalesOrderItem.objects.filter(
        sales_order__in=orders).count()
    avg_order_val = (total_revenue / max(len(completed_data), 1))
    avg_items     = round(total_items / total_orders, 1) if total_orders else 0

    highest_order = orders.order_by('-total_amount').first()

    orders_today   = sum(1 for o in all_orders_data if o['order_date'] == today)
    pending_orders = sum(1 for o in all_orders_data
                         if o['status'] in ('pending', 'processing'))
    completed_today = sum(1 for o in all_orders_data
                          if o['status'] == 'completed' and o['order_date'] == today)

    status_counts = {}
    for s, _ in ORDER_STATUS_CHOICES:
        c = sum(1 for o in all_orders_data if o['status'] == s)
        if c > 0:
            status_counts[s] = c

    context = {
        'orders':              orders,
        'total_orders':        total_orders,
        'total_revenue':       round(total_revenue, 2),
        'revenue_growth':      _revenue_growth(cur_rev, prev_rev),
        'avg_order_value':     round(avg_order_val, 2),
        'avg_items_per_order': avg_items,
        'highest_order':       highest_order,
        'orders_today':        orders_today,
        'pending_orders':      pending_orders,
        'completed_today':     completed_today,
        'status_counts':       status_counts,
    }
    return render(request, 'sales/sales_order_list.html', context)


# ─────────────────────────────────────────────
# SALES ORDER — DETAIL
# ─────────────────────────────────────────────

@login_required
@staff_required
def sales_order_detail(request, pk):
    # Detail page controller for a single sales order.
    #
    # Template rendered:
    # - `templates/sales/sales_order_detail.html`
    #
    # Data passed to frontend:
    # - `order`
    # - `has_backlog`
    # - `open_backlogs`
    # - `backlog_locked`
    #
    # Frontend call pattern:
    # - normal GET renders the page
    # - normal POST from the same page can request a status change
    # - there is no JS fetch/AJAX call here
    order = get_object_or_404(SalesOrder, pk=pk)
    _normalize_backlog_status(order)

    if request.method == 'POST' and 'update_status' in request.POST:
        # Posted by the order-detail frontend when the user tries to update
        # status from this page.
        new_status = request.POST.get('status')
        if new_status in dict(ORDER_STATUS_CHOICES):
            old_status = order.status
            success, msg = _apply_status_and_stock(order, new_status, old_status)
            if old_status != order.status and order.customer:
                order.customer.update_stats()
            if success:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
        return redirect('sales_order_detail', pk=order.pk)

    has_backlog   = _order_has_open_backlog(order)
    item_ids      = list(order.items.values_list('id', flat=True))
    open_backlogs = (
        BacklogEntry.objects.filter(
            sales_order_item_id__in=item_ids,
            quantity_on_backlog__gt=0,
        ).select_related('product')
        if item_ids else BacklogEntry.objects.none()
    )

    return render(request, 'sales/sales_order_detail.html', {
        'order':         order,
        'has_backlog':   has_backlog,
        'open_backlogs': open_backlogs,
        'backlog_locked': has_backlog and order.status != 'cancelled',
    })


# ─────────────────────────────────────────────
# SALES ORDER — CREATE / EDIT
# ─────────────────────────────────────────────

@login_required
@staff_required
def sales_order_form(request, pk=None):
    # Create/edit page controller for sales orders.
    #
    # Template rendered:
    # - `templates/sales/sales_order_form.html`
    #
    # Data passed to frontend:
    # - `form` for order-level fields
    # - `formset` for line items
    #
    # Frontend integration:
    # - page enhancement JS lives in `static/sales/order_form.js`
    # - status enforcement is still backend-only and happens here plus in
    #   `_apply_status_and_stock()`
    order      = get_object_or_404(SalesOrder, pk=pk) if pk else SalesOrder()
    if order.pk:
        _normalize_backlog_status(order)
    old_status = order.status

    if request.method == 'POST':
        # Submit path for the create/edit frontend form.
        form    = SalesOrderForm(request.POST, instance=order)
        formset = OrderItemFormSet(request.POST, instance=order)
        list(messages.get_messages(request))

        if form.is_valid() and formset.is_valid():
            try:
                order = form.save(commit=False)
                order.subtotal     = 0
                order.total_amount = order.shipping_cost or 0
                order.save()

                formset.instance = order
                formset.save()
                order.calculate_totals()
                order.save()

                requested_status = form.cleaned_data['status']
                # Final server-side check after form submit. Even if someone
                # bypasses frontend restrictions, backlog keeps the order in
                # `pending`.
                success, msg = _apply_status_and_stock(order, requested_status, old_status)
                if success:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)

                if order.customer:
                    order.customer.update_stats()

                return redirect('sales_order_detail', pk=order.pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form    = SalesOrderForm(instance=order)
        formset = OrderItemFormSet(instance=order)

    return render(request, 'sales/sales_order_form.html', {
        'form': form, 'formset': formset,
    })


# ─────────────────────────────────────────────
# STATUS UPDATE (URL-based)
# ─────────────────────────────────────────────

@login_required
@staff_required
def update_order_status(request, pk, status):
    # URL-based action endpoint used by buttons/links in the order detail page.
    #
    # Frontend source:
    # - `templates/sales/sales_order_detail.html`
    #
    # Behavior:
    # - applies backend transition rules
    # - stores a Django message
    # - redirects back to the detail page
    order = get_object_or_404(SalesOrder, pk=pk)
    _normalize_backlog_status(order)
    valid = [s for s, _ in ORDER_STATUS_CHOICES]
    if status in valid:
        old_status = order.status
        success, msg = _apply_status_and_stock(order, status, old_status)
        if old_status != order.status and order.customer:
            order.customer.update_stats()
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
    else:
        messages.error(request, 'Invalid status.')
    return redirect('sales_order_detail', pk=order.pk)


# ─────────────────────────────────────────────
# BACKLOG LIST
# ─────────────────────────────────────────────

@login_required
@staff_required
def backlog_list(request):
    open_backlogs = (
        BacklogEntry.objects.filter(quantity_on_backlog__gt=0)
        .select_related('product')
        .order_by('created_at')
    )
    return render(request, 'sales/backlog_list.html',
                  {'open_backlogs': open_backlogs})


# ─────────────────────────────────────────────
# AJAX
# ─────────────────────────────────────────────

@login_required
@staff_required
def get_product_details(request, product_id):
    try:
        p = Product.objects.get(id=product_id)
        open_backlog = sum(
            bl.quantity_on_backlog
            for bl in BacklogEntry.objects.filter(
                product=p, quantity_on_backlog__gt=0
            )
        )
        return JsonResponse({
            'success':            True,
            'product_id':         p.id,
            'product_name':       p.name,
            'base_price':         float(p.price),
            'sku':                p.sku,
            'available_quantity': p.quantity,
            'minimum_stock':      p.minimum_stock,
            'open_backlog':       open_backlog,
        })
    except Product.DoesNotExist:
        return JsonResponse(
            {'success': False, 'error': 'Product not found'}, status=404)
