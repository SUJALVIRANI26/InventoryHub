/* ============================================================
   InventoryHub – sales/static/sales/order_form.js

   This is a direct port of the original inline <script> that
   worked correctly, with two additions:

   1. productData map  – so price fills in EDIT mode too
      (Django renders existing rows without data-price on options,
       so we read from the hidden template instead).

   2. Stock warning    – yellow non-blocking hint when quantity
      exceeds available stock; order still submits normally,
      backlog + auto-PO handled server-side.
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

    /* ── 1. PRODUCT DATA MAP ─────────────────────────────────
       Read all options from the hidden template once.
       key  : product id string
       value: { price: float, stock: int }
       price is already the 5%-marked-up sales price written by
       `templates/sales/sales_order_form.html`
    ──────────────────────────────────────────────────────── */
    const productData = {};
    document.querySelectorAll('#empty-item-template option').forEach(function (opt) {
        if (opt.value) {
            productData[opt.value] = {
                price: parseFloat(opt.getAttribute('data-price') || 0),
                stock: parseInt(opt.getAttribute('data-stock')  || 9999),
            };
        }
    });

    /* ── 2. APPLY form-control CLASS ─────────────────────────
       Exactly as the original did.
    ──────────────────────────────────────────────────────── */
    document.querySelectorAll('input, select, textarea').forEach(function (el) {
        if (!el.classList.contains('form-control')
            && el.type !== 'hidden'
            && el.type !== 'checkbox'
            && !el.classList.contains('remove-item')) {
            el.classList.add('form-control');
        }
    });

    /* ── 3. DEFAULT VALUES ───────────────────────────────────
       Exactly as the original did.
    ──────────────────────────────────────────────────────── */
    var dateInput = document.querySelector('input[type="date"]');
    if (dateInput && !dateInput.value) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }

    document.querySelectorAll('input[type="number"]').forEach(function (input) {
        if (!input.value) {
            if (input.name.includes('shipping_cost')) {
                input.value = '0.00';
            } else if (input.name.includes('tax_rate')) {
                input.value = '8.00';
            } else if (input.name.includes('quantity') && !input.name.includes('__prefix__')) {
                input.value = '1';
            }
        }
    });

    /* ── 4. ROW TOTAL ────────────────────────────────────────
       Exactly as the original.
    ──────────────────────────────────────────────────────── */
    function calculateRowTotal(row) {
        var priceInput = row.querySelector('[name$="unit_price"]');
        var qtyInput   = row.querySelector('[name$="quantity"]');
        var totalDiv   = row.querySelector('.item-total');

        if (!priceInput || !qtyInput || !totalDiv) return 0;

        var price = parseFloat(priceInput.value) || 0;
        var qty   = parseInt(qtyInput.value)     || 0;
        var total = price * qty;

        totalDiv.textContent = '$' + total.toFixed(2);
        return total;
    }

    /* ── 5. FULL TOTALS ──────────────────────────────────────
       Exactly as the original.
    ──────────────────────────────────────────────────────── */
    function calculateTotals() {
        var subtotal = 0;

        document.querySelectorAll('.order-item-row').forEach(function (row) {
            if (row.style.display !== 'none') {
                subtotal += calculateRowTotal(row);
            }
        });

        var shipping = parseFloat(document.querySelector('[name="shipping_cost"]')?.value) || 0;
        var taxRate  = parseFloat(document.querySelector('[name="tax_rate"]')?.value)      || 0;
        var tax      = subtotal * (taxRate / 100);

        var taxRateDisplay = document.getElementById('tax-rate-display');
        if (taxRateDisplay) taxRateDisplay.textContent = taxRate.toFixed(2);

        document.getElementById('summary-subtotal').textContent = '$' + subtotal.toFixed(2);
        document.getElementById('summary-tax').textContent      = '$' + tax.toFixed(2);
        document.getElementById('summary-shipping').textContent = '$' + shipping.toFixed(2);
        document.getElementById('summary-total').textContent    = '$' + (subtotal + tax + shipping).toFixed(2);
    }

    /* ── 6. PRICE FROM PRODUCT ───────────────────────────────
       Original tried data-price on the option, then regex.
       We keep both strategies but ALSO check productData map
       first — this is what makes edit mode work correctly.
    ──────────────────────────────────────────────────────── */
    function updatePriceFromProduct(select) {
        // This fills the sales price shown in the order form. The price source
        // is already marked up by 5%; it does not use the raw product base price.
        var row        = select.closest('.order-item-row');
        var priceInput = row.querySelector('[name$="unit_price"]');

        if (select.value && priceInput) {
            var price = null;

            // Strategy A: productData map (always works, both create & edit)
            if (productData[select.value]) {
                price = productData[select.value].price;
            }

            // Strategy B: data-price on the option (works for new rows)
            if (price === null) {
                var selectedOption = select.options[select.selectedIndex];
                var attrPrice = selectedOption.getAttribute('data-price');
                if (attrPrice) price = parseFloat(attrPrice);
            }

            // Strategy C: parse price from option text e.g. "Widget ($58000.00)"
            if (price === null) {
                var selectedOption2 = select.options[select.selectedIndex];
                if (selectedOption2 && selectedOption2.text) {
                    var match = selectedOption2.text.match(/\$(\d+(?:\.\d+)?)/);
                    if (match) price = parseFloat(match[1]);
                }
            }

            if (price !== null) {
                priceInput.value = price.toFixed(2);
            }
        } else if (priceInput) {
            priceInput.value = '';
        }

        calculateTotals();
        updateStockWarning(select);
    }

    /* ── 7. STOCK WARNING ────────────────────────────────────
       Non-blocking yellow hint only. Order always goes through.
    ──────────────────────────────────────────────────────── */
    function updateStockWarning(select) {
        if (!select) return;
        var row    = select.closest('.order-item-row');
        if (!row)  return;
        var warnEl = row.querySelector('.stock-warn');
        var qtyEl  = row.querySelector('[name$="quantity"]');
        if (!warnEl || !qtyEl) return;

        var data      = productData[select.value] || null;
        var requested = parseInt(qtyEl.value) || 0;
        var available = data ? data.stock : 9999;

        if (select.value && requested > available) {
            var short = requested - available;
            warnEl.textContent  = available <= 0
                ? '⚠ Out of stock – ' + requested + ' unit(s) will go to backlog.'
                : '⚠ Only ' + available + ' in stock – ' + short + ' unit(s) will go to backlog.';
            warnEl.style.display = 'block';
            showBacklogBanner(true);
        } else {
            warnEl.textContent   = '';
            warnEl.style.display = 'none';
            // only hide banner if NO other row has a warning
            var anyWarn = document.querySelectorAll('.stock-warn');
            var stillWarning = false;
            anyWarn.forEach(function (el) {
                if (el.style.display !== 'none' && el.textContent.trim()) stillWarning = true;
            });
            showBacklogBanner(stillWarning);
        }
    }

    function showBacklogBanner(show) {
        var b = document.getElementById('backlog-banner');
        if (b) b.style.display = show ? 'flex' : 'none';
    }

    /* ── 8. INITIALISE PRODUCT SELECTS ──────────────────────
       Mirrors the original exactly, but calls updatePriceFromProduct
       which now uses the productData map for edit mode.
    ──────────────────────────────────────────────────────── */
    function initializeProductSelects() {
        document.querySelectorAll('.product-select, [name$="product"]').forEach(function (select) {
            var currentValue = select.value;

            // Clone to get a clean element with fresh listeners
            var newSelect       = document.createElement('select');
            newSelect.name      = select.name;
            newSelect.id        = select.id;
            newSelect.className = select.className;
            newSelect.innerHTML = select.innerHTML;
            newSelect.value     = currentValue;

            select.parentNode.replaceChild(newSelect, select);

            newSelect.addEventListener('change', function () {
                updatePriceFromProduct(this);
            });

            // Fill price immediately if a product is already selected (edit mode)
            if (newSelect.value) {
                updatePriceFromProduct(newSelect);
            }
        });
    }

    /* ── 9. QUANTITY INPUTS ──────────────────────────────────
       Mirrors the original exactly, also fires stock warning.
    ──────────────────────────────────────────────────────── */
    function initializeQuantityInputs() {
        document.querySelectorAll('[name$="quantity"]').forEach(function (input) {
            var newInput = input.cloneNode(true);
            input.parentNode.replaceChild(newInput, input);
            newInput.addEventListener('input', function () {
                calculateTotals();
                var row = this.closest('.order-item-row');
                if (row) {
                    var sel = row.querySelector('[name$="product"]');
                    updateStockWarning(sel);
                }
            });
        });
    }

    /* ── 10. REMOVE BUTTONS ──────────────────────────────────
       Exactly as the original.
    ──────────────────────────────────────────────────────── */
    function initializeRemoveButtons() {
        document.querySelectorAll('.remove-item').forEach(function (button) {
            var newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);

            newButton.addEventListener('click', function (e) {
                e.preventDefault();
                var row            = this.closest('.order-item-row');
                var deleteCheckbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');

                if (deleteCheckbox) {
                    deleteCheckbox.checked = true;
                    row.style.display = 'none';
                } else {
                    row.remove();
                }

                var totalForms = document.getElementById('id_items-TOTAL_FORMS');
                if (totalForms) {
                    var visibleRows = document.querySelectorAll('.order-item-row:not([style*="display: none"])').length;
                    totalForms.value = visibleRows;
                }

                calculateTotals();
            });
        });
    }

    /* ── 11. SHIPPING / TAX ──────────────────────────────────
       Exactly as the original.
    ──────────────────────────────────────────────────────── */
    function initializeShippingTax() {
        var shippingInput = document.querySelector('[name="shipping_cost"]');
        if (shippingInput) {
            var newShipping = shippingInput.cloneNode(true);
            shippingInput.parentNode.replaceChild(newShipping, shippingInput);
            newShipping.addEventListener('input', calculateTotals);
        }

        var taxRateInput = document.querySelector('[name="tax_rate"]');
        if (taxRateInput) {
            var newTaxRate = taxRateInput.cloneNode(true);
            taxRateInput.parentNode.replaceChild(newTaxRate, taxRateInput);
            newTaxRate.addEventListener('input', calculateTotals);
        }
    }

    /* ── 12. ADD NEW ROW ─────────────────────────────────────
       Exactly as the original.
    ──────────────────────────────────────────────────────── */
    var addButton   = document.getElementById('add-item');
    var totalForms  = document.getElementById('id_items-TOTAL_FORMS');
    var itemsBody   = document.getElementById('items-body');
    var emptyMessage = document.getElementById('empty-items-message');
    var template    = document.getElementById('empty-item-template');

    if (addButton && totalForms && itemsBody && template) {
        addButton.addEventListener('click', function () {
            var formCount  = parseInt(totalForms.value);
            var newRowHtml = template.innerHTML.replace(/__prefix__/g, formCount);

            var tempDiv       = document.createElement('div');
            tempDiv.innerHTML = newRowHtml;
            var newRow        = tempDiv.firstElementChild;

            if (emptyMessage) emptyMessage.style.display = 'none';

            itemsBody.appendChild(newRow);
            totalForms.value = formCount + 1;

            // Apply form-control to new inputs
            newRow.querySelectorAll('input, select, textarea').forEach(function (el) {
                if (!el.classList.contains('form-control')
                    && el.type !== 'hidden'
                    && el.type !== 'checkbox'
                    && !el.classList.contains('remove-item')) {
                    el.classList.add('form-control');
                }
            });

            var newSelect = newRow.querySelector('.product-select, [name$="product"]');
            if (newSelect) {
                newSelect.addEventListener('change', function () {
                    updatePriceFromProduct(this);
                });
            }

            var newQty = newRow.querySelector('[name$="quantity"]');
            if (newQty) {
                newQty.addEventListener('input', function () {
                    calculateTotals();
                    var row = this.closest('.order-item-row');
                    if (row) updateStockWarning(row.querySelector('[name$="product"]'));
                });
            }

            var newRemoveBtn = newRow.querySelector('.remove-item');
            if (newRemoveBtn) {
                newRemoveBtn.addEventListener('click', function (e) {
                    e.preventDefault();
                    var row            = this.closest('.order-item-row');
                    var deleteCheckbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');

                    if (deleteCheckbox) {
                        deleteCheckbox.checked = true;
                        row.style.display = 'none';
                    } else {
                        row.remove();
                    }

                    var visibleRows = document.querySelectorAll('.order-item-row:not([style*="display: none"])').length;
                    totalForms.value = visibleRows;
                    calculateTotals();
                });
            }

            calculateTotals();
        });
    }

    /* ── 13. FORM VALIDATION ─────────────────────────────────
       Stock shortage is NOT a blocking error. Only missing
       product selection blocks submission.
    ──────────────────────────────────────────────────────── */
    var orderForm = document.getElementById('orderForm');
    if (orderForm) {
        orderForm.addEventListener('submit', function (e) {
            var hasValidProduct = false;
            var visibleRows     = 0;

            document.querySelectorAll('.order-item-row').forEach(function (row) {
                if (row.style.display === 'none') return;
                visibleRows++;
                var productSelect = row.querySelector('[name$="product"]');
                if (productSelect && productSelect.value) {
                    hasValidProduct = true;
                    productSelect.classList.remove('is-invalid');
                } else if (productSelect) {
                    productSelect.classList.add('is-invalid');
                }
            });

            if (visibleRows === 0) {
                e.preventDefault();
                alert('Please add at least one item to the order.');
                return;
            }

            if (!hasValidProduct) {
                e.preventDefault();
                alert('Please select a product for each item.');
                return;
            }
            // Stock shortage → let through; server handles backlog + auto-PO
        });
    }

    /* ── 14. BOOT ────────────────────────────────────────────
       Run everything exactly as the original did.
    ──────────────────────────────────────────────────────── */
    initializeProductSelects();   // fills prices for existing rows (edit mode)
    initializeQuantityInputs();
    initializeRemoveButtons();
    initializeShippingTax();
    calculateTotals();            // recalculate after prices are filled
});
