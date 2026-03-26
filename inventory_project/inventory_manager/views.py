from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from accounts.decorators import manager_required
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta

from .models import (
    Product, Supplier, PurchaseOrder, PurchaseOrderItem, BacklogEntry
)
from .forms import ProductForm, SupplierForm, PurchaseOrderForm, PurchaseOrderItemFormSet


# ─────────────────────────────────────────────
# HELPER: fulfil backlog when a PO is delivered
# ─────────────────────────────────────────────

def _fulfil_backlog_after_delivery(purchase_order):
    """
    Called when a PO is marked as delivered.

    For every item in the PO:
    1. Add received quantity to product stock.
    2. Let `Product.save()` immediately allocate that stock to open backlog
       FIFO (first come, first served).
    3. As backlog is fulfilled, product quantity is reduced again because
       those units are now committed to existing orders.

    The actual FIFO backlog conversion now lives in:
    - `inventory_manager.models.Product._fulfil_open_backlog_from_stock()`

    This keeps PO delivery and manual quantity edits consistent because both
    flows go through the same stock-increase rule.
    """
    for po_item in purchase_order.items.select_related('product').all():
        product = po_item.product

        # This save call is the backend entry point for backlog fulfilment.
        # The model layer will:
        # - add the delivered units
        # - allocate them to the oldest backlog entries first
        # - decrease product.quantity again for fulfilled backlog units
        # - sync SalesOrderItem deducted/backordered fields
        product.quantity += po_item.quantity
        product.save()


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@login_required
@manager_required
def dashboard(request):
    products  = Product.objects.all()
    suppliers = Supplier.objects.all()
    orders    = PurchaseOrder.objects.filter(status='pending')

    # Stock counts done in Python to avoid SQLite F() issues
    all_p          = list(products.values('quantity', 'minimum_stock'))
    low_stock_count = sum(1 for p in all_p if p['quantity'] < p['minimum_stock'])
    low_stock_list  = [
        p for p in products
        if p.quantity < p.minimum_stock
    ]

    # Open backlog summary
    open_backlog_count = BacklogEntry.objects.filter(quantity_on_backlog__gt=0).count()

    context = {
        'total_products':    products.count(),
        'total_suppliers':   suppliers.count(),
        'total_orders':      orders.count(),
        'low_stock_products': low_stock_count,
        'low_stock_list':    low_stock_list,
        'open_backlog_count': open_backlog_count,
        'recent_orders':     orders.order_by('-id')[:5],
        'total_stock_value': sum(p.price * max(p.quantity, 0) for p in products),
    }
    return render(request, 'inventory_manager/dashboard.html', context)


# ─────────────────────────────────────────────
# BACKLOG LIST (inventory manager view)
# ─────────────────────────────────────────────

@login_required
@manager_required
def backlog_list(request):
    open_backlogs = (
        BacklogEntry.objects.filter(quantity_on_backlog__gt=0)
        .select_related('product')
        .order_by('created_at')
    )
    return render(request, 'inventory_manager/backlog_list.html', {
        'open_backlogs': open_backlogs,
    })


# ─────────────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────────────

@login_required
@manager_required
def product_list(request):
    return render(request, 'inventory_manager/product_list.html',
                  {'products': Product.objects.all()})


@login_required
@manager_required
def product_add(request):
    form = ProductForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('inventory_manager:product_list')
    return render(request, 'inventory_manager/product_add.html', {'form': form})


@login_required
@manager_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if form.is_valid():
        form.save()
        return redirect('inventory_manager:product_detail', pk=pk)
    return render(request, 'inventory_manager/product_edit.html',
                  {'form': form, 'product': product})


@login_required
@manager_required
def product_detail(request, pk):
    product   = get_object_or_404(Product, pk=pk)
    backlogs  = BacklogEntry.objects.filter(
        product=product, quantity_on_backlog__gt=0
    )
    return render(request, 'inventory_manager/product_details.html', {
        'product':  product,
        'backlogs': backlogs,
    })


@login_required
@manager_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        return redirect('inventory_manager:product_list')
    return render(request, 'inventory_manager/product_delete.html',
                  {'product': product})


# ─────────────────────────────────────────────
# SUPPLIERS
# ─────────────────────────────────────────────

@login_required
@manager_required
def supplier_list(request):
    suppliers   = Supplier.objects.all()
    total_spend = 0
    for s in suppliers:
        orders          = s.purchaseorder_set.all()
        s.total_orders  = orders.count()
        s.total_spend   = sum(o.total_amount for o in orders)
        s.last_order_date = (
            orders.order_by('-order_date').first().order_date
            if orders.exists() else None
        )
        total_spend += s.total_spend

    context = {
        'suppliers':          suppliers,
        'total_suppliers':    suppliers.count(),
        'active_suppliers':   suppliers.filter(status='active').count(),
        'inactive_suppliers': suppliers.filter(status='inactive').count(),
        'total_spend':        total_spend / 1000 if total_spend else 0,
    }
    return render(request, 'inventory_manager/supplier_list.html', context)


