# 📦 InventoryHub

<div align="center">

![Django](https://img.shields.io/badge/Django-6.0.3-green?style=for-the-badge&logo=django)
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python)
![MySQL](https://img.shields.io/badge/MySQL-supported-orange?style=for-the-badge&logo=mysql)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**A full-featured inventory management system with role-based access, automated purchase orders, and executive reporting**

[Features](#-features) • [Quick Start](#-quick-start) • [Configuration](#-configuration) • [Architecture](#-architecture) • [Usage](#-usage) • [Project Structure](#-project-structure) • [Database Schema](#-database-schema) • [Contributing](#-contributing)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [User Roles](#-user-roles)
- [Project Structure](#-project-structure)
- [Database Schema](#-database-schema)
- [Testing](#-testing)
- [Contributing](#-contributing)
- [License](#-license)
- [Support](#-support)

---

## 🎯 Overview

**InventoryHub** is a Django-based inventory management platform designed for businesses that need tight control over stock, suppliers, sales, and reporting. It combines role-based access control with intelligent automation — automatically generating purchase orders when stock runs low and fulfilling backlogs the moment new stock arrives.

### Key Highlights

- 🔐 **Role-Based Access Control**: Admin, Owner, Manager, and Staff roles with dedicated dashboards
- 📬 **Email Authentication**: OTP-based password reset via Gmail SMTP
- 🏭 **Smart Purchase Orders**: Auto-generated POs when stock falls below minimum threshold
- 🔄 **Backlog Fulfillment**: FIFO backlog resolution triggered automatically on stock arrival
- 📊 **Executive Reporting**: Daily, weekly, monthly, and yearly P&L and KPI dashboards
- 🧾 **Sales Management**: Full order lifecycle with 5% markup pricing and backorder tracking
- 🏷️ **SKU-Based Inventory**: Product tracking with category and supplier associations

---

## ✨ Features

### For Managers 🗂️

- **Inventory Management**
  - Add, edit, and delete products with SKU tracking
  - Category and supplier associations
  - Minimum stock threshold configuration
  - Low-stock alerts and automatic PO generation

- **Supplier Management**
  - Full supplier profiles (contact, address, status)
  - Active/limited/inactive status tracking
  - Supplier-linked purchase orders

- **Purchase Orders**
  - Manual and auto-generated purchase orders
  - Order status: Pending → Ordered → Delivered → Cancelled
  - Backlog auto-fulfillment on delivery

### For Sales 🛒

- **Customer Management**
  - Individual and business customer profiles
  - Order history, total spent, and last order tracking

- **Sales Orders**
  - Full order lifecycle (Pending → Processing → Shipped → Completed)
  - Multiple payment methods and shipping options
  - Automatic 5% markup on product base price
  - Backorder creation when stock is insufficient

### For Owners 📈

- **Executive Dashboard**
  - Daily, weekly, monthly, yearly revenue reports
  - Profit & loss analysis
  - Stock valuation overview
  - KPI trend tracking

### For Administrators 👨‍💼

- **User Management**
  - Create, edit, and delete user accounts
  - Role assignment (Admin, Owner, Manager, Staff)
  - Contact information management

### Technical Features 🔧

- **Authentication**
  - Email-based login (not username)
  - OTP password reset via Gmail SMTP
  - Custom authentication backend
  - Role-based view decorators

- **Automation**
  - Auto-PO generation on low stock or open backlog
  - FIFO backlog fulfillment on stock increase
  - Orphan backlog row cleanup

---

## 🛠️ Tech Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.9+ | Core programming language |
| **Django** | 6.0.3 | Web framework |
| **PyMySQL** | 1.1.2 | MySQL database driver |
| **django-environ** | 0.13.0 | Environment variable management |

### Frontend

| Technology | Purpose |
|------------|---------|
| **HTML5 / CSS3** | UI structure and styling |
| **JavaScript** | Client-side interactivity and form validation |

### Database

- **SQLite** (Development) — zero-configuration default
- **MySQL** (Production) — configurable via `DATABASE_URL` in `.env`

---

## 🏗️ Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Django Application                        │
├───────────────┬───────────────┬──────────────┬──────────────┤
│   accounts    │  admin_panel  │   inventory  │    sales     │
│  (Auth/OTP)   │ (User Mgmt)   │   _manager   │  (Orders)    │
│               │               │  (Stock/PO)  │              │
└───────────────┴───────────────┴──────┬───────┴──────────────┘
                                       │
                               ┌───────┴───────┐
                               │     owner     │
                               │  (Reporting)  │
                               └───────┬───────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      Database Layer                           │
│                    (SQLite / MySQL)                           │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   External Services                           │
│  - Gmail SMTP (OTP Email)                                    │
│  - MySQL (Production Database)                               │
└─────────────────────────────────────────────────────────────┘
```

### Application Flow

```
User Request
     │
     ├─→ accounts/          → Login, OTP reset, role check
     │
     ├─→ admin_panel/       → User CRUD (ADMIN only)
     │
     ├─→ inventory_manager/ → Products, Suppliers, POs, Backlog (MANAGER)
     │       │
     │       └─→ Auto-PO trigger on low stock
     │           Auto-backlog fulfillment on stock arrival (FIFO)
     │
     ├─→ sales/             → Customers, Sales Orders, Backorders (STAFF)
     │       │
     │       └─→ Backlog entry created when stock insufficient
     │
     └─→ owner/             → P&L reports, KPIs, stock valuation (OWNER)
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- Git
- Virtual environment tool (venv/virtualenv)
- MySQL (optional, SQLite works out of the box)

### Installation (5 Minutes)

```bash
# 1. Clone the repository
git clone <repo-url>
cd InventoryHub

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Navigate to project directory
cd inventory_project

# 6. Run migrations
python manage.py migrate

# 7. Create superuser
python manage.py createsuperuser

# 8. Run development server
python manage.py runserver
```

### Access the Application

| Page | URL |
|------|-----|
| Login | http://127.0.0.1:8000/ |
| Admin Panel | http://127.0.0.1:8000/admin-panel/users/ |
| Inventory Manager | http://127.0.0.1:8000/inventory_manager/ |
| Owner Dashboard | http://127.0.0.1:8000/owner/ |
| Django Admin | http://127.0.0.1:8000/admin/ |

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file inside `inventory_project/`:

```env
# Django Settings
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database (leave empty to use SQLite)
DATABASE_URL=mysql://user:password@localhost:3306/inventoryhub

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=1
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=InventoryHub <your-email@gmail.com>
```

### Database Configuration

#### SQLite (Default — Development)

No configuration needed. A `db.sqlite3` file is created automatically.

#### MySQL (Optional)

```env
DATABASE_URL=mysql://your_user:your_password@localhost:3306/inventoryhub
```

Install the MySQL client if not already installed:

```bash
pip install mysqlclient
```

### Email Configuration

#### Development (Console Backend)

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

Emails will be printed to the console instead of being sent.

#### Gmail SMTP

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=1
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-specific-password
```

**Note**: For Gmail, you need to generate an [App Password](https://support.google.com/accounts/answer/185833).

---

## 📖 Usage

### For Managers

#### 1. Manage Products
```
Navigate to: /inventory_manager/
- Add products with SKU, category, supplier, price, and minimum stock
- Edit or delete existing products
- Monitor low-stock alerts
```

#### 2. Manage Suppliers
```
Navigate to: /inventory_manager/suppliers/
- Add suppliers with full contact details
- Set supplier status (active / limited / inactive)
- Only active suppliers can be used in purchase orders
```

#### 3. Handle Purchase Orders
```
Navigate to: /inventory_manager/purchase-orders/
- View auto-generated and manual purchase orders
- Mark orders as Ordered → Delivered
- Delivery automatically fulfills open backlogs (FIFO)
```

### For Sales

#### 1. Manage Customers
```
Navigate to: /sales/customers/
- Add individual or business customers
- View order history and total spending
```

#### 2. Create Sales Orders
```
Navigate to: /sales/orders/
- Select customer and add order items
- Unit price is auto-set to product price + 5% markup
- If stock is insufficient, a backlog entry is created automatically
- Track order status: Pending → Processing → Shipped → Completed
```

### For Owners

#### 1. View Reports
```
Navigate to: /owner/
- Switch between daily, weekly, monthly, yearly views
- Review revenue, profit/loss, and stock valuation
- Monitor KPI trends over time
```

### For Administrators

#### 1. Manage Users
```
Navigate to: /admin-panel/users/
- Add new users and assign roles
- Edit contact info and role
- Delete users
```

---

## 👥 User Roles

| Role | Dashboard URL | Access |
|------|--------------|--------|
| **ADMIN** | `/admin-panel/users/` | User management — create, edit, delete, assign roles |
| **MANAGER** | `/inventory_manager/` | Products, suppliers, purchase orders, backlog |
| **OWNER** | `/owner/` | Executive reports, P&L, KPIs, stock valuation |
| **STAFF** | `/sales/` | Sales-facing operations |

### Login Flow

1. Navigate to `/` — redirects to the login page
2. Enter your email, password, and select your role
3. On success, you are redirected to your role's dashboard
4. Role mismatch results in an "Unauthorized" error

---

## 📁 Project Structure

```
InventoryHub/
│
├── requirement.txt                  # Python dependencies
└── inventory_project/
    ├── manage.py                    # Django management script
    ├── db.sqlite3                   # SQLite database (dev)
    ├── .env                         # Environment variables
    │
    ├── inventory_system/            # Project config (settings, URLs, WSGI)
    │
    ├── accounts/                    # Auth: login, logout, OTP password reset
    │   ├── backends.py              # Email-based auth backend
    │   ├── decorators.py            # Role-based view decorators
    │   ├── views.py                 # Login, logout, forgot/reset password
    │   └── templates/accounts/     # Login, OTP, reset password templates
    │
    ├── admin_panel/                 # User management (CRUD + role assignment)
    │   ├── models.py                # UserProfile model
    │   ├── views.py                 # User list, add, edit, delete
    │   └── templates/admin_panel/  # User management templates
    │
    ├── inventory_manager/           # Core inventory logic
    │   ├── models.py                # Product, Supplier, Category, PurchaseOrder, BacklogEntry
    │   ├── views.py                 # Inventory CRUD, PO management, backlog
    │   └── templates/              # Inventory UI templates
    │
    ├── sales/                       # Sales and customer management
    │   ├── models.py                # Customer, SalesOrder, SalesOrderItem
    │   ├── views.py                 # Sales order CRUD, customer management
    │   └── templates/              # Sales UI templates
    │
    └── owner/                       # Executive reporting
        ├── views.py                 # Dashboard, P&L, KPI reports
        └── templates/              # Owner dashboard templates
```

---

## 🗄️ Database Schema

### Core Models

#### UserProfile (`admin_panel`)
```python
- id: AutoField (Primary Key)
- user: OneToOneField(User)
- contact: CharField
- role: CharField (ADMIN / OWNER / MANAGER / STAFF)
```

#### Product (`inventory_manager`)
```python
- id: AutoField (Primary Key)
- name: CharField
- sku: CharField (Unique)
- category: ForeignKey(Category)
- supplier: ForeignKey(Supplier)
- price: DecimalField
- quantity: IntegerField  ← never goes below 0
- minimum_stock: IntegerField
```

#### Supplier (`inventory_manager`)
```python
- id: AutoField (Primary Key)
- name: CharField
- supplier_code: CharField
- category: ForeignKey(Category)
- contact_person, email, phone, address, city, state, country: CharField
- status: CharField (active / limited / inactive)
```

#### PurchaseOrder (`inventory_manager`)
```python
- id: AutoField (Primary Key)
- supplier: ForeignKey(Supplier)
- order_date: DateField
- expected_delivery: DateField
- status: CharField (pending / ordered / delivered / cancelled)
- auto_generated: BooleanField
```

#### BacklogEntry (`inventory_manager`)
```python
- id: AutoField (Primary Key)
- product: ForeignKey(Product)
- sales_order_item_id: IntegerField
- sales_order_id: IntegerField
- quantity_ordered: IntegerField
- quantity_on_backlog: IntegerField
- created_at: DateTimeField
- fulfilled_at: DateTimeField (nullable)
```

#### Customer (`sales`)
```python
- id: AutoField (Primary Key)
- name, email, phone, company: CharField
- address, city, state, zip_code, country: CharField
- customer_type: CharField (individual / business)
- status: CharField (active / inactive)
- total_orders: IntegerField
- total_spent: DecimalField
- last_order_date: DateField
```

#### SalesOrder (`sales`)
```python
- id: AutoField (Primary Key)
- customer: ForeignKey(Customer)
- order_date: DateField
- payment_method: CharField (credit_card / debit_card / cash / bank_transfer / paypal / check)
- shipping_method: CharField (standard / express / pickup)
- status: CharField (pending / processing / shipped / completed / cancelled)
- subtotal, tax_rate, shipping_cost, total_amount: DecimalField
```

#### SalesOrderItem (`sales`)
```python
- id: AutoField (Primary Key)
- sales_order: ForeignKey(SalesOrder)
- product: ForeignKey(Product)
- quantity: PositiveIntegerField
- unit_price: DecimalField  ← auto-set to product.price × 1.05
- total_price: DecimalField
- backordered_qty: IntegerField
- deducted_qty: IntegerField
```

### Relationships

```
User ──1:1──> UserProfile

Category ──1:N──> Product
Category ──1:N──> Supplier
Supplier ──1:N──> Product
Supplier ──1:N──> PurchaseOrder
PurchaseOrder ──1:N──> PurchaseOrderItem ──N:1──> Product

Customer ──1:N──> SalesOrder ──1:N──> SalesOrderItem ──N:1──> Product
SalesOrderItem ──1:N──> BacklogEntry ──N:1──> Product
```

---

## 🧪 Testing

### Run Tests

```bash
# Run all tests
python manage.py test

# Run tests for a specific app
python manage.py test accounts
python manage.py test inventory_manager
python manage.py test sales

# Run with coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html
```

### Manual Testing Checklist

#### Authentication
- [ ] Login with valid email, password, and role
- [ ] Login with wrong role (should show "Unauthorized")
- [ ] Forgot password — OTP sent to email
- [ ] OTP verification and password reset
- [ ] Logout

#### Inventory Manager
- [ ] Add a product with minimum stock set
- [ ] Reduce quantity below minimum — auto-PO should be created
- [ ] Deliver a purchase order — backlog should be fulfilled
- [ ] Add/edit/delete suppliers
- [ ] Create manual purchase order

#### Sales
- [ ] Add a customer
- [ ] Create a sales order with sufficient stock
- [ ] Create a sales order with insufficient stock — backlog entry created
- [ ] Cancel an order — stock returned
- [ ] Update order status through lifecycle

#### Admin Panel
- [ ] Add a new user with a role
- [ ] Edit user details and role
- [ ] Delete a user

#### Owner Dashboard
- [ ] View daily / weekly / monthly / yearly reports
- [ ] Verify P&L figures reflect completed sales orders

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/YourFeature`)
3. Commit your changes (`git commit -m 'Add YourFeature'`)
4. Push to the branch (`git push origin feature/YourFeature`)
5. Open a Pull Request

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Write unit tests for new features
- Keep commits atomic and well-described

### Pull Request Process

1. Update `README.md` with details of changes if needed
2. Update documentation for new features
3. Ensure all tests pass
4. Request review from maintainers
5. Squash commits before merging

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Django** - The web framework for perfectionists with deadlines
- **PyMySQL** - Pure Python MySQL client library
- **django-environ** - Twelve-factor inspired environment variable management
- **Contributors** - Thanks to all contributors who helped build this project

---

## 📞 Support

### Documentation

- [Django Documentation](https://docs.djangoproject.com/)
- [django-environ Documentation](https://django-environ.readthedocs.io/)
- [PyMySQL Documentation](https://pymysql.readthedocs.io/)
- [Gmail App Passwords Guide](https://support.google.com/accounts/answer/185833)

### Get Help

- **Issues**: Open a GitHub Issue in the repository
- **Discussions**: Use GitHub Discussions for questions and ideas

---

## 📊 Project Statistics

- **Apps**: 5 (accounts, admin_panel, inventory_manager, sales, owner)
- **Core Models**: 10+
- **User Roles**: 4 (Admin, Owner, Manager, Staff)
- **Supported Databases**: SQLite, MySQL

---
## 👥 Team

### Core Contributors

- **rriddhi09** - admin panel, owner 
- **SUJALVIRANI26** - sales team, account authentication
- **KrishSorathiya** - inventory manager

---

<div align="center">

**Made with ❤️ by the InventoryHub Team**

[⬆ Back to Top](#-inventoryhub)

</div>
