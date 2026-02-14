/* static/inventory_manager/js/main.js */

document.addEventListener('DOMContentLoaded', function() {
    
    // --- Initialize Charts ---
    initCharts();
    
    // --- Active Menu Handling ---
    highlightActiveMenu();
    
    // --- Initialize Tooltips ---
    initTooltips();
    
    // --- Initialize File Upload Previews ---
    initFileUploadPreviews();
    
    // --- Initialize Delete Confirmations ---
    initDeleteConfirmations();
    
    // --- Initialize Form Validation ---
    initFormValidation();
    
    // --- Initialize Date Pickers ---
    initDatePickers();
    
    // --- Initialize Search Functionality ---
    initSearch();
});

/**
 * Initialize all charts on the page
 */
function initCharts() {
    // Bar Chart (Customer Habits)
    const ctxBar = document.getElementById('barChart');
    if (ctxBar) {
        new Chart(ctxBar, {
            type: 'bar',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                datasets: [
                    {
                        label: 'Views',
                        data: [40000, 30000, 20000, 45000, 25000, 50000, 40000, 55000, 48000, 60000, 52000, 58000],
                        backgroundColor: '#e2e6ea',
                        borderRadius: 5,
                        barPercentage: 0.6
                    },
                    {
                        label: 'Sales',
                        data: [30000, 20000, 15000, 39784, 20000, 40000, 30000, 42000, 35000, 45000, 40000, 43000],
                        backgroundColor: '#4e73df',
                        borderRadius: 5,
                        barPercentage: 0.6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { 
                        position: 'top', 
                        align: 'start', 
                        labels: { 
                            usePointStyle: true,
                            boxWidth: 8
                        } 
                    } 
                },
                scales: {
                    y: { 
                        beginAtZero: true, 
                        grid: { 
                            borderDash: [5, 5], 
                            drawBorder: false 
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + (value / 1000) + 'k';
                            }
                        }
                    },
                    x: { 
                        grid: { display: false } 
                    }
                }
            }
        });
    }

    // Doughnut Chart (Product Categories)
    const ctxDonut = document.getElementById('donutChart');
    if (ctxDonut) {
        new Chart(ctxDonut, {
            type: 'doughnut',
            data: {
                labels: ['Electronics', 'Games', 'Furniture', 'Clothing', 'Others'],
                datasets: [{
                    data: [45, 30, 25, 15, 10],
                    backgroundColor: ['#4e73df', '#1cc88a', '#e74a3b', '#f6c23e', '#36b9cc'],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                cutout: '75%',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.label + ': ' + context.raw + '%';
                            }
                        }
                    }
                }
            }
        });
    }

    // Line Chart (Revenue Trend)
    const ctxLine = document.getElementById('lineChart');
    if (ctxLine) {
        new Chart(ctxLine, {
            type: 'line',
            data: {
                labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
                datasets: [{
                    label: 'This Month',
                    data: [45000, 52000, 48000, 60000],
                    borderColor: '#4e73df',
                    backgroundColor: 'rgba(78, 115, 223, 0.05)',
                    tension: 0.4,
                    fill: true
                }, {
                    label: 'Last Month',
                    data: [38000, 42000, 40000, 45000],
                    borderColor: '#858796',
                    backgroundColor: 'rgba(133, 135, 150, 0.05)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
}

/**
 * Highlight active menu item based on current URL
 */
function highlightActiveMenu() {
    const currentPath = window.location.pathname;
    const menuItems = document.querySelectorAll('.menu-item');
    
    menuItems.forEach(item => {
        const href = item.getAttribute('href');
        if (href && currentPath.includes(href) && href !== '/') {
            item.classList.add('active');
        } else if (href === '/' && currentPath === '/') {
            item.classList.add('active');
        } else if (href === '/inventory_manager/' && currentPath.includes('/inventory_manager/')) {
            item.classList.add('active');
        }
    });
}

/**
 * Initialize tooltips
 */
function initTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(element => {
        element.addEventListener('mouseenter', function(e) {
            const tooltip = this.getAttribute('data-tooltip');
            // Tooltip is handled by CSS
        });
    });
}

/**
 * Initialize file upload previews
 */
function initFileUploadPreviews() {
    const imageFields = ['main_image', 'image_1', 'image_2', 'image_3', 'image_4'];
    
    imageFields.forEach(function(fieldName) {
        const input = document.getElementById('id_' + fieldName);
        const previewDiv = document.getElementById(fieldName + '_preview');
        const fileNameSpan = document.getElementById(fieldName + '_name');
        
        if (input && previewDiv) {
            input.addEventListener('change', function(e) {
                if (this.files && this.files[0]) {
                    const file = this.files[0];
                    
                    // Update file name
                    if (fileNameSpan) {
                        fileNameSpan.textContent = file.name.length > 20 
                            ? file.name.substring(0, 17) + '...' 
                            : file.name;
                    }
                    
                    // Show image preview
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        previewDiv.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
                    }
                    reader.readAsDataURL(file);
                } else {
                    if (fileNameSpan) {
                        fileNameSpan.textContent = 'No file chosen';
                    }
                    previewDiv.innerHTML = `<i class="fa-solid fa-image" style="font-size: 2rem; color: #ccc;"></i>`;
                }
            });
        }
    });
}

/**
 * Initialize delete confirmations
 */
function initDeleteConfirmations() {
    const deleteButtons = document.querySelectorAll('.btn-delete, [data-confirm]');
    
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const message = this.getAttribute('data-confirm') || 'Are you sure you want to delete this item? This action cannot be undone.';
            
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
        });
    });
    
    // Handle delete forms
    const deleteForms = document.querySelectorAll('form[data-confirm]');
    deleteForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const message = this.getAttribute('data-confirm') || 'Are you sure you want to delete this item?';
            
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
        });
    });
}

