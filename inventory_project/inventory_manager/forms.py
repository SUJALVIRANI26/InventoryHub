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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only allow ordering from active suppliers
        self.fields["supplier"].queryset = Supplier.objects.filter(status="active")

    def clean_supplier(self):
        supplier = self.cleaned_data["supplier"]
        if supplier.status != "active":
            raise forms.ValidationError("You can create purchase orders only for active suppliers.")
        return supplier

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
