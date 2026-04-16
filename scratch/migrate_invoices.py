import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

import certifi

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")

if not mongo_uri:
    print("Error: MONGO_URI not found in .env")
    sys.exit(1)

db_name = os.getenv("DB_NAME", "battery_shop")
client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
db = client[db_name]

# Find all sales sorted by date ascending (oldest first)
sales = list(db.sales.find().sort("date", 1))

print(f"Found {len(sales)} sales to renumber.")

for index, sale in enumerate(sales, start=1):
    invoice_number = f"INV-{str(index).zfill(4)}"
    
    # Update the sale
    db.sales.update_one(
        {"_id": sale["_id"]},
        {"$set": {"invoice_number": invoice_number}}
    )
    
print("Successfully renumbered all invoices! Oldest sale is now INV-0001.")
