"""
Sales routes — create, edit, view sales history, and generate invoices.
When a sale is created the route also:
  1. Creates the customer if they are new.
  2. Decrements inventory stock for the chosen battery.
  3. Creates a warranty record.
  4. Calculates profit and stores invoice number.

Pricing logic:
  actual_price    = full battery price (before exchange)
  old_battery_value = value of old battery exchanged
  final_amount    = actual_price - old_battery_value  (what customer pays)
  profit          = actual_price - purchase_price       (shop's margin)
"""

from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.db import get_db

sales_bp = Blueprint("sales", __name__, url_prefix="/sales")


# ─── Helper: backward-compatible sale normalization ─────────
def normalize_sale(sale, db=None):
    """
    Ensure a sale dict has actual_price, old_battery_value, final_amount,
    and invoice_number — even for old records that only have 'price'.
    Optionally persists generated invoice_number back to DB.
    """
    old_bat = sale.get("old_battery_value", 0) or 0

    if "actual_price" in sale:
        actual_price = sale["actual_price"]
    elif "selling_price" in sale:
        # Very old records that used selling_price
        actual_price = sale["selling_price"] + old_bat
    elif "price" in sale:
        # Records that used price (= final amount customer paid)
        actual_price = sale["price"] + old_bat
    else:
        actual_price = 0

    final_amount = actual_price - old_bat
    sale["actual_price"] = actual_price
    sale["old_battery_value"] = old_bat
    sale["final_amount"] = final_amount

    # Invoice number — generate if missing
    if not sale.get("invoice_number"):
        inv_num = _generate_invoice_number(db) if db is not None else "INV-0000"
        sale["invoice_number"] = inv_num
        # Persist back to DB
        if db is not None and "_id" in sale:
            db.sales.update_one(
                {"_id": sale["_id"]},
                {"$set": {"invoice_number": inv_num, "actual_price": actual_price}}
            )

    return sale


def _generate_invoice_number(db):
    """Generate next sequential invoice number like INV-0001."""
    # Find the highest existing invoice number
    last = db.sales.find(
        {"invoice_number": {"$exists": True, "$ne": ""}},
    ).sort("invoice_number", -1).limit(1)

    last_list = list(last)
    if last_list and last_list[0].get("invoice_number", "").startswith("INV-"):
        try:
            num = int(last_list[0]["invoice_number"].split("-")[1]) + 1
        except (ValueError, IndexError):
            num = 1
    else:
        # Count existing sales as starting point
        num = db.sales.count_documents({}) or 1

    return f"INV-{str(num).zfill(4)}"


