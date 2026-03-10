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
    Item form where price is read-only; actual value is
    enforced in the model based on the selected product.
    """
    class Meta:
        model = SalesOrderItem
        fields = ('product', 'quantity', 'unit_price')
        widgets = {
            'unit_price': forms.NumberInput(attrs={'readonly': 'readonly'}),
        }


class OrderItemBaseFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            unit_price = form.cleaned_data.get("unit_price")

            # Basic guard so price is not negative in UI;
            # the actual value is overwritten in the model.
            if unit_price is not None and unit_price < 0:
                raise forms.ValidationError("Unit price cannot be negative.")


# This allows adding multiple products to one order
OrderItemFormSet = inlineformset_factory(
    SalesOrder,
    SalesOrderItem,
    form=SalesOrderItemForm,
    extra=1,
    can_delete=True,
    formset=OrderItemBaseFormSet,
)