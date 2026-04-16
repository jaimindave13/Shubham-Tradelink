"""
Mechanic routes — manage mechanic accounts (khata system).
Mechanics buy on credit and pay later. This module tracks:
  - Mechanic profiles
  - Credit sales (udhar)
  - Payments received
  - Outstanding balance per mechanic
"""

from datetime import datetime, timedelta, date
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.db import get_db

mechanics_bp = Blueprint("mechanics", __name__, url_prefix="/mechanics")


# ─── List all mechanics with outstanding balances ────────────
@mechanics_bp.route("/")
def list_mechanics():
    db = get_db()
    query = request.args.get("q", "").strip()
    serial_query = request.args.get("serial", "").strip()

    # ── Date filter logic ────────────────────────────────────
    date_filter = request.args.get("date_filter", "all").strip()
    date_from_str = request.args.get("date_from", "").strip()
    date_to_str = request.args.get("date_to", "").strip()

    today = date.today()
    if date_filter == "all":
        filter_start = None
        filter_end = None
    elif date_filter == "last_7":
        filter_start = datetime.combine(today - timedelta(days=7), datetime.min.time())
        filter_end = datetime.combine(today + timedelta(days=1), datetime.min.time())
    elif date_filter == "custom" and date_from_str and date_to_str:
        try:
            filter_start = datetime.strptime(date_from_str, "%d/%m/%Y")
            filter_end = datetime.strptime(date_to_str, "%d/%m/%Y") + timedelta(days=1)
        except ValueError:
            filter_start = datetime.combine(today.replace(day=1), datetime.min.time())
            filter_end = datetime.combine(today + timedelta(days=1), datetime.min.time())
    else:
        # Default: this month
        date_filter = "this_month"
        filter_start = datetime.combine(today.replace(day=1), datetime.min.time())
        filter_end = datetime.combine(today + timedelta(days=1), datetime.min.time())

    date_query = {"date": {"$gte": filter_start, "$lt": filter_end}} if filter_start else {}

    # ── Serial number lookup ─────────────────────────────────
    serial_results = []
    if serial_query:
        matched_sales = list(db.mechanic_sales.find({
            "serial_number": {"$regex": serial_query, "$options": "i"}
        }).sort("date", -1))

        for sale in matched_sales:
            mechanic = db.mechanics.find_one({"_id": sale.get("mechanic_id")})
            serial_results.append({
                "mechanic_name": mechanic.get("name", "Unknown") if mechanic else "Deleted",
                "mechanic_id": str(sale.get("mechanic_id", "")),
                "mechanic_phone": mechanic.get("phone", "") if mechanic else "",
                "mechanic_shop": mechanic.get("shop_name", "") if mechanic else "",
                "battery_model": sale.get("battery_model", ""),
                "serial_number": sale.get("serial_number", ""),
                "quantity": sale.get("quantity", 1),
                "amount": sale.get("amount", 0),
                "date": sale.get("date"),
            })

    # ── Mechanic list ────────────────────────────────────────
    if query:
        filter_query = {
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"phone": {"$regex": query, "$options": "i"}},
                {"shop_name": {"$regex": query, "$options": "i"}},
            ]
        }
    else:
        filter_query = {}

    all_mechanics = list(db.mechanics.find(filter_query).sort("created_at", -1))

    # Calculate outstanding balance (unfiltered) + period revenue (filtered)
    mechanics = []
    total_filtered_revenue = 0

    for m in all_mechanics:
        # Unfiltered dues (always show true balance)
        total_credit = sum(
            s.get("amount", 0) for s in db.mechanic_sales.find({"mechanic_id": m["_id"]})
        )
        total_paid = sum(
            p.get("amount", 0) for p in db.mechanic_payments.find({"mechanic_id": m["_id"]})
        )
        m["total_credit"] = total_credit
        m["total_paid"] = total_paid
        m["balance"] = total_credit - total_paid

        # Filtered revenue for the selected period
        period_sales = list(db.mechanic_sales.find({
            "mechanic_id": m["_id"], **date_query
        }))
        period_revenue = sum(s.get("amount", 0) for s in period_sales)
        m["period_revenue"] = period_revenue

        # Only include mechanics with activity in the period (or if searching/viewing all)
        if period_revenue > 0 or query or date_filter == "all":
            mechanics.append(m)
            total_filtered_revenue += period_revenue

    # Grand total outstanding (from displayed mechanics)
    total_outstanding = sum(m["balance"] for m in mechanics)

    return render_template(
        "mechanics.html",
        mechanics=mechanics,
        query=query,
        total_outstanding=total_outstanding,
        serial_query=serial_query,
        serial_results=serial_results,
        date_filter=date_filter,
        date_from=date_from_str,
        date_to=date_to_str,
        total_filtered_revenue=total_filtered_revenue,
    )


