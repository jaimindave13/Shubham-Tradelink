"""
Warranty routes — view all warranties with phone-based search.
"""

from datetime import datetime, timedelta
from flask import Blueprint, render_template, request
from models.db import get_db

warranties_bp = Blueprint("warranties", __name__, url_prefix="/warranties")


@warranties_bp.route("/")
def list_warranties():
    """List warranties with optional phone/name search. Mark items expiring within 7 days."""
    db = get_db()
    query = request.args.get("q", "").strip()

    # If searching, find matching customers first, then their warranties
    if query:
        matching_customers = list(db.customers.find({
            "$or": [
                {"phone": {"$regex": query, "$options": "i"}},
                {"name": {"$regex": query, "$options": "i"}},
                {"vehicle_number": {"$regex": query, "$options": "i"}},
            ]
        }))
        customer_ids = [c["_id"] for c in matching_customers]
        warranties = list(
            db.warranties.find({"customer_id": {"$in": customer_ids}}).sort("expiry_date", 1)
        )
    else:
        warranties = list(db.warranties.find().sort("expiry_date", 1))

    soon = datetime.utcnow() + timedelta(days=7)

    for w in warranties:
        customer = db.customers.find_one({"_id": w.get("customer_id")})
        w["customer_name"] = customer["name"] if customer else "Unknown"
        w["customer_phone"] = customer["phone"] if customer else ""
        w["vehicle_number"] = customer.get("vehicle_number", "") if customer else ""
        w["expiring_soon"] = w["expiry_date"] <= soon

    return render_template("warranties.html", warranties=warranties, query=query)
