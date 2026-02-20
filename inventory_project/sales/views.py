from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.contrib import messages

from .forms import OrderItemFormSet, SalesOrderForm, CustomerForm
from .models import SalesOrder, Customer
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout


@login_required
def dashboard(request):
    return render(request, 'sales/dashboard.html')

@login_required
def products(request):
    return render(request, 'sales/product_list.html')

@login_required
def product_form(request, pk=None):
    # You'll need to create a ProductForm
    context = {}
    if pk:
        # Edit existing product
        pass
    return render(request, 'sales/product_form.html', context)

@login_required
def sales_order_form(request, pk=None):
    if pk:
        order = get_object_or_404(SalesOrder, pk=pk)
    else:
        order = SalesOrder()   # ✅ create empty instance

    if request.method == 'POST':
        form = SalesOrderForm(request.POST, instance=order)
        formset = OrderItemFormSet(request.POST, instance=order)

        if form.is_valid() and formset.is_valid():
            order = form.save(commit=False)
            order.subtotal  = 0
            order.total_amount = order.shipping_cost or 0
            order.save()

            formset.instance = order
            formset.save()

            order.calculate_totals()
            order.save()

            messages.success(request, 'Sales order saved successfully!')
            return redirect('sales_order_detail', pk=order.pk)
    else:
        form = SalesOrderForm(instance=order)
        formset = OrderItemFormSet(instance=order)

    return render(request, 'sales/sales_order_form.html', {
        'form': form,
        'formset': formset
    })



@login_required
def sales_order(request):
    orders = SalesOrder.objects.all().order_by('-order_date')
    return render(request, 'sales/sales_order_list.html', {'orders': orders})

@login_required
def sales_order_detail(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    return render(request, 'sales/sales_order_detail.html', {'order': order})


@login_required
def customer(request):
    customers = Customer.objects.all().order_by('-customer_since')
    return render(request, 'sales/customer.html', {'customers': customers})

@login_required
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
            # messages.success(request, 'Customer saved successfully!')
            return redirect('customers')
    
    today = timezone.now().date()
    return render(request, 'sales/customer_form.html', {
        'form': form,
        'today': today
    })

@login_required
def invoices(request):
    return render(request, 'sales/invoices.html')

@login_required
def invoice_form(request, pk=None):
    return render(request, 'sales/invoice_form.html')


@login_required
def invoice_print(request, pk):
    # You'll need an Invoice model
    return render(request, 'sales/invoice_print.html')
@login_required
def setting(request):
    return render(request, 'sales/settings.html')

# @login_required
# def logout_user(request):
#     logout(request)
#     return redirect('login')