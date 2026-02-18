from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, FormView, TemplateView
)
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db.models import Q, Sum, Count, Avg, F
from django.db.models.functions import TruncMonth, TruncYear
from django.db.models import Value, CharField
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import csv
import json
from datetime import datetime, timedelta
from io import TextIOWrapper, StringIO

from .models import (
    Product, Category, Supplier, PurchaseOrder, PurchaseOrderItem,
    StockMovement, StockAlert,
    DashboardMetric, ImportHistory, OrderHistory
)
from .forms import (
    ProductForm, PurchaseOrderForm, PurchaseOrderItemFormSet,
    StockUpdateForm, StockAdjustmentForm, SupplierForm,AlertSettingsForm
)

# ---------------------------
# Dashboard View
# ---------------------------
class DashboardView(TemplateView):
    template_name = 'inventory_manager/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Current date
        context['current_date'] = timezone.now()
        
        # ========== PRODUCT STATS ==========
        context['total_products'] = Product.objects.count()
        context['active_products'] = Product.objects.filter(status='active').count()
        context['draft_products'] = Product.objects.filter(status='draft').count()
        context['inactive_products'] = Product.objects.filter(status='inactive').count()
        
        # Product growth (compare with last month)
        last_month = timezone.now() - timedelta(days=30)
        products_last_month = Product.objects.filter(created_at__lte=last_month).count()
        if products_last_month > 0:
            growth = ((context['total_products'] - products_last_month) / products_last_month) * 100
            context['product_growth'] = f"+{growth:.1f}%"
        else:
            context['product_growth'] = "+0%"
        
        # ========== CATEGORY STATS ==========
        context['total_categories'] = Category.objects.count()
        context['active_categories'] = Category.objects.filter(
            products__isnull=False
        ).distinct().count()
        
        # ========== SUPPLIER STATS ==========
        context['total_suppliers'] = Supplier.objects.count()
        
        # ========== STOCK VALUE ==========
        total_value = 0
        for product in Product.objects.all():
            if product.cost_price:
                total_value += product.quantity * product.cost_price
            else:
                total_value += product.quantity * product.price
        
        context['total_stock_value'] = total_value
        
        # ========== STOCK ALERTS ==========
        context['low_stock_products'] = Product.objects.filter(
            quantity__gt=0, 
            quantity__lte=F('min_stock_level')
        ).count()
        
        context['out_of_stock'] = Product.objects.filter(quantity=0).count()
        
        # ========== RECENT PRODUCTS ==========
        context['recent_products'] = Product.objects.select_related('category').order_by('-created_at')[:5]
        
        # ========== CATEGORIES WITH PRODUCT COUNTS ==========
        categories = Category.objects.annotate(
            product_count=Count('products')
        ).filter(product_count__gt=0).order_by('-product_count')[:10]
        context['products_by_category'] = categories
        
        # ========== PURCHASE ORDER STATS ==========
        context['total_purchase_orders'] = PurchaseOrder.objects.count()
        context['pending_orders'] = PurchaseOrder.objects.filter(status='pending').count()
        
        # ========== STOCK MOVEMENT STATS ==========
        context['total_movements'] = StockMovement.objects.count()
        
        # ========== CHART DATA ==========
        context['revenue_chart_labels'] = self.get_revenue_chart_labels()
        context['revenue_data'] = self.get_revenue_data()
        
        # ========== RECENT ACTIVITIES ==========
        context['recent_activities'] = self.get_recent_activities()
        
        # ========== ALERT COUNTS FOR SIDEBAR ==========
        context['product_alert_count'] = StockAlert.objects.filter(status='pending').count()
        context['stock_alert_count'] = Product.objects.filter(quantity__lte=F('min_stock_level')).count()
        context['pending_order_count'] = PurchaseOrder.objects.filter(status='pending').count()
        
        return context

    def get_revenue_chart_labels(self):
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        return months

    def get_revenue_data(self):
        now = timezone.now()
        data = []
        for month in range(1, 13):
            revenue = PurchaseOrderItem.objects.filter(
                purchase_order__order_date__year=now.year,
                purchase_order__order_date__month=month,
                purchase_order__status='delivered'
            ).aggregate(total=Sum(F('quantity') * F('unit_price')))['total'] or 0
            data.append(round(revenue / 1000, 1))
        return data

    def get_recent_activities(self):
        activities = []
        
        # Recent purchase orders
        recent_pos = PurchaseOrder.objects.select_related('supplier').order_by('-created_at')[:3]
        for po in recent_pos:
            activities.append({
                'title': f"Purchase Order {po.order_number}",
                'description': f"Created for {po.supplier.name}",
                'time_ago': self.time_ago(po.created_at)
            })
        
        # Recent stock movements
        recent_movements = StockMovement.objects.select_related('product').order_by('-created_at')[:3]
        for movement in recent_movements:
            activities.append({
                'title': f"Stock {movement.get_movement_type_display()}",
                'description': f"{movement.product.name} - {movement.quantity_change:+d} units",
                'time_ago': self.time_ago(movement.created_at)
            })
        
        return activities

    def time_ago(self, timestamp):
        delta = timezone.now() - timestamp
        if delta.days > 0:
            return f"{delta.days} days ago"
        elif delta.seconds > 3600:
            return f"{delta.seconds // 3600} hours ago"
        elif delta.seconds > 60:
            return f"{delta.seconds // 60} minutes ago"
        else:
            return "just now"


