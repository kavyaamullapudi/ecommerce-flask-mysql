import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
db = SQLAlchemy()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://ecommerce_user:change_this_password@localhost:3306/ecommerce_db?charset=utf8mb4",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
db.init_app(app)

ORDER_STATUSES = ["Pending", "Confirmed", "Shipped", "Delivered", "Cancelled"]


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    category = db.Column(db.String(80), nullable=False, default="General")
    image_url = db.Column(db.String(500), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending")
    shipping_name = db.Column(db.String(100), nullable=False)
    shipping_address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship("User", backref=db.backref("orders", lazy=True))
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan", lazy=True)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
    product_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)


def current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


@app.context_processor
def inject_user():
    return {"current_user": current_user(), "cart_count": sum(int(q) for q in session.get("cart", {}).values())}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Please log in first.", "info")
            return redirect(url_for("login"))
        if user.role != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def parse_price(value):
    try:
        price = Decimal(value).quantize(Decimal("0.01"))
        if not price.is_finite() or price < 0:
            raise ValueError
        return price
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Enter a valid non-negative price.")


def product_form_data():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "General").strip() or "General"
    image_url = request.form.get("image_url", "").strip()
    if not name:
        raise ValueError("Product name is required.")
    try:
        stock = int(request.form.get("stock", "0"))
        if stock < 0:
            raise ValueError
    except ValueError:
        raise ValueError("Stock must be a non-negative whole number.")
    return {
        "name": name,
        "description": description,
        "category": category[:80],
        "image_url": image_url[:500] or None,
        "price": parse_price(request.form.get("price", "")),
        "stock": stock,
    }


