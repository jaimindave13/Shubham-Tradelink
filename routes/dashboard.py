"""
Dashboard route — the home page.
Shows today's KPIs (sales count, revenue, profit, mechanic dues, quick-entry income),
low-stock alerts, payment-mode breakdown, and recent sales.
"""

from datetime import datetime, timedelta, date
from flask import Blueprint, render_template
from models.db import get_db

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    db = get_db()

    # ── Today's window (local machine time, matches shop's IST day) ──
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = today_start + timedelta(days=1)
    month_start = today_start.replace(day=1)

    # ── Today's sales ────────────────────────────────────────────────
    today_sales = list(db.sales.find({"date": {"$gte": today_start, "$lt": today_end}}))
    total_sales_today = len(today_sales)

    total_battery_revenue_today = 0.0
    total_profit_today = 0.0
    payment_breakdown = {"Cash": 0.0, "UPI": 0.0, "Card": 0.0, "Credit": 0.0, "Other": 0.0}

    for sale in today_sales:
        old_bat = sale.get("old_battery_value", 0) or 0
        actual = sale["actual_price"] if "actual_price" in sale else (sale.get("price", 0) + old_bat)
        final = actual - old_bat
        total_battery_revenue_today += final
        total_profit_today += sale.get("profit", actual - sale.get("purchase_price", 0))

        mode = (sale.get("payment_mode") or "Other").strip()
        if mode not in payment_breakdown:
            mode = "Other"
        payment_breakdown[mode] += final

    # ── Today's quick-entry income ───────────────────────────────────
    quick_today_pipeline = [
        {"$match": {"date": {"$gte": today_start, "$lt": today_end}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]
    quick_today_doc = next(iter(db.quick_entries.aggregate(quick_today_pipeline)), {})
    quick_revenue_today = float(quick_today_doc.get("total") or 0)
    quick_count_today = int(quick_today_doc.get("count") or 0)

    # Add quick-entry payment modes too (so the breakdown reflects all cash today)
    quick_today_docs = db.quick_entries.find(
        {"date": {"$gte": today_start, "$lt": today_end}},
        {"amount": 1, "payment_mode": 1},
    )
    for qe in quick_today_docs:
        mode = (qe.get("payment_mode") or "Other").strip()
        if mode not in payment_breakdown:
            mode = "Other"
        payment_breakdown[mode] += float(qe.get("amount") or 0)

    total_revenue_today = total_battery_revenue_today + quick_revenue_today

    # ── Month-to-date revenue (battery + quick entries) ──────────────
    month_battery_pipeline = [
        {"$match": {"date": {"$gte": month_start, "$lt": today_end}}},
        {"$group": {
            "_id": None,
            "total": {"$sum": {"$ifNull": [
                "$final_amount",
                {"$subtract": [
                    {"$ifNull": ["$actual_price", 0]},
                    {"$ifNull": ["$old_battery_value", 0]},
                ]},
            ]}},
        }},
    ]
    month_battery_doc = next(iter(db.sales.aggregate(month_battery_pipeline)), {})
    month_quick_pipeline = [
        {"$match": {"date": {"$gte": month_start, "$lt": today_end}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    month_quick_doc = next(iter(db.quick_entries.aggregate(month_quick_pipeline)), {})
    month_revenue = float(month_battery_doc.get("total") or 0) + float(month_quick_doc.get("total") or 0)

    # ── Low stock items (stock ≤ 1) ─────────────────────────────────
    low_stock_items = list(db.inventory.find({"stock": {"$lte": 1}}).sort("stock", 1))

    # ── Recent 10 sales — bulk-fetch customer names (avoid N+1) ──────
    recent_sales = list(db.sales.find().sort("date", -1).limit(10))
    customer_ids = [s.get("customer_id") for s in recent_sales if s.get("customer_id")]
    customer_map = {}
    if customer_ids:
        for c in db.customers.find({"_id": {"$in": customer_ids}}, {"name": 1}):
            customer_map[c["_id"]] = c.get("name", "Unknown")
    for sale in recent_sales:
        sale["customer_name"] = customer_map.get(sale.get("customer_id"), "Walk-in")

    # ── Mechanic outstanding (one aggregation per collection) ────────
    credit_doc = next(iter(db.mechanic_sales.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ])), {})
    paid_doc = next(iter(db.mechanic_payments.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ])), {})
    mechanic_outstanding = float(credit_doc.get("total") or 0) - float(paid_doc.get("total") or 0)

    return render_template(
        "dashboard.html",
        today=today,
        total_sales_today=total_sales_today,
        total_revenue_today=total_revenue_today,
        total_battery_revenue_today=total_battery_revenue_today,
        total_profit_today=total_profit_today,
        quick_revenue_today=quick_revenue_today,
        quick_count_today=quick_count_today,
        payment_breakdown=payment_breakdown,
        month_revenue=month_revenue,
        low_stock_items=low_stock_items,
        recent_sales=recent_sales,
        mechanic_outstanding=mechanic_outstanding,
    )
