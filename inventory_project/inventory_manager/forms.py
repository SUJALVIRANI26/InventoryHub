from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import (
    Product, Category, Supplier, PurchaseOrder, PurchaseOrderItem,
    StockMovement, StockAlert
)
import csv
import io

# ---------------------------
# Product Forms
# ---------------------------
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'category', 'brand', 'description',
            'price', 'cost_price', 'quantity', 'min_stock_level',
            'reorder_point', 'supplier', 'status'  # ✅ No image fields
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter product name'}),
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., SKU-001'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter brand name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Enter product description...'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'min_stock_level': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '5'}),
            'reorder_point': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '10'}),
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.all().order_by('name')
        self.fields['supplier'].queryset = Supplier.objects.filter(status='active').order_by('name')
        self.fields['supplier'].empty_label = "-- Select Supplier --"
        self.fields['category'].empty_label = "-- Select Category --"

    def clean_sku(self):
        sku = self.cleaned_data['sku']
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            if Product.objects.filter(sku=sku).exclude(pk=instance.pk).exists():
                raise ValidationError('This SKU already exists.')
        else:
            if Product.objects.filter(sku=sku).exists():
                raise ValidationError('This SKU already exists.')
        return sku.upper()

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price and price <= 0:
            raise ValidationError('Price must be greater than zero.')
        return price


class ProductImportForm(forms.Form):
    file = forms.FileField(
        label='CSV File',
        help_text='Upload a CSV file with product data.',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv'})
    )
    update_existing = forms.BooleanField(
        label='Update existing products',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean_file(self):
        file = self.cleaned_data['file']
        if not file.name.endswith('.csv'):
            raise ValidationError('Please upload a CSV file.')
        
        if file.size > 10 * 1024 * 1024:
            raise ValidationError('File size must be less than 10MB.')
        
        # Validate CSV structure
        try:
            file.seek(0)
            reader = csv.reader(io.TextIOWrapper(file, encoding='utf-8'))
            headers = next(reader)
            required_fields = ['product_name', 'sku']
            for field in required_fields:
                if field not in headers:
                    raise ValidationError(f'CSV must contain "{field}" column.')
        except Exception as e:
            raise ValidationError(f'Invalid CSV file: {str(e)}')
        
        file.seek(0)
        return file


# ---------------------------
# Purchase Order Forms
# ---------------------------
class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = [
            'supplier', 'order_date', 'expected_delivery',
            'shipping_method', 'payment_terms', 'status',
            'shipping_cost', 'tax_rate', 'notes', 'tracking_number'
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'order_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expected_delivery': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'shipping_method': forms.Select(attrs={'class': 'form-control'}),
            'payment_terms': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'shipping_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '10.00'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Add any special instructions...'}),
            'tracking_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter tracking number'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.filter(status='active').order_by('name')
        self.fields['supplier'].empty_label = "-- Select Supplier --"
        
        # Set default dates
        if not self.instance.pk:
            self.fields['order_date'].initial = timezone.now().date()
            self.fields['expected_delivery'].initial = timezone.now().date() + timezone.timedelta(days=7)

    def clean_expected_delivery(self):
        order_date = self.cleaned_data.get('order_date')
        expected_delivery = self.cleaned_data.get('expected_delivery')
        
        if order_date and expected_delivery and expected_delivery < order_date:
            raise ValidationError('Expected delivery date cannot be before order date.')
        
        return expected_delivery

class PurchaseOrderItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ['product', 'quantity', 'unit_price']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control product-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Qty'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Price'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(status='active').order_by('name')
        self.fields['product'].label_from_instance = lambda obj: f"{obj.name} ({obj.sku}) - ${obj.price}"
        self.fields['product'].empty_label = "-- Select Product --"
        
        # Make fields required
        self.fields['product'].required = True
        self.fields['quantity'].required = True
        self.fields['unit_price'].required = True

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        unit_price = cleaned_data.get('unit_price')
        
        # Auto-populate unit price from product if not provided
        if product and not unit_price:
            cleaned_data['unit_price'] = product.price
        
        return cleaned_data
    
PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder,  # Parent model
    PurchaseOrderItem,  # Child model
    form=PurchaseOrderItemForm,  # Form to use
    extra=1,  # Number of empty forms
    can_delete=True,  # Allow deletion
    min_num=1,  # Minimum forms required
    validate_min=True,  # Validate minimum
    fields=['product', 'quantity', 'unit_price']  # Fields to include
)

