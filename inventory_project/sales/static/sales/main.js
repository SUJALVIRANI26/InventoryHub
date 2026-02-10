/* static/inventory_manager/js/master.js */
document.addEventListener('DOMContentLoaded', function() {
    
    // --- Chart Initialization ---
    // Note: This requires Chart.js to be loaded before this script
    // Sales Chart
    const salesCtx = document.getElementById('salesChart');
    if (salesCtx) {
        new Chart(salesCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'Revenue',
                    data: [3200, 4200, 5100, 5800, 4900, 6200, 7300],
                    borderColor: '#4e73df',
                    backgroundColor: 'rgba(78, 115, 223, 0.05)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            borderDash: [5, 5]
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }

    // Product Chart
    const productCtx = document.getElementById('productChart');
    if (productCtx) {
        new Chart(productCtx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Electronics', 'Games', 'Furniture', 'Accessories'],
                datasets: [{
                    data: [45, 25, 15, 15],
                    backgroundColor: ['#4e73df', '#1cc88a', '#f6c23e', '#e74a3b'],
                    borderWidth: 0,
                    hoverOffset: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true,
                        }
                    }
                }
            }
        });
    }

    // --- Active Menu Handling ---
    const currentPath = window.location.pathname;
    const menuItems = document.querySelectorAll('.menu-item');
    const currentPage = window.location.pathname.split('/').pop();
    
    menuItems.forEach(item => {
        const href = item.getAttribute('href');
        if (href && currentPage.includes(href.replace('.html', ''))) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // --- Form Validation ---
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredInputs = form.querySelectorAll('[required]');
            let isValid = true;
            
            requiredInputs.forEach(input => {
                if (!input.value.trim()) {
                    isValid = false;
                    input.style.borderColor = 'var(--danger)';
                } else {
                    input.style.borderColor = '';
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                alert('Please fill in all required fields marked with *');
            }
        });
    });

    // --- Search Functionality ---
    const searchInputs = document.querySelectorAll('.search-bar input');
    searchInputs.forEach(input => {
        input.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const table = this.closest('.main-content').querySelector('table');
            
            if (table) {
                const rows = table.querySelectorAll('tbody tr');
                rows.forEach(row => {
                    const text = row.textContent.toLowerCase();
                    if (text.includes(searchTerm)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                });
            }
        });
    });

    // --- Print Invoice Button ---
    const printButtons = document.querySelectorAll('[onclick*="print"]');
    printButtons.forEach(button => {
        button.addEventListener('click', function() {
            window.print();
        });
    });

    // --- Delete Confirmation ---
    const deleteButtons = document.querySelectorAll('button[style*="danger"], .btn-danger');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to delete this item? This action cannot be undone.')) {
                e.preventDefault();
            }
        });
    });

    // --- Auto-generate Order Numbers ---
    const orderDateInput = document.getElementById('orderDate');
    if (orderDateInput) {
        orderDateInput.addEventListener('change', function() {
            const orderNumberInput = document.querySelector('input[placeholder*="Order #"]');
            if (orderNumberInput && !orderNumberInput.value) {
                const date = new Date(this.value);
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                const random = Math.floor(Math.random() * 1000);
                orderNumberInput.value = `SO-${year}${month}${day}-${random}`;
            }
        });
    }

    // --- Stock Level Warnings ---
    const stockInputs = document.querySelectorAll('input[id*="stock"], input[id*="Stock"]');
    stockInputs.forEach(input => {
        input.addEventListener('change', function() {
            const value = parseInt(this.value);
            const minStock = parseInt(this.getAttribute('min')) || 5;
            
            if (value <= 0) {
                this.style.borderColor = 'var(--danger)';
            } else if (value <= minStock) {
                this.style.borderColor = 'var(--warning)';
            } else {
                this.style.borderColor = '';
            }
        });
    });

    // --- Real-time Calculations for Order Forms ---
    const quantityInputs = document.querySelectorAll('input[type="number"][value]');
    quantityInputs.forEach(input => {
        input.addEventListener('input', function() {
            const row = this.closest('div[style*="grid-template-columns"]');
            if (row) {
                const price = parseFloat(row.querySelector('input[placeholder*="0.00"]').value) || 0;
                const quantity = parseFloat(this.value) || 0;
                const totalCell = row.nextElementSibling; // Assuming total is in next cell
                
                if (totalCell && totalCell.tagName === 'TD') {
                    totalCell.textContent = `$${(price * quantity).toFixed(2)}`;
                    updateOrderTotal();
                }
            }
        });
    });

    function updateOrderTotal() {
        const totalCells = document.querySelectorAll('td:last-child');
        let subtotal = 0;
        
        totalCells.forEach(cell => {
            const value = parseFloat(cell.textContent.replace('$', '')) || 0;
            if (!isNaN(value)) {
                subtotal += value;
            }
        });
        
        const tax = subtotal * 0.08; // 8% tax
        const shipping = 24.80; // Fixed shipping
        const total = subtotal + tax + shipping;
        
        // Update summary elements
        const subtotalEl = document.querySelector('[style*="Subtotal"]');
        const taxEl = document.querySelector('[style*="Tax"]');
        const shippingEl = document.querySelector('[style*="Shipping"]');
        const totalEl = document.querySelector('[style*="Total"]');
        
        if (subtotalEl) subtotalEl.textContent = `$${subtotal.toFixed(2)}`;
        if (taxEl) taxEl.textContent = `$${tax.toFixed(2)}`;
        if (shippingEl) shippingEl.textContent = `$${shipping.toFixed(2)}`;
        if (totalEl) totalEl.textContent = `$${total.toFixed(2)}`;
    }

    // --- Mobile Menu Toggle ---
    const menuToggle = document.createElement('button');
    menuToggle.innerHTML = '<i class="fa-solid fa-bars"></i>';
    menuToggle.style.cssText = 'position: fixed; top: 20px; left: 20px; z-index: 1001; background: var(--primary); color: white; border: none; width: 40px; height: 40px; border-radius: 50%; display: none;';
    document.body.appendChild(menuToggle);

    menuToggle.addEventListener('click', function() {
        document.querySelector('.sidebar').classList.toggle('active');
    });

    // Show/hide menu toggle based on screen size
    function checkScreenSize() {
        if (window.innerWidth <= 768) {
            menuToggle.style.display = 'flex';
            menuToggle.style.alignItems = 'center';
            menuToggle.style.justifyContent = 'center';
        } else {
            menuToggle.style.display = 'none';
            document.querySelector('.sidebar').classList.remove('active');
        }
    }

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);

    // --- Auto-save Draft for Forms ---
    const formInputs = document.querySelectorAll('.form-control');
    formInputs.forEach(input => {
        input.addEventListener('input', function() {
            const formId = this.closest('form').id || 'draft';
            localStorage.setItem(`formDraft_${formId}_${this.id}`, this.value);
        });
        
        // Load draft data
        const formId = input.closest('form')?.id || 'draft';
        const savedValue = localStorage.getItem(`formDraft_${formId}_${input.id}`);
        if (savedValue && !input.value) {
            input.value = savedValue;
        }
    });

    // --- Clear Draft Button ---
    const clearDraftButtons = document.querySelectorAll('[type="reset"]');
    clearDraftButtons.forEach(button => {
        button.addEventListener('click', function() {
            const formId = this.closest('form').id || 'draft';
            formInputs.forEach(input => {
                localStorage.removeItem(`formDraft_${formId}_${input.id}`);
            });
        });
    });

    console.log('DealDeck Inventory Manager initialized successfully!');
});