@login_required
@manager_required
def supplier_add(request):
    form = SupplierForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('inventory_manager:supplier_list')
    return render(request, 'inventory_manager/supplier_add.html', {'form': form})


@login_required
@manager_required
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=supplier)
    if form.is_valid():
        form.save()
        return redirect('inventory_manager:supplier_detail', pk=pk)
    return render(request, 'inventory_manager/supplier_edit.html',
                  {'form': form, 'supplier': supplier})


@login_required
@manager_required
def supplier_detail(request, pk):
    supplier  = get_object_or_404(Supplier, pk=pk)
    orders    = PurchaseOrder.objects.filter(supplier=supplier).order_by('-order_date')
    delivered = orders.filter(status='delivered').count()
    total     = orders.count()
    context = {
        'supplier':              supplier,
        'recent_orders':         orders[:5],
        'total_orders':          total,
        'total_spend':           sum(o.total_amount for o in orders),
        'on_time_delivery_rate': round((delivered / total) * 100, 1) if total else 0,
    }
    return render(request, 'inventory_manager/supplier_details.html', context)


@login_required
@manager_required
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        supplier.delete()
        return redirect('inventory_manager:supplier_list')
    return render(request, 'inventory_manager/supplier_confirm_delete.html',
                  {'supplier': supplier})


# ─────────────────────────────────────────────
# PURCHASE ORDERS
# ─────────────────────────────────────────────

@login_required
@manager_required
def purchase_order_list(request):
    return render(request, 'inventory_manager/purchase_order_list.html', {
        'purchase_orders': PurchaseOrder.objects.all().order_by('-id'),
    })


@login_required
@manager_required
def purchase_order_create(request):
    form    = PurchaseOrderForm(request.POST or None)
    formset = PurchaseOrderItemFormSet(request.POST or None)

    if form.is_valid() and formset.is_valid():
        po = form.save()
        formset.instance = po
        formset.save()

        if po.status == 'delivered':
            _fulfil_backlog_after_delivery(po)
            messages.success(
                request,
                f"PO-{po.id} created as delivered. Stock updated and backlog fulfilled."
            )
        else:
            messages.success(request, f"Purchase order PO-{po.id} created.")

        return redirect('inventory_manager:purchase_order_list')

    return render(request, 'inventory_manager/purchase_order_create.html',
                  {'form': form, 'formset': formset})


@transaction.atomic
@login_required
@manager_required
def purchase_order_edit(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)

    if po.status == 'delivered':
        messages.error(request, "Delivered purchase orders cannot be edited.")
        return redirect('inventory_manager:purchase_order_detail', pk=po.pk)

    old_status = po.status

    if request.method == 'POST':
        form    = PurchaseOrderForm(request.POST, instance=po)
        formset = PurchaseOrderItemFormSet(request.POST, instance=po)

        if form.is_valid() and formset.is_valid():
            new_status = form.cleaned_data.get('status')

            # Can only mark delivered after ordered
            if new_status == 'delivered' and old_status != 'ordered':
                form.add_error(
                    'status',
                    "An order can only be marked as delivered after it has been ordered."
                )
                return render(request, 'inventory_manager/purchase_order_edit.html', {
                    'form': form, 'formset': formset, 'purchase_order': po,
                })

            po = form.save()
            formset.save()

            # Auto-set expected_delivery when pending → ordered
            if old_status == 'pending' and po.status == 'ordered' \
                    and not po.expected_delivery:
                po.expected_delivery = po.order_date + timedelta(days=5)
                po.save()

            # ── DELIVER: add stock + fulfil backlog ───────────
            if old_status != 'delivered' and po.status == 'delivered':
                _fulfil_backlog_after_delivery(po)
                messages.success(
                    request,
                    f"PO-{po.id} marked as delivered. "
                    f"Stock updated and backlog fulfilled where possible."
                )
            else:
                messages.success(request, "Purchase order updated.")

            return redirect('inventory_manager:purchase_order_detail', pk=po.pk)

    else:
        form    = PurchaseOrderForm(instance=po)
        formset = PurchaseOrderItemFormSet(instance=po)

    return render(request, 'inventory_manager/purchase_order_edit.html', {
        'form': form, 'formset': formset, 'purchase_order': po,
    })


@login_required
@manager_required
def purchase_order_detail(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    return render(request, 'inventory_manager/purchase_order_details.html',
                  {'purchase_order': po})


@login_required
@manager_required
def purchase_order_delete(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == 'POST':
        po.delete()
        return redirect('inventory_manager:purchase_order_list')
    return render(request, 'inventory_manager/purchase_order_delete.html',
                  {'purchase_order': po})