# ---------------------------
# Product Views
# ---------------------------
class ProductListView(ListView):
    model = Product
    template_name = 'inventory_manager/product_list.html'
    context_object_name = 'products'
    paginate_by = 10

    def get_queryset(self):
        
        queryset = Product.objects.select_related('category', 'supplier')
        # Search
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(sku__icontains=search_query) |
                Q(brand__icontains=search_query) |
                Q(category__name__icontains=search_query)
            )
        
        # Filter by category
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by stock status
        stock_status = self.request.GET.get('stock_status')
        if stock_status == 'low':
            queryset = queryset.filter(quantity__lte=F('min_stock_level'), quantity__gt=0)
        elif stock_status == 'out':
            queryset = queryset.filter(quantity=0)
        
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_products'] = Product.objects.count()
        context['categories'] = Category.objects.all()
        context['search_query'] = self.request.GET.get('search', '')
        return context


class ProductCreateView(CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory_manager/product_add.html'
    success_url = reverse_lazy('inventory_manager:product_list')

    def form_valid(self, form):
        # Save the product first
        if self.request.user.is_authenticated:
            form.instance.created_by = self.request.user
        self.object = form.save()
        
        # 🚫 REMOVED: All image upload handling code
        
        # Create initial stock movement
        if self.object.quantity > 0:
            StockMovement.objects.create(
                product=self.object,
                movement_type='adjustment',
                quantity_change=self.object.quantity,
                previous_quantity=0,
                new_quantity=self.object.quantity,
                notes='Initial stock setup',
                is_manual=False,
                created_by=self.request.user if self.request.user.is_authenticated else None
            )
        
        messages.success(self.request, f'Product "{self.object.name}" created successfully!')
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Product'
        return context


class ProductDetailView(DetailView):
    model = Product
    template_name = 'inventory_manager/product_details.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        
        # Get stock movements
        context['stock_movements'] = product.stock_movements.all()[:5]
        
        # Get sales performance
        context['total_sold'] = product.stock_movements.filter(
            movement_type='sale'
        ).aggregate(total=Sum('quantity_change'))['total'] or 0
        
        context['revenue'] = product.purchase_order_items.filter(
            purchase_order__status='delivered'
        ).aggregate(total=Sum(F('quantity') * F('unit_price')))['total'] or 0
        
        # Get recent sales
        context['recent_sales'] = product.purchase_order_items.filter(
            purchase_order__status='delivered'
        ).select_related('purchase_order').order_by('-purchase_order__order_date')[:5]
        
        # Calculate average monthly sales
        thirty_days_ago = timezone.now() - timedelta(days=30)
        monthly_sales = product.stock_movements.filter(
            movement_type='sale',
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('quantity_change'))['total'] or 0
        context['avg_monthly'] = monthly_sales
        
        return context


class ProductUpdateView(UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory_manager/product_edit.html'

    def get_success_url(self):
        return reverse_lazy('inventory_manager:product_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        print("="*50)
        print("EDIT FORM IS VALID")
        print("Form data:", form.cleaned_data)
        
        if self.request.user.is_authenticated:
            form.instance.updated_by = self.request.user
        
        self.object = form.save()
        print(f"Product updated: {self.object.name} (ID: {self.object.id})")
        
        messages.success(self.request, f'Product "{self.object.name}" updated successfully!')
        print("="*50)
        return super().form_valid(form)

    def form_invalid(self, form):
        print("="*50)
        print("EDIT FORM IS INVALID")
        print("Form errors:", form.errors)
        print("="*50)
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Product'
        return context


class ProductDeleteView(DeleteView):
    model = Product
    template_name = 'inventory_manager/product_delete.html'
    success_url = reverse_lazy('inventory_manager:product_list')

    def delete(self, request, *args, **kwargs):
        product = self.get_object()
        product_name = product.name
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f'Product "{product_name}" deleted successfully!')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        context['product'] = product
        context['purchase_order_count'] = product.purchase_order_items.count()
        return context


# ---------------------------
# Purchase Order Views
# ---------------------------
class PurchaseOrderListView(ListView):
    model = PurchaseOrder
    template_name = 'inventory_manager/purchase_order_list.html'
    context_object_name = 'purchase_orders'
    paginate_by = 10

    def get_queryset(self):
        queryset = PurchaseOrder.objects.select_related('supplier', 'created_by').prefetch_related('items')
        
        # Search
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(order_number__icontains=search_query) |
                Q(supplier__name__icontains=search_query) |
                Q(tracking_number__icontains=search_query)
            )
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by supplier
        supplier = self.request.GET.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        
        return queryset.order_by('-order_date', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistics
        context['total_orders'] = PurchaseOrder.objects.count()
        context['total_value'] = PurchaseOrder.objects.aggregate(total=Sum('total_amount'))['total'] or 0
        context['pending_orders'] = PurchaseOrder.objects.filter(status='pending').count()
        context['in_transit'] = PurchaseOrder.objects.filter(status='shipped').count()
        context['delivered_orders'] = PurchaseOrder.objects.filter(status='delivered').count()
        
        # Growth percentages (placeholder values for demo)
        context['total_orders_growth'] = 5.2
        context['total_value_growth'] = 12.4
        
        # Recent activities for demo
        context['recent_activities'] = []
        for po in PurchaseOrder.objects.order_by('-created_at')[:5]:
            context['recent_activities'].append({
                'title': f"Order {po.order_number}",
                'description': f"{po.get_status_display()} - {po.supplier.name}",
                'time_ago': self.time_ago(po.created_at)
            })
        
        # Statistics for demo
        context['this_month_spend'] = 45876
        context['last_month_spend'] = 38942
        context['this_quarter_spend'] = 128765
        context['ytd_spend'] = 245876
        context['this_month_percentage'] = 75
        context['last_month_percentage'] = 65
        context['this_quarter_percentage'] = 85
        context['ytd_percentage'] = 90
        
        return context

    def time_ago(self, timestamp):
        delta = timezone.now() - timestamp
        if delta.days > 0:
            return f"{delta.days} days ago"
        elif delta.seconds > 3600:
            return f"{delta.seconds // 3600} hours ago"
        elif delta.seconds > 60:
            return f"{delta.seconds // 60} minutes ago"
        else:
            return "just now"


class PurchaseOrderCreateView(CreateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'inventory_manager/purchase_order_create.html'
    success_url = reverse_lazy('inventory_manager:purchase_order_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = PurchaseOrderItemFormSet(self.request.POST, instance=self.object)
        else:
            context['formset'] = PurchaseOrderItemFormSet(instance=self.object)
        
        # Pre-select supplier if provided in URL
        supplier_id = self.request.GET.get('supplier')
        if supplier_id and 'form' in context:
            try:
                context['form'].initial['supplier'] = supplier_id
            except:
                pass
        
        # Recent suppliers for quick actions
        context['recent_suppliers'] = Supplier.objects.filter(
            status='active'
        ).order_by('-last_order_date')[:5]
        
        # Generate order number for display
        year = timezone.now().year
        last_po = PurchaseOrder.objects.filter(order_number__startswith=f'PO-{year}').order_by('-order_number').first()
        if last_po:
            try:
                last_num = int(last_po.order_number.split('-')[2])
                context['order_number'] = f"PO-{year}-{last_num + 1:03d}"
            except:
                context['order_number'] = f"PO-{year}-001"
        else:
            context['order_number'] = f"PO-{year}-001"
        
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        
        if formset.is_valid():
            # Set created_by
            if self.request.user.is_authenticated:
                form.instance.created_by = self.request.user
            
            # Save the purchase order
            self.object = form.save()
            
            # Save formset with the purchase order instance
            formset.instance = self.object
            formset.save()
            
            # Create order history
            OrderHistory.objects.create(
                purchase_order=self.object,
                action='created',
                user=self.request.user if self.request.user.is_authenticated else None,
                notes=f"Purchase order created with {self.object.items.count()} items"
            )
            
            # Update supplier last order date
            supplier = self.object.supplier
            supplier.last_order_date = self.object.order_date
            supplier.total_orders += 1
            supplier.total_spend += self.object.total_amount
            supplier.save()
            
            messages.success(self.request, f'Purchase Order {self.object.order_number} created successfully!')
            return redirect('inventory_manager:purchase_order_detail', pk=self.object.pk)
        else:
            print("Formset errors:", formset.errors)  # Debug
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        
        # Print errors to console for debugging
        print("="*50)
        print("FORM ERRORS:", form.errors)
        print("FORMSET ERRORS:", self.get_context_data()['formset'].errors)
        print("="*50)
        
        return super().form_invalid(form)


class PurchaseOrderDetailView(DetailView):
    model = PurchaseOrder
    template_name = 'inventory_manager/purchase_order_details.html'
    context_object_name = 'purchase_order'

    def get_queryset(self):
        return PurchaseOrder.objects.select_related('supplier', 'created_by', 'updated_by').prefetch_related(
            'items', 'items__product', 'history', 'history__user'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        purchase_order = self.get_object()
        
        # Get items
        context['items'] = purchase_order.items.all().select_related('product')
        
        # Get order history
        context['history'] = purchase_order.history.all().select_related('user')[:10]
        
        # Calculate summary
        context['items_count'] = purchase_order.items.count()
        context['total_units'] = purchase_order.items.aggregate(total=Sum('quantity'))['total'] or 0
        
        # Days to delivery
        if purchase_order.expected_delivery:
            days_left = (purchase_order.expected_delivery - timezone.now().date()).days
            context['days_remaining'] = max(days_left, 0)
        
        # Order age
        if purchase_order.created_at:
            order_age = (timezone.now().date() - purchase_order.created_at.date()).days
            context['order_age'] = max(order_age, 0)
        
        return context


class PurchaseOrderUpdateView(UpdateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'inventory_manager/purchase_order_edit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = PurchaseOrderItemFormSet(self.request.POST, instance=self.object)
        else:
            context['formset'] = PurchaseOrderItemFormSet(instance=self.object)
        
        # Days remaining
        if self.object.expected_delivery:
            days_left = (self.object.expected_delivery - timezone.now().date()).days
            context['days_remaining'] = max(days_left, 0)
        
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        
        if formset.is_valid():
            if self.request.user.is_authenticated:
                form.instance.updated_by = self.request.user
            self.object = form.save()
            
            # Save formset
            formset.instance = self.object
            formset.save()
            
            # Create order history
            OrderHistory.objects.create(
                purchase_order=self.object,
                action='updated',
                user=self.request.user if self.request.user.is_authenticated else None,
                notes="Purchase order updated"
            )
            
            messages.success(self.request, f'Purchase Order {self.object.order_number} updated successfully!')
            return redirect('inventory_manager:purchase_order_detail', pk=self.object.pk)
        else:
            return self.form_invalid(form)


class PurchaseOrderDeleteView(DeleteView):
    model = PurchaseOrder
    template_name = 'inventory_manager/purchase_order_delete.html'
    success_url = reverse_lazy('inventory_manager:purchase_order_list')

    def delete(self, request, *args, **kwargs):
        purchase_order = self.get_object()
        order_number = purchase_order.order_number
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f'Purchase Order {order_number} deleted successfully!')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        purchase_order = self.get_object()
        context['purchase_order'] = purchase_order
        context['total_units'] = purchase_order.items.aggregate(total=Sum('quantity'))['total'] or 0
        return context


# ---------------------------
# Stock Management Views
# ---------------------------
class StockListView(ListView):
    model = Product
    template_name = 'inventory_manager/stock_list.html'
    context_object_name = 'products'
    paginate_by = 10

    def get_queryset(self):
        queryset = Product.objects.select_related('category')
        
        # Search
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(sku__icontains=search_query) |
                Q(brand__icontains=search_query)
            )
        
        # Filter by stock status
        stock_status = self.request.GET.get('stock_status')
        if stock_status == 'low':
            queryset = queryset.filter(quantity__lte=F('min_stock_level'), quantity__gt=0)
        elif stock_status == 'out':
            queryset = queryset.filter(quantity=0)
        elif stock_status == 'in':
            queryset = queryset.filter(quantity__gt=F('min_stock_level'))
        
        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistics
        context['total_products'] = Product.objects.count()
        context['total_stock_value'] = Product.objects.aggregate(
            total=Sum(F('quantity') * F('cost_price'))
        )['total'] or 0
        context['low_stock_count'] = Product.objects.filter(quantity__lte=F('min_stock_level'), quantity__gt=0).count()
        context['out_of_stock_count'] = Product.objects.filter(quantity=0).count()
        
        # Growth percentages (placeholder for demo)
        context['stock_growth'] = 5.2
        context['value_growth'] = 12.4
        
        # Recent stock movements
        context['recent_movements'] = StockMovement.objects.select_related('product', 'created_by').order_by('-created_at')[:10]
        
        # Stock alerts
        context['stock_alerts'] = StockAlert.objects.filter(status='pending').select_related('product')[:5]
        context['critical_alerts_count'] = StockAlert.objects.filter(alert_type='critical', status='pending').count()
        
        return context


class StockUpdateView(FormView):
    template_name = 'inventory_manager/stock_update.html'
    form_class = StockUpdateForm
    success_url = reverse_lazy('inventory_manager:stock_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Recent stock movements
        context['recent_movements'] = StockMovement.objects.select_related('product').order_by('-created_at')[:5]
        
        # Pre-select product if provided in URL
        product_id = self.request.GET.get('product')
        if product_id and 'form' in context:
            try:
                context['form'].initial['product'] = int(product_id)
            except:
                pass
        
        return context

    def form_valid(self, form):
        product = form.cleaned_data['product']
        update_type = form.cleaned_data['update_type']
        quantity = form.cleaned_data['quantity']
        reason = form.cleaned_data['reason']
        reference = form.cleaned_data['reference']
        notes = form.cleaned_data['notes']
        
        old_quantity = product.quantity
        
        # Calculate new quantity based on update type
        if update_type == 'add':
            new_quantity = old_quantity + quantity
            quantity_change = quantity
        elif update_type == 'remove':
            new_quantity = max(old_quantity - quantity, 0)
            quantity_change = -min(quantity, old_quantity)
        else:  # set
            new_quantity = quantity
            quantity_change = new_quantity - old_quantity
        
        # Update product quantity
        product.quantity = new_quantity
        if self.request.user.is_authenticated:
            product.updated_by = self.request.user
        product.save(update_fields=['quantity', 'updated_at', 'updated_by'])
        
        # Create stock movement record
        movement = StockMovement.objects.create(
            product=product,
            movement_type=self.get_movement_type_from_reason(reason),
            adjustment_reason=reason if reason in ['count', 'damage', 'theft', 'other'] else None,
            quantity_change=quantity_change,
            previous_quantity=old_quantity,
            new_quantity=new_quantity,
            reference_number=reference,
            notes=notes,
            is_manual=True,
            created_by=self.request.user if self.request.user.is_authenticated else None
        )
        
        # Check and create stock alerts if needed
        self.check_stock_alerts(product)
        
        messages.success(
            self.request,
            f'Stock updated for {product.name}. New quantity: {new_quantity} units.'
        )
        
        return super().form_valid(form)

    def get_movement_type_from_reason(self, reason):
        mapping = {
            'purchase': 'purchase',
            'sale': 'sale',
            'return': 'return',
            'damage': 'damage',
            'adjustment': 'adjustment',
            'other': 'adjustment'
        }
        return mapping.get(reason, 'adjustment')

    def check_stock_alerts(self, product):
        """Create or resolve stock alerts based on current stock level"""
        # Resolve existing pending alerts
        StockAlert.objects.filter(
            product=product,
            status='pending'
        ).update(status='resolved', resolved_at=timezone.now())
        
        # Create new alerts if needed
        if product.quantity <= 0:
            StockAlert.objects.create(
                product=product,
                alert_type='critical',
                message=f'{product.name} is out of stock!',
                current_stock=product.quantity,
                threshold=product.min_stock_level
            )
        elif product.quantity <= product.min_stock_level:
            StockAlert.objects.create(
                product=product,
                alert_type='warning',
                message=f'{product.name} is below minimum stock level ({product.min_stock_level}).',
                current_stock=product.quantity,
                threshold=product.min_stock_level
            )
        elif product.quantity <= product.reorder_point:
            StockAlert.objects.create(
                product=product,
                alert_type='warning',
                message=f'{product.name} is approaching minimum stock level.',
                current_stock=product.quantity,
                threshold=product.reorder_point
            )


class StockAdjustmentView(FormView):
    template_name = 'inventory_manager/stock_adjustment.html'
    form_class = StockAdjustmentForm
    success_url = reverse_lazy('inventory_manager:stock_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.filter(status='active').order_by('name')
        return context

    def form_valid(self, form):
        csv_file = form.cleaned_data.get('csv_file')
        notify = form.cleaned_data.get('notify', True)
        
        if csv_file:
            # Process CSV file
            self.process_csv_adjustment(csv_file)
        else:
            # Process manual adjustments from form
            self.process_manual_adjustments(self.request.POST)
        
        messages.success(self.request, 'Stock adjustments applied successfully!')
        return super().form_valid(form)

    def process_csv_adjustment(self, csv_file):
        """Process stock adjustments from CSV file"""
        import_history = ImportHistory.objects.create(
            import_type='stock',
            file_name=csv_file.name,
            file_size=csv_file.size,
            status='processing',
            created_by=self.request.user if self.request.user.is_authenticated else None
        )

        try:
            csv_file.seek(0)
            reader = csv.DictReader(TextIOWrapper(csv_file, encoding='utf-8'))
            
            success_count = 0
            error_count = 0
            errors = []
            row_num = 1

            for row_num, row in enumerate(reader, start=2):
                try:
                    sku = row.get('SKU')
                    adjustment_qty = int(row.get('Adjustment_Quantity', 0))
                    reason = row.get('Reason', 'count')
                    notes = row.get('Notes', '')
                    
                    if not sku:
                        raise ValueError('SKU is required')
                    
                    product = Product.objects.get(sku=sku)
                    
                    old_quantity = product.quantity
                    new_quantity = max(old_quantity + adjustment_qty, 0)
                    
                    # Update product
                    product.quantity = new_quantity
                    if self.request.user.is_authenticated:
                        product.updated_by = self.request.user
                    product.save(update_fields=['quantity', 'updated_at', 'updated_by'])
                    
                    # Create stock movement
                    StockMovement.objects.create(
                        product=product,
                        movement_type='adjustment',
                        adjustment_reason=reason,
                        quantity_change=adjustment_qty,
                        previous_quantity=old_quantity,
                        new_quantity=new_quantity,
                        notes=notes,
                        is_manual=True,
                        created_by=self.request.user if self.request.user.is_authenticated else None
                    )
                    
                    success_count += 1
                    
                except Product.DoesNotExist:
                    error_count += 1
                    errors.append(f"Row {row_num}: Product with SKU '{sku}' not found")
                except Exception as e:
                    error_count += 1
                    errors.append(f"Row {row_num}: {str(e)}")

            import_history.status = 'completed' if error_count == 0 else 'failed'
            import_history.records_total = row_num - 1
            import_history.records_success = success_count
            import_history.records_failed = error_count
            import_history.error_log = '\n'.join(errors)
            import_history.completed_at = timezone.now()
            import_history.save()

        except Exception as e:
            import_history.status = 'failed'
            import_history.error_log = str(e)
            import_history.completed_at = timezone.now()
            import_history.save()

    def process_manual_adjustments(self, post_data):
        """Process manual stock adjustments from form"""
        i = 0
        while f'adjustments[{i}][product]' in post_data:
            product_id = post_data.get(f'adjustments[{i}][product]')
            adjustment_type = post_data.get(f'adjustments[{i}][type]')
            quantity = int(post_data.get(f'adjustments[{i}][quantity]', 0))
            reason = post_data.get(f'adjustments[{i}][reason]', 'count')
            notes = post_data.get(f'adjustments[{i}][notes]', '')
            
            if product_id and quantity > 0:
                try:
                    product = Product.objects.get(id=product_id)
                    old_quantity = product.quantity
                    
                    if adjustment_type == 'increase':
                        new_quantity = old_quantity + quantity
                        qty_change = quantity
                    elif adjustment_type == 'decrease':
                        new_quantity = max(old_quantity - quantity, 0)
                        qty_change = -min(quantity, old_quantity)
                    else:  # set
                        new_quantity = quantity
                        qty_change = new_quantity - old_quantity
                    
                    product.quantity = new_quantity
                    if self.request.user.is_authenticated:
                        product.updated_by = self.request.user
                    product.save(update_fields=['quantity', 'updated_at', 'updated_by'])
                    
                    StockMovement.objects.create(
                        product=product,
                        movement_type='adjustment',
                        adjustment_reason=reason,
                        quantity_change=qty_change,
                        previous_quantity=old_quantity,
                        new_quantity=new_quantity,
                        notes=notes,
                        is_manual=True,
                        created_by=self.request.user if self.request.user.is_authenticated else None
                    )
                    
                except Product.DoesNotExist:
                    pass
            
            i += 1


class StockMovementListView(ListView):
    model = StockMovement
    template_name = 'inventory_manager/stock_movement.html'
    context_object_name = 'movements'
    paginate_by = 20

    def get_queryset(self):
        queryset = StockMovement.objects.select_related('product', 'created_by')
        
        # Date range filter
        date_range = self.request.GET.get('date_range')
        if date_range == '7':
            queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=7))
        elif date_range == '30':
            queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=30))
        elif date_range == '90':
            queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=90))
        else:
            queryset = queryset.filter(created_at__gte=timezone.now() - timedelta(days=30))
        
        # Movement type filter
        movement_type = self.request.GET.get('movement_type')
        if movement_type and movement_type != 'all':
            queryset = queryset.filter(movement_type=movement_type)
        
        # Search
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(product__name__icontains=search_query) |
                Q(product__sku__icontains=search_query) |
                Q(reference_number__icontains=search_query) |
                Q(transaction_id__icontains=search_query)
            )
        
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistics
        thirty_days_ago = timezone.now() - timedelta(days=30)
        movements = StockMovement.objects.filter(created_at__gte=thirty_days_ago)
        
        context['total_records'] = StockMovement.objects.count()
        context['total_transactions'] = movements.count()
        context['total_stock_in'] = movements.filter(quantity_change__gt=0).aggregate(
            total=Sum('quantity_change')
        )['total'] or 0
        context['total_stock_out'] = abs(movements.filter(quantity_change__lt=0).aggregate(
            total=Sum('quantity_change')
        )['total'] or 0)
        context['net_change'] = context['total_stock_in'] - context['total_stock_out']
        
        # Movement by type
        context['movement_by_type'] = {
            'purchase': movements.filter(movement_type='purchase').count(),
            'sale': movements.filter(movement_type='sale').count(),
            'adjustment': movements.filter(movement_type='adjustment').count(),
            'return': movements.filter(movement_type='return').count(),
        }
        
        # Top products by movement
        context['top_products'] = StockMovement.objects.filter(
            created_at__gte=thirty_days_ago
        ).values(
            'product__id', 'product__name', 'product__sku'
        ).annotate(
            total_movements=Count('id'),
            net_change=Sum('quantity_change')
        ).order_by('-total_movements')[:5]
        
        return context


