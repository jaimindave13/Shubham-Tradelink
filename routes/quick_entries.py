"""
Quick Entry routes — lightweight transactions that don't require customer tracking.
Handles charging, checking, DM water, and other small services.
"""

from datetime import datetime, date, timedelta
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.db import get_db

quick_entry_bp = Blueprint("quick_entry", __name__, url_prefix="/quick-entries")


def _parse_date(date_str):
    """Parse DD/MM/YYYY string into a datetime object (midnight)."""
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y")
    except (ValueError, AttributeError):
        return None


@quick_entry_bp.route("/", methods=["GET", "POST"])
def index():
    """Show quick-entry form + recent entries list."""
    db = get_db()

    if request.method == "POST":
        entry_type = request.form.get("entry_type", "").strip()
        amount = request.form.get("amount", "").strip()
        payment_mode = request.form.get("payment_mode", "").strip()
        notes = request.form.get("notes", "").strip()
        entry_date_str = request.form.get("entry_date", "").strip()

        # ── Validation ───────────────────────────────────────────
        if not all([entry_type, amount, payment_mode]):
            flash("Type, amount, and payment mode are required.", "error")
            return redirect(url_for("quick_entry.index"))

        try:
            amount = float(amount)
        except ValueError:
            flash("Amount must be a number.", "error")
            return redirect(url_for("quick_entry.index"))

        if amount <= 0:
            flash("Amount must be greater than zero.", "error")
            return redirect(url_for("quick_entry.index"))

        entry_date = _parse_date(entry_date_str)
        if not entry_date:
            entry_date = datetime.combine(date.today(), datetime.min.time())

        db.quick_entries.insert_one(
            {
                "type": entry_type,
                "amount": amount,
                "payment_mode": payment_mode,
                "notes": notes,
                "date": entry_date,
                "created_at": datetime.utcnow(),
            }
        )
        flash(f"{entry_type} — ₹{amount:.2f} recorded!", "success")
        return redirect(url_for("quick_entry.index"))

    # ── GET: fetch entries + stats ───────────────────────────────
    today_str = date.today().strftime("%d/%m/%Y")

    # Today's quick-entry total
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
    today_entries = list(db.quick_entries.find({"date": {"$gte": today_start, "$lt": today_end}}))
    today_total = sum(e.get("amount", 0) for e in today_entries)
    today_count = len(today_entries)

    # This month's revenue
    first_of_month = date.today().replace(day=1)
    month_start = datetime.combine(first_of_month, datetime.min.time())
    month_entries = list(db.quick_entries.find({"date": {"$gte": month_start}}))
    monthly_total = sum(e.get("amount", 0) for e in month_entries)
    monthly_count = len(month_entries)

    # ── Date range filter (optional) ─────────────────────────────
    from_str = request.args.get("from", "").strip()
    to_str = request.args.get("to", "").strip()
    from_date = _parse_date(from_str)
    to_date = _parse_date(to_str)

    filtered_total = None
    filtered_count = None

    if from_date and to_date:
        to_date_end = to_date + timedelta(days=1)  # inclusive end
        query = {"date": {"$gte": from_date, "$lt": to_date_end}}
        entries = list(db.quick_entries.find(query).sort("date", -1))
        filtered_total = sum(e.get("amount", 0) for e in entries)
        filtered_count = len(entries)
    else:
        entries = list(db.quick_entries.find().sort("date", -1).limit(50))

    return render_template(
        "quick_entries.html",
        entries=entries,
        today=today_str,
        today_total=today_total,
        today_count=today_count,
        monthly_total=monthly_total,
        monthly_count=monthly_count,
        filtered_total=filtered_total,
        filtered_count=filtered_count,
        filter_from=from_str,
        filter_to=to_str,
    )


@quick_entry_bp.route("/delete/<entry_id>", methods=["POST"])
def delete_entry(entry_id):
    """Delete a quick entry."""
    db = get_db()
    entry = db.quick_entries.find_one({"_id": ObjectId(entry_id)})

    if not entry:
        flash("Entry not found.", "error")
        return redirect(url_for("quick_entry.index"))

    db.quick_entries.delete_one({"_id": ObjectId(entry_id)})
    flash("Entry deleted.", "success")
    return redirect(url_for("quick_entry.index"))
