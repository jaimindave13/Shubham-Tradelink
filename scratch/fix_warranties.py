import os
import sys
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import timedelta
from dateutil.relativedelta import relativedelta

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")

if not mongo_uri:
    print("Error: MONGO_URI not found in .env")
    sys.exit(1)

db_name = os.getenv("DB_NAME", "battery_shop")
client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
db = client[db_name]

# Find all warranties
warranties = list(db.warranties.find())

print(f"Found {len(warranties)} warranties to fix.")

for warranty in warranties:
    purchase_date = warranty.get("purchase_date")
    warranty_months = warranty.get("warranty_months", 12)
    
    if purchase_date:
        # Correctly calculate expiry date matching exact calendar months
        new_expiry_date = purchase_date + relativedelta(months=warranty_months) - timedelta(days=1)
        
        db.warranties.update_one(
            {"_id": warranty["_id"]},
            {"$set": {"expiry_date": new_expiry_date}}
        )

print("Successfully fixed all warranty calculate logic in database!")
