from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import F
from .models import *
from .forms import *


# ================= DASHBOARD =================
def dashboard(request):
    products = Product.objects.all()
    suppliers = Supplier.objects.all()
    orders = PurchaseOrder.objects.all()

    context = {
        'total_products': products.count(),
        'total_suppliers': suppliers.count(),
        'total_orders': orders.count(),
        'low_stock_products': products.filter(quantity__lte=F('minimum_stock')).count(),
        'low_stock_list': products.filter(quantity__lte=F('minimum_stock')),
        'recent_orders': orders.order_by('-id')[:5],
        'total_stock_value': sum(p.price * p.quantity for p in products),
    }

    return render(request, 'inventory_manager/dashboard.html', context)


# ================= PRODUCT =================
def product_list(request):
    return render(request, 'inventory_manager/product_list.html',
                  {'products': Product.objects.all()})


def product_add(request):
    form = ProductForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('inventory_manager:product_list')
    return render(request, 'inventory_manager/product_add.html', {'form': form})


def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if form.is_valid():
        form.save()
        return redirect('inventory_manager:product_detail', pk=pk)
    return render(request, 'inventory_manager/product_edit.html',
                  {'form': form, 'product': product})


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'inventory_manager/product_details.html',
                  {'product': product})


def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        product.delete()
        return redirect('inventory_manager:product_list')
    return render(request, 'inventory_manager/product_delete.html',
                  {'product': product})


# ================= SUPPLIER =================

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



def supplier_add(request):
    form = SupplierForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('inventory_manager:supplier_list')
    return render(request, 'inventory_manager/supplier_add.html', {'form': form})


def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=supplier)
    if form.is_valid():
        form.save()
        return redirect('inventory_manager:supplier_detail', pk=pk)
    return render(request, 'inventory_manager/supplier_edit.html',
                  {'form': form, 'supplier': supplier})


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



def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST":
        supplier.delete()
        return redirect('inventory_manager:supplier_list')
    return render(request, 'inventory_manager/supplier_confirm_delete.html',
                  {'supplier': supplier})


# ================= PURCHASE ORDER =================
def purchase_order_list(request):
    return render(request, 'inventory_manager/purchase_order_list.html',
                  {'purchase_orders': PurchaseOrder.objects.all()})


def purchase_order_create(request):
    form = PurchaseOrderForm(request.POST or None)
    formset = PurchaseOrderItemFormSet(request.POST or None)

    if form.is_valid() and formset.is_valid():
        po = form.save()
        formset.instance = po
        formset.save()
        return redirect('inventory_manager:purchase_order_list')

    return render(request, 'inventory_manager/purchase_order_create.html',
                  {'form': form, 'formset': formset})


def purchase_order_edit(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    form = PurchaseOrderForm(request.POST or None, instance=po)
    formset = PurchaseOrderItemFormSet(request.POST or None, instance=po)

    if form.is_valid() and formset.is_valid():
        form.save()
        formset.save()
        return redirect('inventory_manager:purchase_order_detail', pk=pk)

    return render(request, 'inventory_manager/purchase_order_edit.html',
                  {'form': form, 'formset': formset, 'purchase_order': po})


def purchase_order_detail(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    return render(request, 'inventory_manager/purchase_order_details.html',
                  {'purchase_order': po})


def purchase_order_delete(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == "POST":
        po.delete()
        return redirect('inventory_manager:purchase_order_list')
    return render(request, 'inventory_manager/purchase_order_delete.html',
                  {'purchase_order': po})
