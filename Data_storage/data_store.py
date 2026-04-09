import json
from pymongo import MongoClient

# Load cleaned JSON
with open(
    r"C:\Users\arunkarthick.l\Documents\PoC\Dataset Preprocessing\flipkart_products_clean.json",
    "r",
    encoding="utf-8"
) as f:
    products = json.load(f)

# Fields required by Flutter Product model
REQUIRED_FIELDS = {
    "pid",
    "title",
    "brand",
    "price",
    "category",
    "description",
    "images",
    "specifications"
}

# Filter only required fields
filtered_products = [
    {key: product[key] for key in REQUIRED_FIELDS if key in product}
    for product in products
]

# MongoDB connection
client = MongoClient("mongodb://localhost:27017")
db = client["flipkart_db"]

# Optional: clear collection before insert
db.products.delete_many({})

# Insert clean documents
result = db.products.insert_many(filtered_products)

print(f"✅ Inserted {len(result.inserted_ids)} products with clean schema")