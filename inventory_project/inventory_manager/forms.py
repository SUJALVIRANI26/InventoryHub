from django import forms
from django.forms import inlineformset_factory
from .models import Product, Supplier, PurchaseOrder, PurchaseOrderItem


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = '__all__'


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = '__all__'
        widgets = {
            'order_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'expected_delivery': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
        }

PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    fields=('product', 'quantity', 'unit_price'),
    extra=1,
    can_delete=True
)
