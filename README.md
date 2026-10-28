# ShopNest — E-Commerce Web Application

A full-stack demo store built with Python, Flask, SQLAlchemy, MySQL, HTML, CSS, and JavaScript.

## Features

- Product catalog, search, and category filter
- Session-based shopping cart
- Registration, login, hashed passwords, and admin/user roles
- Admin product create/edit/hide and stock management
- Checkout with stock validation and transactional order creation
- Order history, order detail, order status tracking
- Admin order status updates; stock is restored when an order is cancelled
- Responsive UI for desktop and mobile

## Requirements

- Python 3.10+
- MySQL Server 8+ (or a compatible MySQL server)
- pip

## 1. Create the MySQL database/user

Open MySQL Workbench or a MySQL terminal and run `schema.sql`. It creates:
- database `ecommerce_db`
- user `ecommerce_user`
- password `change_this_password`

For a real project, change that password and use a dedicated database user with only the required permissions. If you already manage MySQL users yourself, create the database and user manually instead.

## 2. Configure environment variables

Linux/macOS:
```bash
cp .env.example .env
```

Windows PowerShell:
```powershell
Copy-Item .env.example .env
```

Edit `.env`. Set a long random `SECRET_KEY`, and update `DATABASE_URL` if your MySQL username/password/host differ. To set up an admin, add these lines:
```dotenv
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=use-a-long-unique-password
```

Do not commit `.env` to Git.

## 3. Create a virtual environment and install dependencies

Windows:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 4. Create tables and seed sample products

Run these commands from the project folder after activating the virtual environment:

```bash
flask --app app init-db
flask --app app seed
```

The `seed` command adds four sample products and creates/promotes the configured admin account if `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set in `.env`. If you set the admin variables after the first seed, run the seed command again.

If you change the database URL, ensure the target database already exists and is reachable.

## 5. Start the app

```bash
flask --app app run --debug
```

Open `http://127.0.0.1:5000`.

For local development only, you can instead run `python app.py`; debug mode is off by default. Do not use Flask's development server in production.

## 6. Test the app

1. Open the shop page and browse/search products.
2. Register a normal customer account.
3. Add products to the cart and change quantities.
4. Check out with a delivery name and address.
5. Open **My orders** to view the order and progress.
6. Log out and sign in using the admin email/password configured in `.env`.
7. Open **Admin** to create/edit/hide products and update order statuses.

The admin is created by the `flask --app app seed` command from the credentials in `.env`; public registration always creates a normal user.

## Routes overview

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Product catalog/search |
| GET/POST | `/register` | Create customer account |
| GET/POST | `/login` | Sign in |
| POST | `/logout` | Sign out |
| GET | `/cart` | View cart |
| POST | `/cart/add/<id>` | Add item |
| POST | `/cart/update/<id>` | Update quantity |
| POST | `/cart/remove/<id>` | Remove item |
| GET/POST | `/checkout` | Place order |
| GET | `/orders` | Order history (admin sees all) |
| GET | `/orders/<id>` | Order details/tracking |
| GET | `/admin` | Admin dashboard |
| GET/POST | `/admin/products/new` | Add product |
| GET/POST | `/admin/products/<id>/edit` | Edit product |
| POST | `/admin/products/<id>/toggle` | Hide/publish product |
| POST | `/admin/orders/<id>/status` | Update order status |

## Important notes before production

This is a learning project, not a production-ready commerce platform.

- The demo checkout does not collect payments or integrate a payment gateway.
- Add CSRF protection (for example, Flask-WTF), rate limiting, email verification, password reset, logging, tests, and secure deployment settings before public launch.
- Set `SESSION_COOKIE_SECURE=True` behind HTTPS in production.
- Use migrations (for example, Flask-Migrate) instead of relying on `create_all` when changing schemas.
- Product images use external Unsplash URLs in the demo; use validated uploads or trusted image hosting for a real deployment.
- The demo allows a simple order-status workflow. Production systems need stricter status transitions, refunds, shipping integration, and audit logs.
- Keep all prices and stock validation on the server. Never trust prices sent by the browser.
