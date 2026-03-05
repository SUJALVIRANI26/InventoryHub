from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDay, TruncMonth
from django.shortcuts import render
from django.utils import timezone

from inventory_manager.models import Product, PurchaseOrderItem
from sales.models import SalesOrder, SalesOrderItem


def _safe_decimal(value):
    return value if value is not None else Decimal('0')


def _percent_delta(current, previous):
    current = _safe_decimal(current)
    previous = _safe_decimal(previous)
    if previous == 0:
        return Decimal('100.0') if current > 0 else Decimal('0.0')
    return ((current - previous) / previous) * Decimal('100.0')


def _period_bounds(period):
    today = timezone.localdate()

    if period == 'daily':
        return today, today, 'day'
    if period == 'weekly':
        return today - timedelta(days=6), today, 'day'
    if period == 'monthly':
        return today.replace(day=1), today, 'day'
    if period == 'yearly':
        return today.replace(month=1, day=1), today, 'month'

    return today - timedelta(days=6), today, 'day'


def _sales_total_between(start_date, end_date):
    return _safe_decimal(
        SalesOrder.objects.filter(order_date__range=(start_date, end_date)).aggregate(
            total=Sum('total_amount')
        )['total']
    )


def _purchase_total_between(start_date, end_date):
    line_total = ExpressionWrapper(
        F('quantity') * F('unit_price'),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    return _safe_decimal(
        PurchaseOrderItem.objects.filter(purchase_order__order_date__range=(start_date, end_date)).aggregate(
            total=Sum(line_total)
        )['total']
    )


def _build_report_context(title, subtitle, period):
    start_date, end_date, chart_grain = _period_bounds(period)

    sales_qs = SalesOrder.objects.filter(order_date__range=(start_date, end_date))
    sales_total = _safe_decimal(sales_qs.aggregate(total=Sum('total_amount'))['total'])
    orders_count = sales_qs.count()

    purchase_total = _purchase_total_between(start_date, end_date)
    net_profit = sales_total - purchase_total

    stock_value_expr = ExpressionWrapper(
        F('quantity') * F('price'),
        output_field=DecimalField(max_digits=16, decimal_places=2),
    )
    stock_value = _safe_decimal(Product.objects.aggregate(total=Sum(stock_value_expr))['total'])
    low_stock_count = Product.objects.filter(quantity__lte=F('minimum_stock')).count()

    period_days = (end_date - start_date).days + 1
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_days - 1)

    previous_sales_total = _sales_total_between(previous_start, previous_end)
    previous_purchase_total = _purchase_total_between(previous_start, previous_end)
    previous_net_profit = previous_sales_total - previous_purchase_total

    sales_delta = _percent_delta(sales_total, previous_sales_total)
    purchase_delta = _percent_delta(purchase_total, previous_purchase_total)
    net_profit_delta = _percent_delta(net_profit, previous_net_profit)

    if chart_grain == 'month':
        trend_qs = sales_qs.annotate(point=TruncMonth('order_date')).values('point').annotate(
            total=Sum('total_amount')
        ).order_by('point')
        trend_labels = [item['point'].strftime('%b') for item in trend_qs]
    else:
        trend_qs = sales_qs.annotate(point=TruncDay('order_date')).values('point').annotate(
            total=Sum('total_amount')
        ).order_by('point')
        trend_labels = [item['point'].strftime('%d %b') for item in trend_qs]

    trend_values = [float(_safe_decimal(item['total'])) for item in trend_qs]

    if not trend_labels:
        trend_labels = ['No Data']
        trend_values = [0]

    mix_labels = ['Sales', 'Purchase', 'Stock Value']
    mix_values = [float(sales_total), float(purchase_total), float(stock_value)]

    top_products_qs = SalesOrderItem.objects.filter(
        sales_order__order_date__range=(start_date, end_date)
    ).values('product__name').annotate(
        qty_sold=Sum('quantity'),
        revenue=Sum('total_price'),
    ).order_by('-qty_sold')[:5]

    top_product_name = top_products_qs[0]['product__name'] if top_products_qs else 'N/A'

    sales_tx = list(
        sales_qs.values('order_date', 'status', 'total_amount').order_by('-order_date')[:6]
    )
    purchase_tx = list(
        PurchaseOrderItem.objects.filter(
            purchase_order__order_date__range=(start_date, end_date)
        ).select_related('purchase_order').values(
            'purchase_order__order_date',
            'purchase_order__status',
            'quantity',
            'unit_price',
        ).order_by('-purchase_order__order_date')[:6]
    )

    status_map = {
        'completed': ('Completed', 'success'),
        'delivered': ('Delivered', 'success'),
        'pending': ('Pending', 'warning'),
        'processing': ('Processing', 'warning'),
        'ordered': ('Ordered', 'warning'),
        'cancelled': ('Cancelled', 'danger'),
        'inactive': ('Inactive', 'danger'),
    }

    transactions = []

    for row in sales_tx:
        status_label, status_class = status_map.get(row['status'], (row['status'].title(), 'warning'))
        transactions.append({
            'date': row['order_date'],
            'category': 'Sales',
            'amount': _safe_decimal(row['total_amount']),
            'status_label': status_label,
            'status_class': status_class,
        })

    for row in purchase_tx:
        amount = Decimal(str(row['quantity'])) * _safe_decimal(row['unit_price'])
        raw_status = row['purchase_order__status']
        status_label, status_class = status_map.get(raw_status, (raw_status.title(), 'warning'))
        transactions.append({
            'date': row['purchase_order__order_date'],
            'category': 'Purchase',
            'amount': amount,
            'status_label': status_label,
            'status_class': status_class,
        })

    transactions.sort(key=lambda item: item['date'], reverse=True)

    return {
        'page_title': title,
        'page_subtitle': subtitle,
        'start_date': start_date,
        'end_date': end_date,
        'sales_total': sales_total,
        'purchase_total': purchase_total,
        'net_profit': net_profit,
        'orders_count': orders_count,
        'stock_value': stock_value,
        'low_stock_count': low_stock_count,
        'top_product_name': top_product_name,
        'sales_delta': round(float(sales_delta), 2),
        'purchase_delta': round(float(purchase_delta), 2),
        'net_profit_delta': round(float(net_profit_delta), 2),
        'trend_labels': trend_labels,
        'trend_values': trend_values,
        'mix_labels': mix_labels,
        'mix_values': mix_values,
        'transactions': transactions[:10],
    }


