"""
Configuration settings for Shubham Tradelink Management System.
All sensitive values are loaded from environment variables.
"""

import os
import sys
from dotenv import load_dotenv

# Load .env file (for local development)
load_dotenv()

# ── MongoDB Atlas connection string ──────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("❌ ERROR: MONGO_URI environment variable is not set.")
    print("   Set it with: export MONGO_URI='your_mongodb_connection_string'")
    sys.exit(1)

# ── Database name ────────────────────────────────────────────
DB_NAME = os.getenv("DB_NAME", "battery_shop")

# ── Flask secret key (required for sessions) ─────────────────
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    print("❌ ERROR: SECRET_KEY environment variable is not set.")
    print("   Set it with: export SECRET_KEY='a-random-secret-string'")
    sys.exit(1)
