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

# If no hash is set but a plain password is provided, hash it at startup
# (so plain-text is never used for comparison at runtime)
if not ADMIN_PASSWORD_HASH:
    _plain = os.getenv("ADMIN_PASSWORD", "")
    if _plain:
        ADMIN_PASSWORD_HASH = generate_password_hash(_plain)


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

        # Authenticate using hashed password only
        if ADMIN_PASSWORD_HASH and check_password_hash(ADMIN_PASSWORD_HASH, password):
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
