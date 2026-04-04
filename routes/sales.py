"""
Sales routes — create a new sale.
When a sale is created the route also:
  1. Creates the customer if they are new.
  2. Decrements inventory stock for the chosen battery.
  3. Creates a warranty record (expiry = purchase_date + 1 year).
"""

from datetime import datetime, timedelta
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.db import get_db

sales_bp = Blueprint("sales", __name__, url_prefix="/sales")

# Warranty period in days (default 1 year)
WARRANTY_DAYS = 365


@sales_bp.route("/history")
def sales_history():
    """Show all sales with date range filters and search."""
    db = get_db()
    from datetime import date

    # Read filter params
    query = request.args.get("q", "").strip()
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()

    filter_query = {}

    # Date range filter
    date_filter = {}
    if date_from:
        try:
            date_filter["$gte"] = datetime.strptime(date_from, "%d/%m/%Y")
        except ValueError:
            pass
    if date_to:
        try:
            # Include the entire "to" day
            date_filter["$lte"] = datetime.strptime(date_to, "%d/%m/%Y") + timedelta(days=1)
        except ValueError:
            pass
    if date_filter:
        filter_query["date"] = date_filter

    # Fetch sales
    sales = list(db.sales.find(filter_query).sort("date", -1))

    # Attach customer names and apply search filter
    filtered_sales = []
    for sale in sales:
        customer = db.customers.find_one({"_id": sale.get("customer_id")})
        sale["customer_name"] = customer["name"] if customer else "Unknown"
        sale["customer_phone"] = customer["phone"] if customer else ""

        # If search query, filter by customer name or battery model
        if query:
            if (query.lower() not in sale["customer_name"].lower()
                    and query.lower() not in sale.get("battery_model", "").lower()
                    and query not in sale.get("customer_phone", "")):
                continue
        filtered_sales.append(sale)

    # Summary stats for the filtered results
    total_count = len(filtered_sales)
    total_revenue = sum(s.get("price", 0) for s in filtered_sales)

    return render_template(
        "sales_history.html",
        sales=filtered_sales,
        query=query,
        date_from=date_from,
        date_to=date_to,
        total_count=total_count,
        total_revenue=total_revenue,
    )


@sales_bp.route("/add", methods=["GET", "POST"])
def add_sale():
    db = get_db()

    if request.method == "POST":
        # ── Customer fields ──────────────────────────────────
        is_new_customer = request.form.get("is_new_customer", "true")
        customer_id = request.form.get("customer_id", "").strip()
        phone = request.form.get("phone", "").strip()
        name = request.form.get("name", "").strip()
        vehicle = request.form.get("vehicle", "").strip()
        vehicle_number = request.form.get("vehicle_number", "").strip()

        # ── Sale fields ──────────────────────────────────────
        sale_date_str = request.form.get("sale_date", "").strip()
        battery_id = request.form.get("battery_id", "").strip()
        serial_number = request.form.get("serial_number", "").strip()
        price = request.form.get("price", "").strip()
        payment_mode = request.form.get("payment_mode", "").strip()
        service = request.form.get("service", "").strip()

        # ── Validation ───────────────────────────────────────
        if not all([phone, battery_id, serial_number, price, payment_mode, service]):
            flash("All sale fields are required.", "error")
            return redirect(url_for("sales.add_sale"))

        # If new customer, validate customer fields too
        if is_new_customer == "true":
            if not all([name, vehicle, vehicle_number]):
                flash("Customer name, vehicle, and vehicle number are required for new customers.", "error")
                return redirect(url_for("sales.add_sale"))

        try:
            price = float(price)
        except ValueError:
            flash("Price must be a number.", "error")
            return redirect(url_for("sales.add_sale"))

        # Parse the sale date (defaults to today if invalid)
        try:
            sale_date = datetime.strptime(sale_date_str, "%d/%m/%Y")
        except (ValueError, TypeError):
            sale_date = datetime.combine(date.today(), datetime.min.time())

        # ── 1) Handle customer ───────────────────────────────
        if is_new_customer == "true":
            # Check if phone already exists (edge case)
            existing = db.customers.find_one({"phone": phone})
            if existing:
                customer_oid = existing["_id"]
            else:
                result = db.customers.insert_one({
                    "name": name,
                    "phone": phone,
                    "vehicle": vehicle,
                    "vehicle_number": vehicle_number,
                    "created_at": datetime.utcnow(),
                })
                customer_oid = result.inserted_id
        else:
            if not customer_id:
                flash("Customer not found. Please search again.", "error")
                return redirect(url_for("sales.add_sale"))
            customer_oid = ObjectId(customer_id)

        # ── 2) Validate battery & stock ──────────────────────
        battery = db.inventory.find_one({"_id": ObjectId(battery_id)})
        if not battery:
            flash("Selected battery not found.", "error")
            return redirect(url_for("sales.add_sale"))

        if battery.get("stock", 0) < 1:
            flash("This battery is out of stock!", "error")
            return redirect(url_for("sales.add_sale"))

        # ── 3) Insert sale record ────────────────────────────
        sale_doc = {
            "date": sale_date,
            "customer_id": customer_oid,
            "battery_model": f"{battery['brand']} {battery['model']}",
            "serial_number": serial_number,
            "price": price,
            "payment_mode": payment_mode,
            "service": service,
        }
        db.sales.insert_one(sale_doc)

        # ── 4) Decrement stock ───────────────────────────────
        db.inventory.update_one(
            {"_id": ObjectId(battery_id)},
            {"$inc": {"stock": -1}},
        )

        # ── 5) Create warranty entry ────────────────────────
        warranty_months = battery.get("warranty_months", 12)
        warranty_days = warranty_months * 30  # approximate
        warranty_doc = {
            "customer_id": customer_oid,
            "battery_model": f"{battery['brand']} {battery['model']}",
            "serial_number": serial_number,
            "purchase_date": sale_date,
            "expiry_date": sale_date + timedelta(days=warranty_days),
            "warranty_months": warranty_months,
        }
        db.warranties.insert_one(warranty_doc)

        flash("Sale recorded successfully!", "success")
        return redirect(url_for("dashboard.index"))

    # GET — prepare dropdown data
    batteries = list(db.inventory.find({"stock": {"$gt": 0}}))
    from datetime import date
    today = date.today().strftime("%d/%m/%Y")
    return render_template("add_sale.html", batteries=batteries, today=today)
