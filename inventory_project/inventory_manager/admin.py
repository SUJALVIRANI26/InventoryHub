from django.contrib import admin
from .models import Supplier, Product, Category, PurchaseOrder, PurchaseOrderItem

admin.site.register(Supplier)
admin.site.register(Product)
admin.site.register(Category)
admin.site.register(PurchaseOrder)
admin.site.register(PurchaseOrderItem)
