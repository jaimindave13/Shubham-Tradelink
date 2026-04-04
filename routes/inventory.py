"""
Inventory routes — list, add, and edit batteries.
"""

from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.db import get_db

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@inventory_bp.route("/")
def list_inventory():
    """Show all batteries, sorted by brand then model."""
    db = get_db()
    batteries = list(db.inventory.find().sort([("brand", 1), ("model", 1)]))
    return render_template("inventory.html", batteries=batteries)


@inventory_bp.route("/add", methods=["GET", "POST"])
def add_battery():
    """Render the add-battery form (GET) or save a new battery (POST)."""
    if request.method == "POST":
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        stock = request.form.get("stock", "").strip()
        purchase_price = request.form.get("purchase_price", "").strip()
        selling_price = request.form.get("selling_price", "").strip()
        warranty_months = request.form.get("warranty_months", "12").strip()

        # ── Validation ───────────────────────────────────────────
        if not all([brand, model, stock, purchase_price, selling_price]):
            flash("All fields are required.", "error")
            return redirect(url_for("inventory.add_battery"))

        try:
            stock = int(stock)
            purchase_price = float(purchase_price)
            selling_price = float(selling_price)
            warranty_months = int(warranty_months)
        except ValueError:
            flash("Stock and warranty must be whole numbers; prices must be numbers.", "error")
            return redirect(url_for("inventory.add_battery"))

        db = get_db()
        db.inventory.insert_one(
            {
                "brand": brand,
                "model": model,
                "stock": stock,
                "purchase_price": purchase_price,
                "selling_price": selling_price,
                "warranty_months": warranty_months,
            }
        )
        flash("Battery added to inventory!", "success")
        return redirect(url_for("inventory.list_inventory"))

    return render_template("add_battery.html")


@inventory_bp.route("/edit/<battery_id>", methods=["GET", "POST"])
def edit_battery(battery_id):
    """Edit an existing battery's details."""
    db = get_db()
    battery = db.inventory.find_one({"_id": ObjectId(battery_id)})

    if not battery:
        flash("Battery not found.", "error")
        return redirect(url_for("inventory.list_inventory"))

    if request.method == "POST":
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        stock = request.form.get("stock", "").strip()
        purchase_price = request.form.get("purchase_price", "").strip()
        selling_price = request.form.get("selling_price", "").strip()
        warranty_months = request.form.get("warranty_months", "12").strip()

        if not all([brand, model, stock, purchase_price, selling_price]):
            flash("All fields are required.", "error")
            return redirect(url_for("inventory.edit_battery", battery_id=battery_id))

        try:
            stock = int(stock)
            purchase_price = float(purchase_price)
            selling_price = float(selling_price)
            warranty_months = int(warranty_months)
        except ValueError:
            flash("Stock and warranty must be whole numbers; prices must be numbers.", "error")
            return redirect(url_for("inventory.edit_battery", battery_id=battery_id))

        db.inventory.update_one(
            {"_id": ObjectId(battery_id)},
            {
                "$set": {
                    "brand": brand,
                    "model": model,
                    "stock": stock,
                    "purchase_price": purchase_price,
                    "selling_price": selling_price,
                    "warranty_months": warranty_months,
                }
            },
        )
        flash("Battery updated!", "success")
        return redirect(url_for("inventory.list_inventory"))

    return render_template("edit_battery.html", battery=battery)


@inventory_bp.route("/delete/<battery_id>", methods=["POST"])
def delete_battery(battery_id):
    """Remove a battery from inventory."""
    db = get_db()
    battery = db.inventory.find_one({"_id": ObjectId(battery_id)})

    if not battery:
        flash("Battery not found.", "error")
        return redirect(url_for("inventory.list_inventory"))

    db.inventory.delete_one({"_id": ObjectId(battery_id)})
    flash(f"{battery['brand']} {battery['model']} removed from inventory.", "success")
    return redirect(url_for("inventory.list_inventory"))
