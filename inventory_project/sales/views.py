from django.shortcuts import render
from django.http import HttpResponse
from django.utils import timezone
import datetime

def dashboard(request):
    return render(request,'sales/dashboard.html')

def products(request):
    return render(request,'sales/product_list.html')

def product_form(request):
    return render(request,'sales/product_form.html')

def sales_order(request):
    return render(request,'sales/sales_order_list.html')

def sales_order_form(request):
    return render(request,'sales/sales_order_form.html')

def sales_order_detail(request):
    return render(request,'sales/sales_order_detail.html')

def customer(request):
    return  render(request,'sales/customer.html')

def customer_form(request):
    today = timezone.now().date()
    return render(request,'sales/customer_form.html',{"today" : today})

def invoices(request):
    return render(request,'sales/invoices.html')

def invoice_form(request):
    return render(request,'sales/invoice_form.html')

def invoice_print(request):
    return render(request,'sales/invoice_print.html')
def setting(request):
    return render(request,'sales/settings.html')




# Create your views here.
