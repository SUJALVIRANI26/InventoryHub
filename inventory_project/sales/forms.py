from django.forms import ModelForm, inlineformset_factory, BaseInlineFormSet
from django import forms
from .models import Customer, SalesOrder, SalesOrderItem


class CustomerForm(ModelForm):
    class Meta:
        model = Customer
        fields = [
            'name', 'email', 'phone', 'company',
            'address_line1', 'address_line2', 'city', 'state', 'zip_code', 'country',
            'customer_since', 'status', 'customer_type', 'tax_id', 'notes'
        ]


class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = ['customer', 'order_date', 'payment_method', 'shipping_method', 'notes', 'shipping_cost', 'status', 'tax_rate']


class SalesOrderItemForm(ModelForm):
    """
    Item form where price is locked to the product's base price.
    """
    class Meta:
        model = SalesOrderItem
        fields = ('product', 'quantity', 'unit_price')
        widgets = {
            'unit_price': forms.NumberInput(attrs={
                'step': '0.01', 
                'min': '0',
                'class': 'unit-price-input',
                'readonly': 'readonly',
            }),
            'product': forms.Select(attrs={
                'class': 'product-select'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add a data attribute to each product option with its price
        if self.fields['product'].queryset.exists():
            self.fields['product'].choices = [
                (product.id, f"{product.name} (${product.price})") 
                for product in self.fields['product'].queryset
            ]
    
    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        
        # Always lock unit_price to the product's base price on the server side
        if product:
            cleaned_data['unit_price'] = product.price
        
        return cleaned_data


class OrderItemBaseFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        # Only enforce stock limits when creating a brand new order.
        # For edits, we assume existing reservations are already reflected in stock.
        enforce_stock_limits = self.instance.pk is None

        # Track total requested quantity per product for this new order
        product_requested_quantities = {}

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            unit_price = form.cleaned_data.get("unit_price")
            product = form.cleaned_data.get("product")
            quantity = form.cleaned_data.get("quantity") or 0

            # Ensure we don't order more than available stock when creating a new order
            if enforce_stock_limits and product and quantity:
                current_total = product_requested_quantities.get(product.pk, 0)
                new_total = current_total + quantity

                if new_total > product.quantity:
                    raise forms.ValidationError(
                        f"Not enough stock for {product.name}. "
                        f"Available: {product.quantity}, requested: {new_total}."
                    )

                product_requested_quantities[product.pk] = new_total


# This allows adding multiple products to one order
OrderItemFormSet = inlineformset_factory(
    SalesOrder,
    SalesOrderItem,
    form=SalesOrderItemForm,
    extra=0,
    can_delete=True,
    formset=OrderItemBaseFormSet,
)