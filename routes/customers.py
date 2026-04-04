"""
Customer routes — list, search, edit, and delete customers.
"""

from datetime import datetime
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.db import get_db

customers_bp = Blueprint("customers", __name__, url_prefix="/customers")


@customers_bp.route("/")
def list_customers():
    """List all customers sorted by date added (newest first), with optional search."""
    db = get_db()
    query = request.args.get("q", "").strip()

    if query:
        filter_query = {
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"phone": {"$regex": query, "$options": "i"}},
                {"vehicle_number": {"$regex": query, "$options": "i"}},
            ]
        }
    else:
        filter_query = {}

    customers = list(
        db.customers.find(filter_query).sort("created_at", -1)
    )

    return render_template("customers.html", customers=customers, query=query)


@customers_bp.route("/edit/<customer_id>", methods=["GET", "POST"])
def edit_customer(customer_id):
    """Edit an existing customer's details."""
    db = get_db()
    customer = db.customers.find_one({"_id": ObjectId(customer_id)})

    if not customer:
        flash("Customer not found.", "error")
        return redirect(url_for("customers.list_customers"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        vehicle = request.form.get("vehicle", "").strip()
        vehicle_number = request.form.get("vehicle_number", "").strip()

        if not all([name, phone, vehicle, vehicle_number]):
            flash("All fields are required.", "error")
            return redirect(url_for("customers.edit_customer", customer_id=customer_id))

        # Check if phone is taken by another customer
        existing = db.customers.find_one({"phone": phone, "_id": {"$ne": ObjectId(customer_id)}})
        if existing:
            flash("Another customer already has this phone number.", "error")
            return redirect(url_for("customers.edit_customer", customer_id=customer_id))

        db.customers.update_one(
            {"_id": ObjectId(customer_id)},
            {"$set": {
                "name": name,
                "phone": phone,
                "vehicle": vehicle,
                "vehicle_number": vehicle_number,
            }}
        )
        flash("Customer updated!", "success")
        return redirect(url_for("customers.list_customers"))

    return render_template("edit_customer.html", customer=customer)


@customers_bp.route("/delete/<customer_id>", methods=["POST"])
def delete_customer(customer_id):
    """Delete a customer."""
    db = get_db()
    customer = db.customers.find_one({"_id": ObjectId(customer_id)})

    if not customer:
        flash("Customer not found.", "error")
        return redirect(url_for("customers.list_customers"))

    db.warranties.delete_many({"customer_id": ObjectId(customer_id)})
    db.sales.delete_many({"customer_id": ObjectId(customer_id)})
    db.customers.delete_one({"_id": ObjectId(customer_id)})
    flash(f"Customer '{customer['name']}' deleted.", "success")
    return redirect(url_for("customers.list_customers"))


@customers_bp.route("/search")
def search_customer():
    """AJAX endpoint — search customer by phone number for the sales form."""
    phone = request.args.get("phone", "").strip()
    if not phone:
        return jsonify({"found": False})

    db = get_db()
    customer = db.customers.find_one({"phone": phone})
    if customer:
        return jsonify({
            "found": True,
            "customer_id": str(customer["_id"]),
            "name": customer["name"],
            "phone": customer["phone"],
            "vehicle": customer["vehicle"],
            "vehicle_number": customer["vehicle_number"],
        })
    return jsonify({"found": False})