# ─── Add new mechanic ───────────────────────────────────────
@mechanics_bp.route("/add", methods=["GET", "POST"])
def add_mechanic():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        shop_name = request.form.get("shop_name", "").strip()

        if not all([name, phone]):
            flash("Name and phone are required.", "error")
            return redirect(url_for("mechanics.add_mechanic"))

        db = get_db()
        if db.mechanics.find_one({"phone": phone}):
            flash("A mechanic with this phone already exists.", "error")
            return redirect(url_for("mechanics.add_mechanic"))

        db.mechanics.insert_one({
            "name": name,
            "phone": phone,
            "shop_name": shop_name,
            "created_at": datetime.utcnow(),
        })
        flash("Mechanic added!", "success")
        return redirect(url_for("mechanics.list_mechanics"))

    return render_template("add_mechanic.html")


# ─── Mechanic Ledger (detail page) ──────────────────────────
@mechanics_bp.route("/<mechanic_id>")
def mechanic_ledger(mechanic_id):
    db = get_db()
    mechanic = db.mechanics.find_one({"_id": ObjectId(mechanic_id)})
    if not mechanic:
        flash("Mechanic not found.", "error")
        return redirect(url_for("mechanics.list_mechanics"))

    # Fetch all credit sales and payments
    sales = list(db.mechanic_sales.find({"mechanic_id": ObjectId(mechanic_id)}))
    payments = list(db.mechanic_payments.find({"mechanic_id": ObjectId(mechanic_id)}))

    # Build a unified transaction list sorted by date
    transactions = []
    for s in sales:
        transactions.append({
            "date": s["date"],
            "type": "credit",
            "description": f"{s.get('battery_model', 'Battery')} (S/N: {s.get('serial_number', '-')})",
            "amount": s.get("amount", 0),
        })
    for p in payments:
        transactions.append({
            "date": p["date"],
            "type": "payment",
            "description": f"Payment ({p.get('payment_mode', 'Cash')})" + (f" — {p.get('notes', '')}" if p.get("notes") else ""),
            "amount": p.get("amount", 0),
            "payment_id": str(p["_id"]),
            "receipt_number": p.get("receipt_number", ""),
        })
    transactions.sort(key=lambda t: t["date"], reverse=True)

    # Totals
    total_credit = sum(s.get("amount", 0) for s in sales)
    total_paid = sum(p.get("amount", 0) for p in payments)
    balance = total_credit - total_paid

    # Get batteries for credit sale form
    batteries = list(db.inventory.find({"stock": {"$gt": 0}}))
    today = date.today().strftime("%d/%m/%Y")

    return render_template(
        "mechanic_ledger.html",
        mechanic=mechanic,
        transactions=transactions,
        total_credit=total_credit,
        total_paid=total_paid,
        balance=balance,
        batteries=batteries,
        today=today,
    )


