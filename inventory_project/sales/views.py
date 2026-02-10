from django.shortcuts import render
from django.http import HttpResponse

def dashboard(request):
    return render(request,'sales/dashboard.html')

def products(request):
    return HttpResponse("We are currently building this feature. Check back soon!")

def sales_order(request):
    return HttpResponse("We are currently building this feature. Check back soon!")

def customer(request):
    return HttpResponse("We are currently building this feature. Check back soon!")

def invoices(request):
    return HttpResponse("We are currently building this feature. Check back soon!")

def setting(request):
    return HttpResponse("We are currently building this feature. Check back soon!")




# Create your views here.