class StockAlertListView(ListView):
    model = StockAlert
    template_name = 'inventory_manager/stock_alerts.html'
    context_object_name = 'alerts'
    paginate_by = 20

    def get_queryset(self):
        queryset = StockAlert.objects.select_related('product', 'resolved_by')
        
        # Filter by status
        status = self.request.GET.get('status', 'pending')
        if status != 'all':
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistics
        context['critical_count'] = StockAlert.objects.filter(
            alert_type='critical', status='pending'
        ).count()
        context['warning_count'] = StockAlert.objects.filter(
            alert_type='warning', status='pending'
        ).count()
        context['out_of_stock_count'] = Product.objects.filter(quantity=0).count()
        context['low_stock_count'] = Product.objects.filter(
            quantity__lte=F('min_stock_level'), quantity__gt=0
        ).count()
        
        # Critical alerts
        context['critical_alerts'] = StockAlert.objects.filter(
            alert_type='critical', status='pending'
        ).select_related('product')[:5]
        
        # Warning alerts
        context['warning_alerts'] = StockAlert.objects.filter(
            alert_type='warning', status='pending'
        ).select_related('product')[:8]
        
        # Alert history
        context['alert_history'] = StockAlert.objects.filter(
            status__in=['resolved', 'ignored']
        ).select_related('product', 'resolved_by').order_by('-created_at')[:10]
        
        return context