# ─── Add credit sale to mechanic (multi-battery) ────────────
@mechanics_bp.route("/<mechanic_id>/sale", methods=["POST"])
def add_mechanic_sale(mechanic_id):
    import json

    db = get_db()
    mechanic = db.mechanics.find_one({"_id": ObjectId(mechanic_id)})
    if not mechanic:
        flash("Mechanic not found.", "error")
        return redirect(url_for("mechanics.list_mechanics"))

    sale_date_str = request.form.get("sale_date", "").strip()
    try:
        sale_date = datetime.strptime(sale_date_str, "%d/%m/%Y")
    except (ValueError, TypeError):
        sale_date = datetime.combine(date.today(), datetime.min.time())

    # ── Parse multi-battery JSON payload ─────────────────────
    batteries_json = request.form.get("batteries_json", "").strip()
    if not batteries_json:
        flash("No batteries submitted.", "error")
        return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

    try:
        battery_entries = json.loads(batteries_json)
    except json.JSONDecodeError:
        flash("Invalid battery data.", "error")
        return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

    if not battery_entries or not isinstance(battery_entries, list):
        flash("At least one battery is required.", "error")
        return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

    # ── Process each battery entry ───────────────────────────
    total_amount = 0
    items_recorded = 0

    for i, entry in enumerate(battery_entries):
        battery_id = entry.get("battery_id", "")
        quantity = entry.get("quantity", 0)
        serials = entry.get("serials", [])

        if not battery_id or quantity < 1 or not serials:
            flash(f"Battery #{i+1}: Missing required fields.", "error")
            return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

        if len(serials) != quantity:
            flash(f"Battery #{i+1}: Serial count ({len(serials)}) doesn't match quantity ({quantity}).", "error")
            return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

        battery = db.inventory.find_one({"_id": ObjectId(battery_id)})
        if not battery:
            flash(f"Battery #{i+1}: Not found in inventory.", "error")
            return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

        if battery.get("stock", 0) < quantity:
            flash(f"Battery #{i+1}: Not enough stock! Only {battery.get('stock', 0)} available.", "error")
            return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

        battery_model = f"{battery['brand']} {battery['model']}"
        description = f"{quantity}x {battery_model}" if quantity > 1 else battery_model
        custom_price = entry.get("custom_price", 0)
        if custom_price and custom_price > 0:
            unit_price = custom_price
        else:
            unit_price = battery.get("mechanic_price") or battery.get("selling_price", 0)
        amount = unit_price * quantity
        serial_str = ", ".join(serials)

        # Insert credit sale record
        db.mechanic_sales.insert_one({
            "mechanic_id": ObjectId(mechanic_id),
            "battery_model": description,
            "serial_number": serial_str,
            "quantity": quantity,
            "amount": amount,
            "date": sale_date,
            "created_at": datetime.utcnow(),
        })

        # Decrement stock
        db.inventory.update_one(
            {"_id": ObjectId(battery_id)},
            {"$inc": {"stock": -quantity}},
        )

        total_amount += amount
        items_recorded += quantity

    flash(f"Credit sale recorded! ({items_recorded} batteries, ₹{total_amount:.2f})", "success")
    return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))


# ─── Record payment from mechanic ───────────────────────────
@mechanics_bp.route("/<mechanic_id>/payment", methods=["POST"])
def add_mechanic_payment(mechanic_id):
    db = get_db()
    mechanic = db.mechanics.find_one({"_id": ObjectId(mechanic_id)})
    if not mechanic:
        flash("Mechanic not found.", "error")
        return redirect(url_for("mechanics.list_mechanics"))

    amount = request.form.get("amount", "").strip()
    payment_mode = request.form.get("payment_mode", "").strip()
    payment_date_str = request.form.get("payment_date", "").strip()
    notes = request.form.get("notes", "").strip()

    if not all([amount, payment_mode]):
        flash("Amount and payment mode are required.", "error")
        return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

    try:
        amount = float(amount)
    except ValueError:
        flash("Amount must be a number.", "error")
        return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

    try:
        payment_date = datetime.strptime(payment_date_str, "%d/%m/%Y")
    except (ValueError, TypeError):
        payment_date = datetime.combine(date.today(), datetime.min.time())

    # Generate receipt number (REC-0001 format)
    last_payment = db.mechanic_payments.find_one(
        {"receipt_number": {"$exists": True}},
        sort=[("receipt_number", -1)]
    )
    if last_payment and last_payment.get("receipt_number", "").startswith("REC-"):
        try:
            last_num = int(last_payment["receipt_number"].split("-")[1])
        except (ValueError, IndexError):
            last_num = 0
    else:
        last_num = db.mechanic_payments.count_documents({})
    receipt_number = f"REC-{last_num + 1:04d}"

    result = db.mechanic_payments.insert_one({
        "mechanic_id": ObjectId(mechanic_id),
        "amount": amount,
        "date": payment_date,
        "payment_mode": payment_mode,
        "notes": notes,
        "receipt_number": receipt_number,
        "created_at": datetime.utcnow(),
    })

    flash(f"Payment of ₹{amount:.2f} recorded! ({receipt_number})", "success")
    return redirect(url_for("mechanics.mechanic_receipt", payment_id=str(result.inserted_id)))


