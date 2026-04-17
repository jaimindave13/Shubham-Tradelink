"""
Dashboard route — the home page.
Shows today's sales count, revenue, low-stock alerts, and recent sales.
"""

from datetime import datetime, timedelta
from flask import Blueprint, render_template
from models.db import get_db

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    db = get_db()

    # ── Today's date (local machine time) ──────────────────────
    # Sales from the date picker are stored as midnight of the chosen date.
    # We use local date so it matches the shop's actual day.
    from datetime import date
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = today_start + timedelta(days=1)

    # ── Aggregate today's sales ──────────────────────────────────
    today_sales = list(
        db.sales.find({"date": {"$gte": today_start, "$lt": today_end}})
    )
    total_sales_today = len(today_sales)

    # Backward-compatible revenue & profit
    total_revenue_today = 0
    total_profit_today = 0
    for sale in today_sales:
        old_bat = sale.get("old_battery_value", 0) or 0
        if "actual_price" in sale:
            actual = sale["actual_price"]
        else:
            actual = sale.get("price", 0) + old_bat
        final = actual - old_bat
        total_revenue_today += final
        total_profit_today += sale.get("profit", actual - sale.get("purchase_price", 0))

    # ── Low stock items (stock ≤ 1) ──────────────────────────────
    low_stock_items = list(db.inventory.find({"stock": {"$lte": 1}}))

    # ── Recent 10 sales (most-recent first) ──────────────────────
    recent_sales_cursor = db.sales.find().sort("date", -1).limit(10)
    recent_sales = []
    for sale in recent_sales_cursor:
        customer = db.customers.find_one({"_id": sale.get("customer_id")})
        sale["customer_name"] = customer["name"] if customer else "Unknown"
        recent_sales.append(sale)

    # ── Mechanic outstanding balance ─────────────────────────────
    total_mechanic_credit = sum(s.get("amount", 0) for s in db.mechanic_sales.find())
    total_mechanic_paid = sum(p.get("amount", 0) for p in db.mechanic_payments.find())
    mechanic_outstanding = total_mechanic_credit - total_mechanic_paid

    return render_template(
        "dashboard.html",
        total_sales_today=total_sales_today,
        total_revenue_today=total_revenue_today,
        total_profit_today=total_profit_today,
        low_stock_items=low_stock_items,
        recent_sales=recent_sales,
        mechanic_outstanding=mechanic_outstanding,
    )