/**
 * Initialize form validation
 */
function initFormValidation() {
    const forms = document.querySelectorAll('form[data-validate]');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            let isValid = true;
            const requiredFields = this.querySelectorAll('[required]');
            
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    isValid = false;
                    field.classList.add('error');
                    
                    // Show error message
                    let errorDiv = field.nextElementSibling;
                    if (!errorDiv || !errorDiv.classList.contains('error-message')) {
                        errorDiv = document.createElement('small');
                        errorDiv.className = 'error-message';
                        errorDiv.style.color = 'var(--danger)';
                        field.parentNode.insertBefore(errorDiv, field.nextSibling);
                    }
                    errorDiv.textContent = 'This field is required';
                } else {
                    field.classList.remove('error');
                    const errorDiv = field.nextElementSibling;
                    if (errorDiv && errorDiv.classList.contains('error-message')) {
                        errorDiv.remove();
                    }
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                
                // Scroll to first error
                const firstError = this.querySelector('.error');
                if (firstError) {
                    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        });
    });
}

/**
 * Initialize date pickers
 */
function initDatePickers() {
    const dateInputs = document.querySelectorAll('input[type="date"]');
    
    dateInputs.forEach(input => {
        // Set default value if empty
        if (!input.value) {
            const today = new Date();
            const year = today.getFullYear();
            const month = String(today.getMonth() + 1).padStart(2, '0');
            const day = String(today.getDate()).padStart(2, '0');
            input.value = `${year}-${month}-${day}`;
        }
    });
}

/**
 * Initialize search functionality
 */
function initSearch() {
    const searchInputs = document.querySelectorAll('.search-bar input');
    
    searchInputs.forEach(input => {
        // Add search on Enter key
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const searchParams = new URLSearchParams(window.location.search);
                searchParams.set('search', this.value);
                window.location.search = searchParams.toString();
            }
        });
        
        // Add search button if present
        const searchButton = input.closest('.search-bar')?.querySelector('i');
        if (searchButton) {
            searchButton.addEventListener('click', function() {
                const searchParams = new URLSearchParams(window.location.search);
                searchParams.set('search', input.value);
                window.location.search = searchParams.toString();
            });
        }
    });
}

/**
 * Format currency
 */
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}

/**
 * Format date
 */
function formatDate(date) {
    return new Intl.DateTimeFormat('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(new Date(date));
}

/**
 * Show loading spinner
 */
function showLoading(container) {
    const spinner = document.createElement('div');
    spinner.className = 'spinner';
    spinner.style.margin = '20px auto';
    
    if (container) {
        container.innerHTML = '';
        container.appendChild(spinner);
    }
    
    return spinner;
}

/**
 * Hide loading spinner
 */
function hideLoading(spinner) {
    if (spinner) {
        spinner.remove();
    }
}

/**
 * Show notification message
 */
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.innerHTML = `
        <i class="fa-solid fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
        <span>${message}</span>
    `;
    
    // Style for floating notification
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '9999';
    notification.style.minWidth = '300px';
    notification.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
    notification.style.animation = 'slideIn 0.3s ease';
    
    document.body.appendChild(notification);
    
    // Auto hide after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Export functions for use in other scripts
window.inventoryManager = {
    formatCurrency,
    formatDate,
    showNotification,
    showLoading,
    hideLoading
};