@login_required
def dashboard(request):
    return render(
        request,
        'owner/dashboard.html',
        {
            'page_title': 'Owner Dashboard',
            'page_subtitle': 'Business overview and all reports',
        },
    )


@login_required
def daily_report(request):
    return render(
        request,
        'owner/reports/daily_report.html',
        _build_report_context('Daily Report', "Today's overall business performance", 'daily'),
    )


@login_required
def weekly_report(request):
    return render(
        request,
        'owner/reports/weekly_report.html',
        _build_report_context('Weekly Report', '7-day trend and KPI movement', 'weekly'),
    )


@login_required
def monthly_report(request):
    return render(
        request,
        'owner/reports/monthly_report.html',
        _build_report_context('Monthly Report', 'Monthly performance and comparisons', 'monthly'),
    )


@login_required
def yearly_report(request):
    return render(
        request,
        'owner/reports/yearly_report.html',
        _build_report_context('Yearly Report', 'Annual growth and long-term trends', 'yearly'),
    )


@login_required
def profit_loss_report(request):
    return render(
        request,
        'owner/reports/profit_loss_report.html',
        _build_report_context('Profit & Loss Report', 'Revenue, cost, and profit analysis', 'monthly'),
    )


@login_required
def stock_report(request):
    return render(
        request,
        'owner/reports/stock_report.html',
        _build_report_context('Stock Report', 'Current stock position and valuation', 'monthly'),
    )


@login_required
def sales_report(request):
    return render(
        request,
        'owner/reports/sales_report.html',
        _build_report_context('Sales Report', 'Sales performance by category and time', 'monthly'),
    )


@login_required
def purchase_report(request):
    return render(
        request,
        'owner/reports/purchase_report.html',
        _build_report_context('Purchase Report', 'Purchase trends and supplier spend', 'monthly'),
    )


@login_required
def top_products_report(request):
    return render(
        request,
        'owner/reports/top_products_report.html',
        _build_report_context('Top Products Report', 'Best performing products by sales', 'monthly'),
    )