# ---------------------------
# Supplier Views
# ---------------------------
class SupplierListView(ListView):
    model = Supplier
    template_name = 'inventory_manager/supplier_list.html'
    context_object_name = 'suppliers'
    paginate_by = 10

    def get_queryset(self):
        queryset = Supplier.objects.select_related('category')
        
        # Search
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(supplier_code__icontains=search_query) |
                Q(contact_person__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(phone__icontains=search_query)
            )
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by category
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistics
        context['total_suppliers'] = Supplier.objects.count()
        context['avg_rating'] = Supplier.objects.aggregate(avg=Avg('average_rating'))['avg'] or 0
        context['active_orders'] = PurchaseOrder.objects.filter(status__in=['pending', 'approved', 'ordered', 'shipped']).count()
        context['total_spend'] = Supplier.objects.aggregate(total=Sum('total_spend'))['total'] or 0
        context['active_suppliers'] = Supplier.objects.filter(status='active').count()
        context['inactive_suppliers'] = Supplier.objects.filter(status='inactive').count()
        
        # Growth percentages (placeholder for demo)
        context['supplier_growth'] = 8.3
        context['active_orders_growth'] = 12.5
        
        # Supplier categories with counts
        category_stats = []
        for category in Category.objects.all():
            count = Supplier.objects.filter(category=category).count()
            if count > 0:
                category_stats.append({
                    'name': category.name,
                    'count': count
                })
        
        # Add suppliers without category
        uncategorized_count = Supplier.objects.filter(category__isnull=True).count()
        if uncategorized_count > 0:
            category_stats.append({
                'name': 'Uncategorized',
                'count': uncategorized_count
            })
        
        context['categories'] = category_stats
        
        # Top suppliers by spend
        context['top_suppliers'] = Supplier.objects.order_by('-total_spend')[:5]

        return context


