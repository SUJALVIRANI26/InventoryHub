from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import F
from django.contrib.auth.decorators import login_required
from accounts.decorators import manager_required
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import *
from .forms import *


def _build_po_product_defaults():
    defaults = {}
    for product in Product.objects.all():
        defaults[str(product.id)] = {
            "price": float(product.price),
            "is_low_stock": product.is_low_stock(),
            "recommended_quantity": max(product.minimum_stock - product.quantity, 1),
        }
    return defaults


# ================= DASHBOARD =================
@login_required
@manager_required
def dashboard(request):
    products = Product.objects.all()
    suppliers = Supplier.objects.all()
    # Show only pending purchase orders on the dashboard
    orders = PurchaseOrder.objects.filter(status='pending')

    context = {
        'total_products': products.count(),
        'total_suppliers': suppliers.count(),
        'total_orders': orders.count(),
        'low_stock_products': products.filter(quantity__lt=F('minimum_stock')).count(),
        'low_stock_list': products.filter(quantity__lt=F('minimum_stock')),
        'recent_orders': orders.order_by('-id')[:5],
        'total_stock_value': sum(p.price * p.quantity for p in products),
    }
    return render(request, 'inventory_manager/dashboard.html', context)


# ================= PRODUCT =================
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
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'inventory_manager/product_details.html',
                  {'product': product})

@login_required
@manager_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        product.delete()
        return redirect('inventory_manager:product_list')
    return render(request, 'inventory_manager/product_delete.html',
                  {'product': product})


# ================= SUPPLIER =================
@login_required
@manager_required
def supplier_list(request):

    suppliers = Supplier.objects.all()

    total_suppliers = suppliers.count()
    active_suppliers = suppliers.filter(status='active').count()
    inactive_suppliers = suppliers.filter(status='inactive').count()

    total_spend = 0

    for supplier in suppliers:
        orders = supplier.purchaseorder_set.all()
        supplier.total_orders = orders.count()
        supplier.total_spend = sum(o.total_amount for o in orders)
        supplier.last_order_date = orders.order_by('-order_date').first().order_date if orders.exists() else None

        total_spend += supplier.total_spend

    context = {
        "suppliers": suppliers,
        "total_suppliers": total_suppliers,
        "active_suppliers": active_suppliers,
        "inactive_suppliers": inactive_suppliers,
        "total_spend": total_spend / 1000 if total_spend else 0,
    }

    return render(request, "inventory_manager/supplier_list.html", context)


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

    supplier = get_object_or_404(Supplier, pk=pk)

    # Get all purchase orders for this supplier
    orders = PurchaseOrder.objects.filter(
        supplier=supplier
    ).order_by('-order_date')

    # Calculate totals
    total_orders = orders.count()

    total_spend = sum(
        order.total_amount for order in orders
    )

    # Example delivery rate (you can improve later)
    delivered_orders = orders.filter(status='delivered').count()
    on_time_delivery_rate = 0
    if total_orders > 0:
        on_time_delivery_rate = round((delivered_orders / total_orders) * 100, 1)

    context = {
        'supplier': supplier,
        'recent_orders': orders[:5],  # IMPORTANT
        'total_orders': total_orders,
        'total_spend': total_spend,
        'on_time_delivery_rate': on_time_delivery_rate,
    }

    return render(
        request,
        'inventory_manager/supplier_details.html',
        context
    )


@login_required
@manager_required
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST":
        supplier.delete()
        return redirect('inventory_manager:supplier_list')
    return render(request, 'inventory_manager/supplier_confirm_delete.html',
                  {'supplier': supplier})


# ================= PURCHASE ORDER =================
@login_required
@manager_required
def purchase_order_list(request):
    # Show all purchase orders in the list view
    return render(request, 'inventory_manager/purchase_order_list.html',
                  {'purchase_orders': PurchaseOrder.objects.all()})

@login_required
@manager_required
def purchase_order_create(request):
    form = PurchaseOrderForm(request.POST or None)
    formset = PurchaseOrderItemFormSet(request.POST or None)

    if form.is_valid() and formset.is_valid():
        po = form.save()
        formset.instance = po
        formset.save()

        if po.status == "delivered":
            for item in po.items.all():
                product = item.product
                product.quantity += item.quantity
                product.save()
        return redirect('inventory_manager:purchase_order_list')

    product_defaults = _build_po_product_defaults()
    return render(request, 'inventory_manager/purchase_order_create.html',
                  {'form': form, 'formset': formset, 'product_defaults': product_defaults})

@transaction.atomic
@login_required
@manager_required
def purchase_order_edit(request, pk):
    purchase_order = get_object_or_404(PurchaseOrder, pk=pk)

    # Once delivered, the order cannot be edited
    if purchase_order.status == "delivered":
        messages.error(request, "Delivered purchase orders cannot be edited.")
        return redirect("inventory_manager:purchase_order_detail", pk=purchase_order.pk)

    old_status = purchase_order.status

    if request.method == "POST":
        form = PurchaseOrderForm(request.POST, instance=purchase_order)
        formset = PurchaseOrderItemFormSet(request.POST, instance=purchase_order)

        if form.is_valid() and formset.is_valid():

            new_status = form.cleaned_data.get("status")
            # Only allow Delivered if the order is already in Ordered state
            if new_status == "delivered" and old_status != "ordered":
                form.add_error("status", "You can mark an order as delivered only after it has been ordered.")
                return render(request, "inventory_manager/purchase_order_edit.html", {
                    "form": form,
                    "formset": formset,
                    "purchase_order": purchase_order,
                    "product_defaults": _build_po_product_defaults(),
                })

            purchase_order = form.save()

            items = formset.save()

            # If status changed from pending to ordered and no expected_delivery, set to 5 days after order_date
            if old_status == "pending" and purchase_order.status == "ordered" and not purchase_order.expected_delivery:
                purchase_order.expected_delivery = purchase_order.order_date + timedelta(days=5)
                purchase_order.save()

            # ✅ STOCK UPDATE LOGIC HERE
            if old_status != "delivered" and purchase_order.status == "delivered":

                for item in purchase_order.items.all():
                    product = item.product
                    product.quantity += item.quantity
                    product.save()

            return redirect("inventory_manager:purchase_order_detail", pk=purchase_order.pk)

    else:
        form = PurchaseOrderForm(instance=purchase_order)
        formset = PurchaseOrderItemFormSet(instance=purchase_order)

    return render(request, "inventory_manager/purchase_order_edit.html", {
        "form": form,
        "formset": formset,
        "purchase_order": purchase_order,
        "product_defaults": _build_po_product_defaults(),
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
    if request.method == "POST":
        po.delete()
        return redirect('inventory_manager:purchase_order_list')
    return render(request, 'inventory_manager/purchase_order_delete.html',
                  {'purchase_order': po})