@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    query = Product.query.filter_by(active=True)
    if search:
        pattern = f"%{search}%"
        query = query.filter(db.or_(Product.name.ilike(pattern), Product.description.ilike(pattern)))
    if category:
        query = query.filter_by(category=category)
    products = query.order_by(Product.created_at.desc()).all()
    categories = [row[0] for row in db.session.query(Product.category).filter_by(active=True).distinct().order_by(Product.category).all()]
    return render_template("index.html", products=products, categories=categories, search=search, selected_category=category)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or len(name) > 100 or not email or len(email) > 255:
            flash("Please enter a valid name and email.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(name=name, email=email, role="user")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            session.clear()
            session["user_id"] = user.id
            flash("Account created successfully.", "success")
            return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session.clear()
            session["user_id"] = user.id
            flash("Welcome back!", "success")
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("index"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/cart")
def cart():
    cart_data = session.get("cart", {})
    items, total = [], Decimal("0.00")
    for product_id, quantity in cart_data.items():
        product = db.session.get(Product, int(product_id))
        if product and product.active and int(quantity) > 0:
            subtotal = product.price * int(quantity)
            items.append({"product": product, "quantity": int(quantity), "subtotal": subtotal})
            total += subtotal
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    product = db.session.get(Product, product_id)
    if not product or not product.active:
        abort(404)
    try:
        quantity = int(request.form.get("quantity", "1"))
        if quantity < 1 or quantity > 99:
            raise ValueError
    except ValueError:
        flash("Quantity must be between 1 and 99.", "error")
        return redirect(url_for("index"))
    cart_data = session.get("cart", {})
    new_quantity = int(cart_data.get(str(product_id), 0)) + quantity
    if new_quantity > product.stock:
        flash(f"Only {product.stock} unit(s) currently available.", "error")
    else:
        cart_data[str(product_id)] = new_quantity
        session["cart"] = cart_data
        session.modified = True
        flash(f"{product.name} added to your cart.", "success")
    return redirect(request.referrer if request.referrer and request.referrer.startswith("/") else url_for("index"))


@app.route("/cart/update/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    cart_data = session.get("cart", {})
    if str(product_id) not in cart_data:
        return redirect(url_for("cart"))
    product = db.session.get(Product, product_id)
    try:
        quantity = int(request.form.get("quantity", "1"))
        if quantity < 1 or quantity > 99:
            raise ValueError
        if not product or not product.active or quantity > product.stock:
            raise ValueError
    except ValueError:
        flash("Invalid quantity or insufficient stock.", "error")
    else:
        cart_data[str(product_id)] = quantity
        session["cart"] = cart_data
        session.modified = True
        flash("Cart updated.", "success")
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    cart_data = session.get("cart", {})
    cart_data.pop(str(product_id), None)
    session["cart"] = cart_data
    session.modified = True
    flash("Item removed from cart.", "info")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart_data = session.get("cart", {})
    if not cart_data:
        flash("Your cart is empty.", "info")
        return redirect(url_for("cart"))
    if request.method == "POST":
        shipping_name = request.form.get("shipping_name", "").strip()
        shipping_address = request.form.get("shipping_address", "").strip()
        if not shipping_name or len(shipping_name) > 100 or not shipping_address or len(shipping_address) > 1000:
            flash("Enter a valid shipping name and address.", "error")
            return redirect(url_for("checkout"))
        try:
            total = Decimal("0.00")
            prepared = []
            # Lock product rows during stock validation and decrement.
            for product_id, quantity in cart_data.items():
                product = db.session.execute(
                    select(Product).where(Product.id == int(product_id)).with_for_update()
                ).scalar_one_or_none()
                quantity = int(quantity)
                if not product or not product.active or quantity < 1 or product.stock < quantity:
                    raise ValueError("A product is unavailable or no longer has enough stock. Please update your cart.")
                prepared.append((product, quantity))
                total += product.price * quantity
            order = Order(
                user_id=current_user().id,
                total_amount=total,
                status="Pending",
                shipping_name=shipping_name,
                shipping_address=shipping_address,
            )
            db.session.add(order)
            db.session.flush()
            for product, quantity in prepared:
                order.items.append(OrderItem(
                    product_id=product.id,
                    product_name=product.name,
                    quantity=quantity,
                    unit_price=product.price,
                ))
                product.stock -= quantity
            db.session.commit()
            session["cart"] = {}
            session.modified = True
            flash(f"Order #{order.id} placed successfully.", "success")
            return redirect(url_for("order_detail", order_id=order.id))
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            flash(str(exc) or "Could not place the order.", "error")
        except Exception:
            db.session.rollback()
            app.logger.exception("Checkout failed")
            flash("Checkout failed. Please try again.", "error")
    return render_template("checkout.html", items=cart_items_for_checkout(cart_data))


def cart_items_for_checkout(cart_data):
    items, total = [], Decimal("0.00")
    for product_id, quantity in cart_data.items():
        product = db.session.get(Product, int(product_id))
        if product and product.active:
            subtotal = product.price * int(quantity)
            items.append({"product": product, "quantity": int(quantity), "subtotal": subtotal})
            total += subtotal
    return {"items": items, "total": total}


@app.route("/orders")
@login_required
def orders():
    user = current_user()
    query = Order.query.order_by(Order.created_at.desc())
    if user.role != "admin":
        query = query.filter_by(user_id=user.id)
    return render_template("orders.html", orders=query.all())


@app.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    user = current_user()
    if user.role != "admin" and order.user_id != user.id:
        abort(403)
    return render_template("order_detail.html", order=order)


@app.route("/admin")
@admin_required
def admin_dashboard():
    products = Product.query.order_by(Product.created_at.desc()).all()
    orders = Order.query.order_by(Order.created_at.desc()).limit(20).all()
    return render_template("admin.html", products=products, orders=orders, statuses=ORDER_STATUSES)


@app.route("/admin/products/new", methods=["GET", "POST"])
@admin_required
def product_new():
    if request.method == "POST":
        try:
            product = Product(**product_form_data())
            db.session.add(product)
            db.session.commit()
            flash("Product created.", "success")
            return redirect(url_for("admin_dashboard"))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template("product_form.html", product=None, page_title="Add product")


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def product_edit(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    if request.method == "POST":
        try:
            data = product_form_data()
            for key, value in data.items():
                setattr(product, key, value)
            db.session.commit()
            flash("Product updated.", "success")
            return redirect(url_for("admin_dashboard"))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template("product_form.html", product=product, page_title="Edit product")


@app.route("/admin/products/<int:product_id>/toggle", methods=["POST"])
@admin_required
def product_toggle(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    product.active = not product.active
    db.session.commit()
    flash("Product visibility updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    status = request.form.get("status", "")
    if status not in ORDER_STATUSES:
        flash("Invalid order status.", "error")
    elif order.status in ("Cancelled", "Delivered") and status != order.status:
        flash("Delivered or cancelled orders cannot be changed in this demo.", "error")
    else:
        # Restock only when cancelling for the first time.
        if status == "Cancelled" and order.status != "Cancelled":
            for item in order.items:
                if item.product_id:
                    product = db.session.get(Product, item.product_id)
                    if product:
                        product.stock += item.quantity
        order.status = status
        db.session.commit()
        flash("Order status updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to view this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The page or item could not be found."), 404


@app.cli.command("init-db")
def init_db():
    """Create database tables."""
    db.create_all()
    print("Database tables created.")


@app.cli.command("seed")
def seed():
    """Add demo products and create an admin account if configured."""
    db.create_all()
    if Product.query.count() == 0:
        db.session.add_all([
            Product(name="Classic Backpack", description="Everyday backpack with a laptop sleeve.", price=Decimal("1299.00"), stock=20, category="Accessories", image_url="https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=80"),
            Product(name="Wireless Headphones", description="Comfortable over-ear headphones for daily use.", price=Decimal("2499.00"), stock=15, category="Electronics", image_url="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=80"),
            Product(name="Everyday Sneakers", description="Lightweight sneakers for casual wear.", price=Decimal("1999.00"), stock=12, category="Fashion", image_url="https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=80"),
            Product(name="Ceramic Coffee Mug", description="Minimal ceramic mug for your morning coffee.", price=Decimal("349.00"), stock=30, category="Home", image_url="https://images.unsplash.com/photo-1514228742587-6b1558f2f3d7?auto=format&fit=crop&w=900&q=80"),
        ])
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if admin_email and admin_password:
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            admin = User(name="Store Admin", email=admin_email, role="admin")
            admin.set_password(admin_password)
            db.session.add(admin)
        else:
            admin.role = "admin"
        db.session.commit()
        print(f"Admin account ready: {admin_email}")
    else:
        db.session.commit()
        print("Products seeded. Set ADMIN_EMAIL and ADMIN_PASSWORD in .env, then run flask seed again to create an admin.")
    print("Seed complete.")


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
