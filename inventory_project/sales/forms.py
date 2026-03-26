from django.forms import ModelForm, inlineformset_factory, BaseInlineFormSet
from django import forms
from .models import Customer, SalesOrder, SalesOrderItem, get_sales_unit_price


class CustomerForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone'].required = True

    class Meta:
        model = Customer
        fields = [
            'name', 'email', 'phone', 'company',
            'address_line1', 'address_line2', 'city', 'state', 'zip_code', 'country',
            'customer_since', 'status', 'customer_type', 'tax_id', 'notes',
        ]


class SalesOrderForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance and instance.pk:
            # Called from `sales.views.sales_order_form()` while rendering the
            # create/edit order page. This affects the status dropdown shown in
            # `templates/sales/sales_order_form.html`.
            #
            # If the order still has backlog, keep only `pending` and
            # `cancelled` in the frontend dropdown. Backend validation in
            # `sales/views.py` still enforces the rule even if the request is
            # manually modified.
            has_backlog = SalesOrderItem.objects.filter(
                sales_order=instance,
                backordered_qty__gt=0,
            ).exists()
            if has_backlog:
                self.fields['status'].choices = [
                    choice for choice in self.fields['status'].choices
                    if choice[0] in ('pending', 'cancelled')
                ]

    class Meta:
        model = SalesOrder
        fields = ['customer', 'order_date', 'payment_method', 'shipping_method',
                  'notes', 'shipping_cost', 'status', 'tax_rate']


class SalesOrderItemForm(ModelForm):
    class Meta:
        model = SalesOrderItem
        fields = ('product', 'quantity', 'unit_price')
        widgets = {
            'unit_price': forms.NumberInput(attrs={
                'step': '0.01', 'min': '0',
                'class': 'unit-price-input', 'readonly': 'readonly',
            }),
            'product': forms.Select(attrs={'class': 'product-select form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        # Always lock unit_price to the sales markup price server-side so
        # frontend edits cannot bypass the 5% increment rule.
        if product:
            cleaned_data['unit_price'] = get_sales_unit_price(product.price)
        return cleaned_data
        # ← NOTE: NO stock check here.
        #   Stock is allowed to go negative (backlog). The model layer
        #   handles deduction and auto-PO creation.


class OrderItemBaseFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        # ← Intentionally no stock validation.
        #   Orders are ALWAYS allowed through regardless of available stock.
        #   If stock is insufficient, sales/models.py will:
        #     1. Allow quantity to go negative on the Product
        #     2. Create a BacklogEntry for the shortfall
        #     3. Auto-create a pending PurchaseOrder to replenish
        #
        #   The JS in sales_order_form.html shows a non-blocking WARNING
        #   to the user when stock is low, but does not prevent submission.


OrderItemFormSet = inlineformset_factory(
    SalesOrder,
    SalesOrderItem,
    form=SalesOrderItemForm,
    extra=0,
    can_delete=True,
    formset=OrderItemBaseFormSet,
)
