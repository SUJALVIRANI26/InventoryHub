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


class PurchaseOrderItemForm(forms.ModelForm):
    """
    Enforce that PO item unit_price cannot be changed by managers.
    Unit price is always derived from Product.price on the server.
    """

    class Meta:
        model = PurchaseOrderItem
        fields = ("product", "quantity", "unit_price")
        widgets = {
            # User can still submit a value (readonly will prevent edits in normal UI),
            # but we ALSO override it server-side in `clean()`.
            "unit_price": forms.NumberInput(
                attrs={"readonly": "readonly", "step": "0.01"}
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Allow leaving these blank in the UI; server-side clean() will fill/validate.
        self.fields["unit_price"].required = False
        self.fields["quantity"].required = False

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        quantity = cleaned_data.get("quantity")

        # If product is not chosen, let the form be treated as empty by the formset.
        if not product:
            return cleaned_data

        # ✅ Price lock: always force PO item price to match the product's base price.
        cleaned_data["unit_price"] = product.price

        # ✅ If manager didn't provide quantity, auto-suggest for low stock items.
        if quantity in (None, "", 0):
            if product.is_low_stock():
                cleaned_data["quantity"] = max(product.minimum_stock - product.quantity, 1)
            else:
                self.add_error("quantity", "Quantity is required for this product.")

        return cleaned_data


PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    fields=("product", "quantity", "unit_price"),
    extra=1,
    can_delete=True,
)
