from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def _owner_context(title, subtitle):
    return {
        'page_title': title,
        'page_subtitle': subtitle,
    }


@login_required
def dashboard(request):
    return render(request, 'owner/dashboard.html', _owner_context('Owner Dashboard', 'Business overview and all reports'))


@login_required
def daily_report(request):
    return render(request, 'owner/reports/daily_report.html', _owner_context('Daily Report', 'Today\'s overall business performance'))


@login_required
def weekly_report(request):
    return render(request, 'owner/reports/weekly_report.html', _owner_context('Weekly Report', '7-day trend and KPI movement'))


@login_required
def monthly_report(request):
    return render(request, 'owner/reports/monthly_report.html', _owner_context('Monthly Report', 'Monthly performance and comparisons'))


@login_required
def yearly_report(request):
    return render(request, 'owner/reports/yearly_report.html', _owner_context('Yearly Report', 'Annual growth and long-term trends'))


@login_required
def profit_loss_report(request):
    return render(request, 'owner/reports/profit_loss_report.html', _owner_context('Profit & Loss Report', 'Revenue, cost, and profit analysis'))


@login_required
def stock_report(request):
    return render(request, 'owner/reports/stock_report.html', _owner_context('Stock Report', 'Current stock position and valuation'))


@login_required
def sales_report(request):
    return render(request, 'owner/reports/sales_report.html', _owner_context('Sales Report', 'Sales performance by category and time'))


@login_required
def purchase_report(request):
    return render(request, 'owner/reports/purchase_report.html', _owner_context('Purchase Report', 'Purchase trends and supplier spend'))


@login_required
def top_products_report(request):
    return render(request, 'owner/reports/top_products_report.html', _owner_context('Top Products Report', 'Best performing products by sales'))