# ---------------------------
# Stock Movement Forms
# ---------------------------
class StockUpdateForm(forms.Form):
    UPDATE_TYPES = [
        ('add', 'Add Stock (Increase)'),
        ('remove', 'Remove Stock (Decrease)'),
        ('set', 'Set to Specific Quantity'),
    ]

    REASONS = [
        ('purchase', 'Purchase Order Received'),
        ('sale', 'Sales Order Fulfilled'),
        ('return', 'Customer Return'),
        ('damage', 'Damaged Goods'),
        ('adjustment', 'Stock Adjustment'),
        ('other', 'Other'),
    ]

    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_product'}),
        empty_label="-- Select Product --"
    )
    update_type = forms.ChoiceField(
        choices=UPDATE_TYPES,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_update_type'})
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter quantity', 'id': 'id_quantity'})
    )
    reason = forms.ChoiceField(
        choices=REASONS,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_reason'})
    )
    reference = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., PO-2023-001', 'id': 'id_reference'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Add any additional notes...', 'id': 'id_notes'})
    )

    def clean(self):
        cleaned_data = super().clean()
        update_type = cleaned_data.get('update_type')
        quantity = cleaned_data.get('quantity')
        product = cleaned_data.get('product')
        
        if update_type == 'remove' and product and quantity:
            if quantity > product.quantity:
                raise ValidationError(f'Cannot remove {quantity} units. Only {product.quantity} units in stock.')
        
        return cleaned_data


class StockAdjustmentForm(forms.Form):
    csv_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control-file', 'accept': '.csv', 'id': 'csvFile'})
    )
    notify = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean_csv_file(self):
        file = self.cleaned_data.get('csv_file')
        if file and not file.name.endswith('.csv'):
            raise ValidationError('Please upload a CSV file.')
        return file


# ---------------------------
# Supplier Forms
# ---------------------------
class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            'name', 'supplier_code', 'category', 'status',
            'contact_person', 'contact_title', 'email', 'phone', 'website',
            'address', 'city', 'state', 'zip_code', 'country',
            'payment_terms', 'credit_limit', 'tax_id', 'preferred_currency',
            'min_order_value', 'lead_time_days', 'notes', 'is_verified', 'is_preferred'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter company name'}),
            'supplier_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Auto-generated if empty'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'contact_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Sales Manager'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@company.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 (555) 123-4567'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.company.com'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123 Main Street'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State/Province'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ZIP/Postal Code'}),
            'country': forms.Select(attrs={'class': 'form-control'}),
            'payment_terms': forms.Select(attrs={'class': 'form-control'}),
            'credit_limit': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tax identification number'}),
            'preferred_currency': forms.Select(attrs={'class': 'form-control'}),
            'min_order_value': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'lead_time_days': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Days'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Add any additional notes...'}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_preferred': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.all().order_by('name')
        self.fields['category'].empty_label = "-- Select Category --"
        
        # Make supplier_code optional
        self.fields['supplier_code'].required = False
        
        # Set country choices
        self.fields['country'].widget = forms.Select(choices=[
            ('', '-- Select Country --'),
            ('United States', 'United States'),
            ('Canada', 'Canada'),
            ('United Kingdom', 'United Kingdom'),
            ('Australia', 'Australia'),
            ('Germany', 'Germany'),
            ('France', 'France'),
            ('Japan', 'Japan'),
            ('China', 'China'),
            ('India', 'India'),
            ('Other', 'Other'),
        ], attrs={'class': 'form-control'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            instance = getattr(self, 'instance', None)
            if instance and instance.pk:
                if Supplier.objects.filter(email=email).exclude(pk=instance.pk).exists():
                    raise ValidationError('This email is already registered.')
            else:
                if Supplier.objects.filter(email=email).exists():
                    raise ValidationError('This email is already registered.')
        return email

# ---------------------------
# Alert Settings Form
# ---------------------------
class AlertSettingsForm(forms.Form):
    email_notifications = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    dashboard_notifications = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    sms_notifications = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    weekly_summary = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    critical_threshold = forms.IntegerField(
        initial=5,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    warning_threshold = forms.IntegerField(
        initial=15,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )


# ---------------------------
# Category Form
# ---------------------------
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'parent': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = Category.objects.all().order_by('name')
        self.fields['parent'].empty_label = "-- No Parent --"

    def clean_name(self):
        name = self.cleaned_data['name']
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            if Category.objects.filter(name=name).exclude(pk=instance.pk).exists():
                raise ValidationError('A category with this name already exists.')
        else:
            if Category.objects.filter(name=name).exists():
                raise ValidationError('A category with this name already exists.')
        return name