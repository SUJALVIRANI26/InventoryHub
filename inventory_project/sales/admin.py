from django.contrib import admin
from .models import *

admin.site.register(Customer)
admin.site.register(SalesOrder)
admin.site.register(SalesOrderItem)

# Register your models here.
