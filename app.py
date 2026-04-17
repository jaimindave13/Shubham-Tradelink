"""
Shubham Tradelink Management System — main entry point.

Development:  python app.py
Production:   gunicorn app:app
"""

import os
from flask import Flask, session, redirect, url_for, request as flask_request
from config import MONGO_URI, DB_NAME, SECRET_KEY
from models.db import init_db

# ── Import blueprints ────────────────────────────────────────
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.customers import customers_bp
from routes.inventory import inventory_bp
from routes.sales import sales_bp
from routes.warranties import warranties_bp
from routes.mechanics import mechanics_bp
from routes.quick_entries import quick_entry_bp


def create_app():
    """Application factory — creates and configures the Flask app."""
    app = Flask(__name__)

    # ── Configuration ────────────────────────────────────────
    app.config["MONGO_URI"] = MONGO_URI
    app.config["DB_NAME"] = DB_NAME
    app.secret_key = SECRET_KEY

    # ── Security headers ─────────────────────────────────────
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # ── Initialise database connection ───────────────────────
    init_db(app)

    # ── Register blueprints (routes) ─────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(warranties_bp)
    app.register_blueprint(mechanics_bp)
    app.register_blueprint(quick_entry_bp)

    # ── PWA: serve service worker from root for full scope ──────
    @app.route("/service-worker.js")
    def service_worker():
        from flask import send_from_directory
        return send_from_directory(
            app.static_folder, "service-worker.js",
            mimetype="application/javascript",
        )

    # ── Login protection ─────────────────────────────────────
    @app.before_request
    def require_login():
        """Redirect to login page if user is not authenticated."""
        allowed_routes = ("auth.login", "static", "service_worker")
        if not session.get("logged_in") and flask_request.endpoint not in allowed_routes:
            return redirect(url_for("auth.login"))

    return app


# ── Create app at module level (needed for gunicorn) ─────────
app = create_app()

# ── Start the development server (local only) ────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