# ─── Mechanic payment receipt ───────────────────────────────
@mechanics_bp.route("/receipt/<payment_id>")
def mechanic_receipt(payment_id):
    db = get_db()
    payment = db.mechanic_payments.find_one({"_id": ObjectId(payment_id)})
    if not payment:
        flash("Payment not found.", "error")
        return redirect(url_for("mechanics.list_mechanics"))

    mechanic = db.mechanics.find_one({"_id": payment["mechanic_id"]})
    if not mechanic:
        flash("Mechanic not found.", "error")
        return redirect(url_for("mechanics.list_mechanics"))

    # Calculate balance: total credit - all payments up to and including this one
    total_credit = sum(
        s.get("amount", 0) for s in db.mechanic_sales.find({"mechanic_id": mechanic["_id"]})
    )
    total_paid = sum(
        p.get("amount", 0) for p in db.mechanic_payments.find({"mechanic_id": mechanic["_id"]})
    )
    # Balance BEFORE this payment = current balance + this payment amount
    previous_balance = (total_credit - total_paid) + payment["amount"]
    remaining_balance = total_credit - total_paid

    # Receipt number fallback for old payments without one
    receipt_number = payment.get("receipt_number", f"REC-{str(payment['_id'])[-4:].upper()}")

    return render_template(
        "mechanic_receipt.html",
        payment=payment,
        mechanic=mechanic,
        receipt_number=receipt_number,
        previous_balance=previous_balance,
        remaining_balance=remaining_balance,
    )


# ─── Edit mechanic ──────────────────────────────────────────
@mechanics_bp.route("/edit/<mechanic_id>", methods=["GET", "POST"])
def edit_mechanic(mechanic_id):
    db = get_db()
    mechanic = db.mechanics.find_one({"_id": ObjectId(mechanic_id)})
    if not mechanic:
        flash("Mechanic not found.", "error")
        return redirect(url_for("mechanics.list_mechanics"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        shop_name = request.form.get("shop_name", "").strip()

        if not all([name, phone]):
            flash("Name and phone are required.", "error")
            return redirect(url_for("mechanics.edit_mechanic", mechanic_id=mechanic_id))

        existing = db.mechanics.find_one({"phone": phone, "_id": {"$ne": ObjectId(mechanic_id)}})
        if existing:
            flash("Another mechanic already has this phone.", "error")
            return redirect(url_for("mechanics.edit_mechanic", mechanic_id=mechanic_id))

        db.mechanics.update_one(
            {"_id": ObjectId(mechanic_id)},
            {"$set": {"name": name, "phone": phone, "shop_name": shop_name}}
        )
        flash("Mechanic updated!", "success")
        return redirect(url_for("mechanics.list_mechanics"))

    return render_template("edit_mechanic.html", mechanic=mechanic)


# ─── Delete mechanic ────────────────────────────────────────
@mechanics_bp.route("/delete/<mechanic_id>", methods=["POST"])
def delete_mechanic(mechanic_id):
    db = get_db()
    mechanic = db.mechanics.find_one({"_id": ObjectId(mechanic_id)})
    if not mechanic:
        flash("Mechanic not found.", "error")
        return redirect(url_for("mechanics.list_mechanics"))

    db.mechanic_sales.delete_many({"mechanic_id": ObjectId(mechanic_id)})
    db.mechanic_payments.delete_many({"mechanic_id": ObjectId(mechanic_id)})
    db.mechanics.delete_one({"_id": ObjectId(mechanic_id)})
    flash(f"Mechanic '{mechanic['name']}' and all records deleted.", "success")
    return redirect(url_for("mechanics.list_mechanics"))
