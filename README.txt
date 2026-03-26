InventoryHub - Project README
==============================

Overview
--------
InventoryHub is a Django-based inventory management platform with:
- A role-based UI for admins, inventory managers, sales staff, and owners.
- Accounts system with OTP-based password reset via email.
- Product, supplier, purchase order, and sales order management workflows.

It supports multiple user roles (Admin, Inventory Manager, Sales, Owner)
with role-specific dashboards and access controls.

Tech Stack
----------
- Python (recommended 3.9+)
- Django 6.0.3
- pymysql (MySQL database driver)
- django-environ (loads .env)
- SQLite (default for local dev) / MySQL (production)
- Gmail SMTP (OTP and email notifications)

Project Layout (High Level)
---------------------------
- inventory_project/inventory_system/    Django settings and URL routing
- inventory_project/accounts/            Auth flows (login, OTP, password reset)
- inventory_project/admin_panel/         Admin user management (add/edit/delete users)
- inventory_project/inventory_manager/   Products, suppliers, purchase orders, backlog
- inventory_project/sales/               Customers, sales orders, order items
- inventory_project/owner/               Owner dashboard and reports

Core Features
-------------
Accounts flow:
- Login: /
- Forgot password / OTP verification / Reset password
- Logout

Admin Panel flow:
- Manage users: /admin-panel/users/
- Add, edit, delete users

Inventory Manager flow:
- Manage products (name, SKU, category, supplier, price, quantity, minimum stock)
- Manage suppliers (contact info, status: active/limited/inactive)
- Purchase orders (pending → ordered → delivered / cancelled)
- Auto-generated POs when stock falls below minimum_stock
- Backlog management: stock never goes negative; shortfalls create backlog entries
  that are automatically fulfilled (FIFO) when new stock arrives

Sales flow:
- Manage customers (individual / business, full contact and billing info)
- Create and manage sales orders with multiple line items
- Sales price auto-applied at 5% markup over base product price
- Order statuses: pending → processing → shipped → completed / cancelled
- Payment methods: Credit Card, Debit Card, Cash, Bank Transfer, PayPal, Check
- Shipping methods: Standard, Express, Store Pickup
- Backordered items tracked per order item; auto-resolved on stock replenishment

Owner flow:
- Dashboard with revenue, sales, and stock overview: /owner/
- Reports: daily, weekly, monthly, yearly, profit/loss, purchase, stock, top products

Django Admin:
- /admin/

URLs (Common)
-------------
- Login (home):              /
- Logout:                    /logout/
- Forgot Password:           /forgot-password/
- OTP Verification:          /verify-otp/
- Reset Password:            /reset-password/
- Admin Panel - Users:       /admin-panel/users/
- Sales Dashboard:           /sales/
- Inventory Manager:         /inventory_manager/
- Owner Dashboard:           /owner/
- Django Admin:              /admin/

Setup (Local Development)
-------------------------
1) Create and activate a virtual environment

2) Install dependencies
   pip install -r requirement.txt
   - At minimum:
     pip install django pymysql django-environ

3) Configure environment variables
   - The app loads .env from inventory_project/.env if present
   - Do NOT commit real secrets. Use placeholders locally.

   Common variables:
   - DATABASE_URL        (e.g. mysql://user:password@127.0.0.1:3306/inv)
                         Leave empty or omit to use default SQLite

   Email variables (set directly in settings.py or via .env):
   - EMAIL_HOST_USER     (Gmail address used for OTP emails)
   - EMAIL_HOST_PASSWORD (Gmail App Password — not your account password)
   - DEFAULT_FROM_EMAIL

4) Run migrations
   - From inventory_project/:
     python manage.py migrate

5) Create a superuser / admin
   - python manage.py createsuperuser

6) Run the server
   - python manage.py runserver

Notes on Stock and Backlog Behaviour
-------------------------------------
- Product stock (quantity) never goes below 0.
- When a sales order item requests more units than available:
  - Available units are deducted immediately.
  - The shortfall is recorded as a BacklogEntry.
  - An auto-generated Purchase Order (PO) is created if the product
    has an active supplier and no ordered PO already exists.
- When new stock arrives (PO delivered or manual quantity edit):
  - Open backlog entries are fulfilled FIFO automatically.
  - The product's on-hand quantity is updated accordingly.
- Stale or orphan backlog rows are cleaned up automatically to prevent
  hidden rows from consuming future delivered stock.

Known Assumptions
-----------------
- This README assumes Python 3.9+ and a local dev setup.
- Default database is SQLite; set DATABASE_URL in .env for MySQL.
- Gmail SMTP is configured in settings.py; update credentials before use.
- If your environment differs, adjust accordingly.