class SupplierCreateView(CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'inventory_manager/supplier_add.html'
    success_url = reverse_lazy('inventory_manager:supplier_list')

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f'Supplier "{self.object.name}" created successfully!')
        return response


class SupplierDetailView(DetailView):
    model = Supplier
    template_name = 'inventory_manager/supplier_details.html'
    context_object_name = 'supplier'

    def get_queryset(self):
        return Supplier.objects.prefetch_related(
            'purchase_orders', 'purchase_orders__items'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.get_object()
        
        # Recent purchase orders
        context['recent_orders'] = supplier.purchase_orders.all().order_by('-order_date')[:5]
        
        # Active orders count
        context['active_orders'] = supplier.purchase_orders.filter(
            status__in=['pending', 'approved', 'ordered', 'shipped']
        ).count()
        
        # Performance metrics
        context['total_spend'] = supplier.total_spend
        
        # Monthly spend trend (last 5 months)
        context['monthly_spend'] = self.get_monthly_spend(supplier)
        
        return context

    def get_monthly_spend(self, supplier):
        now = timezone.now()
        monthly_data = []
        
        for i in range(5, 0, -1):
            month = now.month - i
            year = now.year
            if month <= 0:
                month += 12
                year -= 1
            
            spend = supplier.purchase_orders.filter(
                order_date__year=year,
                order_date__month=month,
                status='delivered'
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            monthly_data.append({
                'month': datetime(year, month, 1).strftime('%b'),
                'spend': round(spend / 1000, 1)  # Convert to K
            })
        
        return monthly_data


class SupplierUpdateView(UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'inventory_manager/supplier_edit.html'

    def get_success_url(self):
        return reverse_lazy('inventory_manager:supplier_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f'Supplier "{self.object.name}" updated successfully!')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

class SupplierDeleteView(DeleteView):
    model = Supplier
    template_name = 'inventory_manager/supplier_confirm_delete.html'
    success_url = reverse_lazy('inventory_manager:supplier_list')

    def delete(self, request, *args, **kwargs):
        supplier = self.get_object()
        supplier_name = supplier.name
        
        # Check if supplier has related records
        has_products = supplier.products.exists()
        has_orders = supplier.purchase_orders.exists()
        
        if has_products or has_orders:
            messages.warning(
                request, 
                f'Cannot delete "{supplier_name}" because it has {supplier.products.count()} products and {supplier.purchase_orders.count()} orders. Mark as inactive instead.'
            )
            return redirect('inventory_manager:supplier_detail', pk=supplier.pk)
        
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f'Supplier "{supplier_name}" deleted successfully!')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.get_object()
        context['supplier'] = supplier
        context['product_count'] = supplier.products.count()
        context['order_count'] = supplier.purchase_orders.count()
        context['total_spend'] = supplier.total_spend
        return context


class SupplierHistoryView(TemplateView):
    template_name = 'inventory_manager/supplier_history.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = get_object_or_404(Supplier, pk=self.kwargs['pk'])
        
        # Get all orders for this supplier
        orders = supplier.purchase_orders.all().order_by('-order_date')
        
       
        # Calculate statistics
        total_orders = orders.count()
        total_spend = orders.aggregate(total=Sum('total_amount'))['total'] or 0
        avg_order_value = total_spend / total_orders if total_orders > 0 else 0
        
        # Order status breakdown
        status_counts = {
            'pending': orders.filter(status='pending').count(),
            'approved': orders.filter(status='approved').count(),
            'shipped': orders.filter(status='shipped').count(),
            'delivered': orders.filter(status='delivered').count(),
            'cancelled': orders.filter(status='cancelled').count(),
        }
        
        context.update({
            'supplier': supplier,
            'orders': orders,
            'total_orders': total_orders,
            'total_spend': total_spend,
            'avg_order_value': avg_order_value,
            'status_counts': status_counts,
            'recent_activities': self.get_recent_activities(supplier),
        })
        return context
    
    def get_recent_activities(self, supplier):
        activities = []
        
        # Order activities
        for order in supplier.purchase_orders.all().order_by('-created_at')[:5]:
            activities.append({
                'action': f'Order {order.order_number}',
                'date': order.created_at,
                'details': f'Status: {order.get_status_display()}, Amount: ${order.total_amount}',
                'icon': 'fa-solid fa-cart-shopping',
                'color': 'primary'
            })
        
        # Sort by date
        activities.sort(key=lambda x: x['date'], reverse=True)
        return activities[:10]


# ---------------------------
# Export Functions
# ---------------------------
def export_product_template(request):
    """Generate CSV template for product import"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="product_import_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['product_name', 'sku', 'category', 'brand', 'price', 
                     'cost_price', 'quantity', 'min_stock_level', 'reorder_point', 
                     'supplier', 'description'])
    writer.writerow(['Wireless Headphones Pro', 'SKU-001', 'Electronics', 'AudioTech',
                     '199.99', '120.50', '45', '10', '15', 'Tech Supplies Inc.',
                     'Premium wireless headphones with noise cancellation'])
    
    return response


def export_adjustment_template(request):
    """Generate CSV template for stock adjustment"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="stock_adjustment_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['SKU', 'Adjustment_Quantity', 'Reason', 'Notes'])
    writer.writerow(['SKU-001', '5', 'count', 'Physical count adjustment'])
    writer.writerow(['SKU-002', '-2', 'damage', 'Damaged during handling'])
    
    return response


def export_stock_movement(request):
    """Export stock movement data as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="stock_movement_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Product', 'SKU', 'Type', 'Quantity', 'Before', 'After', 'Reference', 'User', 'Notes'])
    
    movements = StockMovement.objects.select_related('product', 'created_by').order_by('-created_at')[:1000]
    
    for movement in movements:
        writer.writerow([
            movement.created_at.strftime('%Y-%m-%d %H:%M'),
            movement.product.name,
            movement.product.sku,
            movement.get_movement_type_display(),
            movement.quantity_change,
            movement.previous_quantity,
            movement.new_quantity,
            movement.reference_number or '',
            movement.created_by.get_full_name() or movement.created_by.username if movement.created_by else 'System',
            movement.notes or ''
        ])
    
    return response


def export_supplier_data(request, pk):
    """Export supplier data as CSV"""
    supplier = get_object_or_404(Supplier, pk=pk)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{supplier.name}_data_{supplier.supplier_code}.csv"'
    
    writer = csv.writer(response)
    
    writer.writerow(['SUPPLIER INFORMATION'])
    writer.writerow(['Field', 'Value'])
    writer.writerow(['Name', supplier.name])
    writer.writerow(['Supplier Code', supplier.supplier_code])
    writer.writerow(['Category', supplier.category.name if supplier.category else 'N/A'])
    writer.writerow(['Status', supplier.get_status_display()])
    writer.writerow([])
    
    writer.writerow(['CONTACT INFORMATION'])
    writer.writerow(['Contact Person', supplier.contact_person or ''])
    writer.writerow(['Contact Title', supplier.contact_title or ''])
    writer.writerow(['Email', supplier.email or ''])
    writer.writerow(['Phone', supplier.phone or ''])
    writer.writerow(['Website', supplier.website or ''])
    writer.writerow([])
    
    writer.writerow(['ADDRESS'])
    writer.writerow(['Street', supplier.address or ''])
    writer.writerow(['City', supplier.city or ''])
    writer.writerow(['State', supplier.state or ''])
    writer.writerow(['Zip Code', supplier.zip_code or ''])
    writer.writerow(['Country', supplier.country or ''])
    writer.writerow([])
    
    writer.writerow(['BUSINESS TERMS'])
    writer.writerow(['Payment Terms', supplier.get_payment_terms_display()])
    writer.writerow(['Credit Limit', f'${supplier.credit_limit}' if supplier.credit_limit else 'N/A'])
    writer.writerow(['Tax ID', supplier.tax_id or ''])
    writer.writerow(['Preferred Currency', supplier.get_preferred_currency_display()])
    writer.writerow(['Min Order Value', f'${supplier.min_order_value}' if supplier.min_order_value else 'N/A'])
    writer.writerow(['Lead Time', f'{supplier.lead_time_days} days' if supplier.lead_time_days else 'N/A'])
    writer.writerow([])
    
    writer.writerow(['PERFORMANCE METRICS'])
    writer.writerow(['Total Orders', supplier.total_orders])
    writer.writerow(['Total Spend', f'${supplier.total_spend}'])
    writer.writerow(['Average Rating', f'{supplier.average_rating}/5'])
    writer.writerow(['On-Time Delivery Rate', f'{supplier.on_time_delivery_rate}%'])
    writer.writerow(['Last Order Date', supplier.last_order_date or 'N/A'])
    writer.writerow([])
    
    writer.writerow(['NOTES'])
    writer.writerow([supplier.notes or ''])
    writer.writerow([])
    
    writer.writerow(['RECENT PURCHASE ORDERS'])
    writer.writerow(['Order Number', 'Date', 'Amount', 'Status'])
    
    for order in supplier.purchase_orders.all().order_by('-order_date')[:10]:
        writer.writerow([
            order.order_number,
            order.order_date,
            f'${order.total_amount}',
            order.get_status_display()
        ])
    
    return response


# ---------------------------
# AJAX Views
# ---------------------------
def update_order_status(request, pk):
    """Update purchase order status via AJAX"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            status = data.get('status')
            
            order = get_object_or_404(PurchaseOrder, pk=pk)
            old_status = order.status
            order.status = status
            if request.user.is_authenticated:
                order.updated_by = request.user
            order.save()
            
            # Create order history
            OrderHistory.objects.create(
                purchase_order=order,
                action='status_changed',
                user=request.user if request.user.is_authenticated else None,
                field_name='status',
                old_value=old_status,
                new_value=status,
                notes=f'Status changed via AJAX'
            )
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid method'})


def save_alert_settings(request):
    """Save alert settings via AJAX"""
    if request.method == 'POST':
        # In a real app, you would save these to a UserProfile or Settings model
        # For now, just return success
        return JsonResponse({'success': True, 'message': 'Settings saved successfully'})
    return JsonResponse({'success': False, 'error': 'Invalid method'})


def upload_document(request, supplier_id):
    """Handle document upload via AJAX"""
    if request.method == 'POST' and request.FILES.get('document'):
        supplier = get_object_or_404(Supplier, pk=supplier_id)
        doc_file = request.FILES['document']
        
        document = SupplierDocument.objects.create(
            supplier=supplier,
            name=doc_file.name,
            file=doc_file,
            uploaded_by=request.user if request.user.is_authenticated else None
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Document uploaded successfully',
            'document': {
                'id': document.id,
                'name': document.name,
                'url': document.file.url,
                'uploaded_at': document.uploaded_at.strftime('%Y-%m-%d %H:%M')
            }
        })
    
    return JsonResponse({'success': False, 'error': 'No file uploaded'})


def delete_document(request, pk):
    """Delete a supplier document via AJAX"""
    if request.method == 'POST':
        try:
            document = SupplierDocument.objects.get(pk=pk)
            doc_name = document.name
            document.delete()
            return JsonResponse({
                'success': True,
                'message': f'Document "{doc_name}" deleted successfully'
            })
        except SupplierDocument.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Document not found'
            })
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })


def resolve_alert(request, pk):
    """Resolve a stock alert via AJAX"""
    if request.method == 'POST':
        alert = get_object_or_404(StockAlert, pk=pk)
        alert.status = 'resolved'
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user if request.user.is_authenticated else None
        alert.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid method'})


def get_product_info(request):
    """Get product information for stock update"""
    product_id = request.GET.get('product_id')
    try:
        product = Product.objects.get(id=product_id)
        
        # Get primary image
        primary_image = product.images.filter(is_primary=True).first()
        
        data = {
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'category': product.category.name if product.category else '',
            'price': float(product.price),
            'quantity': product.quantity,
            'min_stock_level': product.min_stock_level,
            'status': product.stock_status,
            'status_display': product.get_stock_status_display(),
            'status_color': 'success' if product.stock_status == 'in_stock' else 'warning' if product.stock_status == 'low_stock' else 'danger',
            'image': primary_image.image.url if primary_image else None
        }
        return JsonResponse({'success': True, 'product': data})
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Product not found'})