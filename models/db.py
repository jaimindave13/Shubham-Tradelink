"""
Database helper — initialises the PyMongo client and exposes
collection handles that the rest of the app can import.

Usage (inside app factory / app.py):
    from models.db import init_db
    init_db(app)

Usage (inside any route blueprint):
    from models.db import get_db
    db = get_db()
    db.customers.find_one(...)
"""

from pymongo import MongoClient
import certifi

# Module-level reference — set once by init_db()
_client = None
_db = None


def init_db(app):
    """
    Call once at app startup.
    Reads MONGO_URI and DB_NAME from the Flask app config,
    connects to MongoDB, and stores the database handle.
    """
    global _client, _db
    _client = MongoClient(
        app.config["MONGO_URI"],
        tls=True,
        tlsCAFile=certifi.where(),
    )
    _db = _client[app.config["DB_NAME"]]


def get_db():
    """
    Returns the MongoDB database handle.
    Must be called after init_db().
    """
    if _db is None:
        raise RuntimeError("Database not initialised. Call init_db(app) first.")
    return _db