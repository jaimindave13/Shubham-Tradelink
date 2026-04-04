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

    mechanics = list(db.mechanics.find(filter_query).sort("created_at", -1))

    # Calculate outstanding balance for each mechanic
    for m in mechanics:
        total_credit = sum(
            s.get("amount", 0) for s in db.mechanic_sales.find({"mechanic_id": m["_id"]})
        )
        total_paid = sum(
            p.get("amount", 0) for p in db.mechanic_payments.find({"mechanic_id": m["_id"]})
        )
        m["total_credit"] = total_credit
        m["total_paid"] = total_paid
        m["balance"] = total_credit - total_paid

    # Grand total outstanding
    total_outstanding = sum(m["balance"] for m in mechanics)

    return render_template(
        "mechanics.html",
        mechanics=mechanics,
        query=query,
        total_outstanding=total_outstanding,
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


# ─── Add credit sale to mechanic ────────────────────────────
@mechanics_bp.route("/<mechanic_id>/sale", methods=["POST"])
def add_mechanic_sale(mechanic_id):
    db = get_db()
    mechanic = db.mechanics.find_one({"_id": ObjectId(mechanic_id)})
    if not mechanic:
        flash("Mechanic not found.", "error")
        return redirect(url_for("mechanics.list_mechanics"))

    battery_id = request.form.get("battery_id", "").strip()
    serial_number = request.form.get("serial_number", "").strip()
    amount = request.form.get("amount", "").strip()
    quantity = request.form.get("quantity", "1").strip()
    sale_date_str = request.form.get("sale_date", "").strip()

    if not all([battery_id, serial_number, amount]):
        flash("All fields are required.", "error")
        return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

    try:
        amount = float(amount)
        quantity = int(quantity)
        if quantity < 1:
            quantity = 1
    except ValueError:
        flash("Amount must be a number, quantity must be a whole number.", "error")
        return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

    try:
        sale_date = datetime.strptime(sale_date_str, "%d/%m/%Y")
    except (ValueError, TypeError):
        sale_date = datetime.combine(date.today(), datetime.min.time())

    battery = db.inventory.find_one({"_id": ObjectId(battery_id)})
    if not battery:
        flash("Battery not found.", "error")
        return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

    if battery.get("stock", 0) < quantity:
        flash(f"Not enough stock! Only {battery.get('stock', 0)} available.", "error")
        return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))

    # Build description
    battery_model = f"{battery['brand']} {battery['model']}"
    description = f"{quantity}x {battery_model}" if quantity > 1 else battery_model

    # Insert credit sale
    db.mechanic_sales.insert_one({
        "mechanic_id": ObjectId(mechanic_id),
        "battery_model": description,
        "serial_number": serial_number,
        "quantity": quantity,
        "amount": amount,
        "date": sale_date,
        "created_at": datetime.utcnow(),
    })

    # Decrement stock by quantity
    db.inventory.update_one(
        {"_id": ObjectId(battery_id)},
        {"$inc": {"stock": -quantity}},
    )

    flash(f"Credit sale recorded! ({quantity}x {battery_model})", "success")
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

    db.mechanic_payments.insert_one({
        "mechanic_id": ObjectId(mechanic_id),
        "amount": amount,
        "date": payment_date,
        "payment_mode": payment_mode,
        "notes": notes,
        "created_at": datetime.utcnow(),
    })

    flash(f"Payment of ₹{amount:.2f} recorded!", "success")
    return redirect(url_for("mechanics.mechanic_ledger", mechanic_id=mechanic_id))


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