@sales_bp.route("/history")
def sales_history():
    """Show all sales with date range filters, search, and profit tracking."""
    db = get_db()

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
            date_filter["$lte"] = datetime.strptime(date_to, "%d/%m/%Y") + timedelta(days=1)
        except ValueError:
            pass
    if date_filter:
        filter_query["date"] = date_filter

    # Fetch sales
    sales = list(db.sales.find(filter_query).sort("date", -1))

    # Bulk-fetch customer names (avoid N+1)
    for sale in sales:
        normalize_sale(sale, db)
    customer_ids = [s.get("customer_id") for s in sales if s.get("customer_id")]
    customer_map = {}
    if customer_ids:
        for c in db.customers.find({"_id": {"$in": customer_ids}}, {"name": 1, "phone": 1}):
            customer_map[c["_id"]] = c
    for sale in sales:
        c = customer_map.get(sale.get("customer_id"), {})
        sale["customer_name"] = c.get("name", "Unknown")
        sale["customer_phone"] = c.get("phone", "")

    # Apply search filter in Python (post-fetch)
    filtered_sales = []
    ql = query.lower() if query else ""
    for sale in sales:
        if ql and (
            ql not in sale["customer_name"].lower()
            and ql not in sale.get("battery_model", "").lower()
            and ql not in sale.get("customer_phone", "")
        ):
            continue
        filtered_sales.append(sale)

    # Summary stats
    total_count = len(filtered_sales)
    total_revenue = sum(s.get("final_amount", s.get("price", 0)) for s in filtered_sales)
    total_profit = sum(s.get("profit", 0) for s in filtered_sales)

    return render_template(
        "sales_history.html",
        sales=filtered_sales,
        query=query,
        date_from=date_from,
        date_to=date_to,
        total_count=total_count,
        total_revenue=total_revenue,
        total_profit=total_profit,
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
        actual_price = request.form.get("actual_price", "").strip()
        payment_mode = request.form.get("payment_mode", "").strip()
        service = request.form.get("service", "").strip()
        old_battery_value = request.form.get("old_battery_value", "0").strip()

        # ── Validation ───────────────────────────────────────
        if not all([phone, battery_id, serial_number, actual_price, payment_mode, service]):
            flash("All sale fields are required.", "error")
            return redirect(url_for("sales.add_sale"))

        if is_new_customer == "true":
            if not all([name, vehicle, vehicle_number]):
                flash("Customer name, vehicle, and vehicle number are required for new customers.", "error")
                return redirect(url_for("sales.add_sale"))

        try:
            actual_price = float(actual_price)
            old_battery_value = float(old_battery_value) if old_battery_value else 0
        except ValueError:
            flash("Price and old battery value must be numbers.", "error")
            return redirect(url_for("sales.add_sale"))

        # Parse sale date
        try:
            sale_date = datetime.strptime(sale_date_str, "%d/%m/%Y")
        except (ValueError, TypeError):
            sale_date = datetime.combine(date.today(), datetime.min.time())

        # ── 1) Handle customer ───────────────────────────────
        if is_new_customer == "true":
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

        # ── 3) Calculate pricing ─────────────────────────────
        purchase_price = battery.get("purchase_price", 0)
        final_amount = actual_price - old_battery_value
        profit = actual_price - purchase_price

        # ── 4) Generate invoice number ───────────────────────
        invoice_number = _generate_invoice_number(db)

        # ── 5) Insert sale record ────────────────────────────
        sale_doc = {
            "date": sale_date,
            "invoice_number": invoice_number,
            "customer_id": customer_oid,
            "battery_id": ObjectId(battery_id),
            "battery_model": f"{battery['brand']} {battery['model']}",
            "serial_number": serial_number,
            "actual_price": actual_price,
            "old_battery_value": old_battery_value,
            "price": final_amount,  # backward compat — final amount
            "purchase_price": purchase_price,
            "profit": profit,
            "payment_mode": payment_mode,
            "service": service,
        }
        result = db.sales.insert_one(sale_doc)

        # ── 6) Decrement stock ───────────────────────────────
        db.inventory.update_one(
            {"_id": ObjectId(battery_id)},
            {"$inc": {"stock": -1}},
        )

        # ── 7) Create warranty entry ────────────────────────
        warranty_months = battery.get("warranty_months", 12)
        expiry_date = sale_date + relativedelta(months=warranty_months) - timedelta(days=1)
        
        warranty_doc = {
            "customer_id": customer_oid,
            "battery_model": f"{battery['brand']} {battery['model']}",
            "serial_number": serial_number,
            "purchase_date": sale_date,
            "expiry_date": expiry_date,
            "warranty_months": warranty_months,
        }
        db.warranties.insert_one(warranty_doc)

        flash(f"Sale recorded! Invoice: {invoice_number}", "success")
        return redirect(url_for("sales.view_invoice", sale_id=result.inserted_id))

    # GET — prepare dropdown data
    batteries = list(db.inventory.find({"stock": {"$gt": 0}}))
    today = date.today().strftime("%d/%m/%Y")
    return render_template("add_sale.html", batteries=batteries, today=today)


# ─── Edit Sale ──────────────────────────────────────────────
@sales_bp.route("/edit/<sale_id>", methods=["GET", "POST"])
def edit_sale(sale_id):
    db = get_db()
    sale = db.sales.find_one({"_id": ObjectId(sale_id)})
    if not sale:
        flash("Sale not found.", "error")
        return redirect(url_for("sales.sales_history"))

    if request.method == "POST":
        serial_number = request.form.get("serial_number", "").strip()
        actual_price = request.form.get("actual_price", "").strip()
        payment_mode = request.form.get("payment_mode", "").strip()
        service = request.form.get("service", "").strip()
        old_battery_value = request.form.get("old_battery_value", "0").strip()
        battery_id = request.form.get("battery_id", "").strip()

        if not all([serial_number, actual_price, payment_mode, service]):
            flash("All fields are required.", "error")
            return redirect(url_for("sales.edit_sale", sale_id=sale_id))

        try:
            actual_price = float(actual_price)
            old_battery_value = float(old_battery_value) if old_battery_value else 0
        except ValueError:
            flash("Price must be a number.", "error")
            return redirect(url_for("sales.edit_sale", sale_id=sale_id))

        # ── Determine if battery changed ────────────────────
        new_battery = db.inventory.find_one({"_id": ObjectId(battery_id)}) if battery_id else None
        old_battery_id = sale.get("battery_id")

        battery_actually_changed = False
        if new_battery:
            if old_battery_id:
                battery_actually_changed = str(new_battery["_id"]) != str(old_battery_id)
            else:
                new_model = f"{new_battery['brand']} {new_battery['model']}"
                battery_actually_changed = new_model != sale.get("battery_model", "")

        final_amount = actual_price - old_battery_value

        update_fields = {
            "serial_number": serial_number,
            "actual_price": actual_price,
            "old_battery_value": old_battery_value,
            "price": final_amount,
            "payment_mode": payment_mode,
            "service": service,
        }

        if battery_actually_changed and new_battery:
            if new_battery.get("stock", 0) < 1:
                flash("New battery is out of stock!", "error")
                return redirect(url_for("sales.edit_sale", sale_id=sale_id))

            if old_battery_id:
                db.inventory.update_one(
                    {"_id": ObjectId(old_battery_id)},
                    {"$inc": {"stock": 1}},
                )
            db.inventory.update_one(
                {"_id": new_battery["_id"]},
                {"$inc": {"stock": -1}},
            )

            update_fields["battery_id"] = new_battery["_id"]
            update_fields["battery_model"] = f"{new_battery['brand']} {new_battery['model']}"
            update_fields["purchase_price"] = new_battery.get("purchase_price", 0)

            db.warranties.update_one(
                {"serial_number": sale.get("serial_number"), "customer_id": sale.get("customer_id")},
                {"$set": {
                    "battery_model": f"{new_battery['brand']} {new_battery['model']}",
                    "serial_number": serial_number,
                }}
            )
        else:
            if new_battery and not old_battery_id:
                update_fields["battery_id"] = new_battery["_id"]
                update_fields["purchase_price"] = new_battery.get("purchase_price", 0)

            if serial_number != sale.get("serial_number"):
                db.warranties.update_one(
                    {"serial_number": sale.get("serial_number"), "customer_id": sale.get("customer_id")},
                    {"$set": {"serial_number": serial_number}}
                )

        # Recalculate profit
        purchase_price = update_fields.get("purchase_price", sale.get("purchase_price", 0))
        update_fields["profit"] = actual_price - purchase_price

        db.sales.update_one({"_id": ObjectId(sale_id)}, {"$set": update_fields})
        flash("Sale updated successfully!", "success")
        return redirect(url_for("sales.sales_history"))

    # GET — normalize sale for form display
    normalize_sale(sale, db)
    customer = db.customers.find_one({"_id": sale.get("customer_id")})
    batteries = list(db.inventory.find())
    return render_template("edit_sale.html", sale=sale, customer=customer, batteries=batteries)


# ─── Invoice View ───────────────────────────────────────────
@sales_bp.route("/invoice/<sale_id>")
def view_invoice(sale_id):
    db = get_db()
    sale = db.sales.find_one({"_id": ObjectId(sale_id)})
    if not sale:
        flash("Sale not found.", "error")
        return redirect(url_for("sales.sales_history"))

    # Normalize for backward compat
    normalize_sale(sale, db)

    customer = db.customers.find_one({"_id": sale.get("customer_id")})

    # Get warranty info
    warranty = db.warranties.find_one({
        "serial_number": sale.get("serial_number"),
        "customer_id": sale.get("customer_id"),
    })

    return render_template(
        "invoice.html",
        sale=sale,
        customer=customer,
        warranty=warranty,
    )
