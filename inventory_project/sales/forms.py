from django.forms import ModelForm, inlineformset_factory
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
        fields = ['customer', 'order_date', 'payment_method', 'shipping_method', 'notes', 'shipping_cost','status','tax_rate']

# This allows adding multiple products to one order
OrderItemFormSet = inlineformset_factory(
    SalesOrder, 
    SalesOrderItem,
    fields=('product', 'quantity', 'unit_price'),
    extra=1,
    can_delete=True,
)