"""
Auth routes — login and logout.
Credentials are loaded from environment variables.
"""

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__)

# ─── Credentials from environment variables ──────────────────
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
# Plain-text fallback (for simpler setup, less secure)
ADMIN_PASSWORD_PLAIN = os.getenv("ADMIN_PASSWORD", "")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login page."""
    if session.get("logged_in"):
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username != ADMIN_USERNAME:
            flash("Invalid username or password.", "error")
            return redirect(url_for("auth.login"))

        # Check hashed password first, fall back to plain-text
        authenticated = False
        if ADMIN_PASSWORD_HASH:
            authenticated = check_password_hash(ADMIN_PASSWORD_HASH, password)
        elif ADMIN_PASSWORD_PLAIN:
            authenticated = (password == ADMIN_PASSWORD_PLAIN)

        if authenticated:
            session["logged_in"] = True
            session["username"] = username
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard.index"))
        else:
            flash("Invalid username or password.", "error")
            return redirect(url_for("auth.login"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Clear session and redirect to login."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
