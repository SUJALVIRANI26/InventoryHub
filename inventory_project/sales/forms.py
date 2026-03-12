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
                'class': 'product-select form-control'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set the product choices with data-price attributes
        if self.fields['product'].queryset.exists():
            choices = []
            for product in self.fields['product'].queryset:
                choices.append((
                    product.id, 
                    f"{product.name} (${product.price})"
                ))
            self.fields['product'].choices = choices
            
            # Add data-price attribute to each option for JavaScript
            self.fields['product'].widget.choices = self.fields['product'].choices
    
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

        # Track total requested quantity per product for this order
        product_requested_quantities = {}

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            product = form.cleaned_data.get("product")
            quantity = form.cleaned_data.get("quantity") or 0

            if product and quantity:
                current_total = product_requested_quantities.get(product.pk, 0)
                new_total = current_total + quantity

                # For existing orders, consider current quantity
                if self.instance.pk:
                    existing_items = SalesOrderItem.objects.filter(
                        sales_order=self.instance,
                        product=product
                    )
                    existing_qty = existing_items.first().quantity if existing_items.exists() else 0
                    net_change = quantity - existing_qty
                    
                    if net_change > product.quantity:
                        form.add_error('quantity', 
                            f"Cannot add {net_change} more of {product.name}. Only {product.quantity} available in stock."
                        )
                else:
                    # For new orders
                    if new_total > product.quantity:
                        form.add_error('quantity', 
                            f"Not enough stock for {product.name}. Available: {product.quantity}, requested: {new_total}."
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