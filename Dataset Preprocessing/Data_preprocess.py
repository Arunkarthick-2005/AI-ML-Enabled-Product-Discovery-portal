import pandas as pd
import uuid
import re
import ast
import os
import json
from datetime import datetime

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(BASE_DIR, "flipkart_com-ecommerce_sample.csv")
OUTPUT_JSON = os.path.join(BASE_DIR, "flipkart_products_clean.json")

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def generate_product_id():
    return f"fk_{uuid.uuid4().hex}"

def clean_text(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    return value if value else None

def clean_price(value):
    if pd.isna(value):
        return None

    try:
        # Convert to float first (handles decimals correctly)
        price = float(str(value).replace(",", "").replace("₹", "").strip())
        return int(round(price))
    except Exception:
        return None

def clean_rating(value):
    try:
        return float(value)
    except:
        return None

def parse_images(value):
    if pd.isna(value):
        return []

    raw = str(value).strip()

    # Case 1: JSON-encoded list → parse it properly
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [img.strip() for img in parsed if img.strip()]
        except Exception:
            pass

    # Case 2: fallback to comma-separated parsing
    return [
        img.strip().strip('"')
        for img in raw.split(",")
        if img.strip()
    ]

def parse_category_tree(value):
    if pd.isna(value):
        return {
            "level_1": None,
            "level_2": None,
            "level_3": None
        }

    try:
        # Step 1: Convert string to Python list
        tree = ast.literal_eval(str(value))

        # Step 2: Extract category path string
        if isinstance(tree, list) and tree:
            path = tree[0]
        else:
            path = str(value)

        # Step 3: Normalize and split
        path = path.replace("&gt;&gt;", ">>")
        parts = [p.strip() for p in path.split(">>") if p.strip()]

    except Exception:
        parts = []

    return {
        "level_1": parts[0] if len(parts) > 0 else None,
        "level_2": parts[1] if len(parts) > 1 else None,
        "level_3": parts[2] if len(parts) > 2 else None,
    }

def parse_specifications(value):
    if pd.isna(value):
        return None

    raw = str(value).strip()
    raw = raw.replace("=&gt;", ":")

    try:
        parsed = ast.literal_eval(raw)
        return parsed
    except Exception:
        return raw

# -------------------------------------------------
# LOAD CSV
# -------------------------------------------------
df = pd.read_csv(INPUT_CSV)
df.columns = df.columns.str.strip().str.lower()

# -------------------------------------------------
# REMOVE DUPLICATES
# -------------------------------------------------
df = df.dropna(how="any")
df = df.drop_duplicates(subset=["product_name","discounted_price"])

# -------------------------------------------------
# TRANSFORM ROWS (NO DATAFRAME STORAGE)
# -------------------------------------------------
cleaned_products = []

for _, row in df.iterrows():
    product = {
        "product_id": generate_product_id(),
        "external_id": clean_text(row.get("uniq_id")),
        "pid": clean_text(row.get("pid")),

        "title": clean_text(row.get("product_name")),
        "brand": clean_text(row.get("brand")),

        "category": parse_category_tree(row.get("product_category_tree")),

        "price": {
            "selling": clean_price(row.get("discounted_price")),
            "retail": clean_price(row.get("retail_price")),
        },

        "rating": {
            "product": clean_rating(row.get("product_rating")),
            "overall": clean_rating(row.get("overall_rating")),
        },

        "description": clean_text(row.get("description")),
        "specifications": parse_specifications(row.get("product_specifications")),

        "images": parse_images(row.get("image")),

        "is_fk_advantage": bool(row.get("is_fk_advantage_product")),
        "product_url": clean_text(row.get("product_url")),

        "source": "flipkart",
        "active": True,

        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    # ✅ Minimal validation policy
    if (
        product["title"] and
        product["price"]["selling"] is not None and
        product["images"]
    ):
        cleaned_products.append(product)

# -------------------------------------------------
# SAVE AS JSON (STRUCTURE PRESERVED)
# -------------------------------------------------
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(cleaned_products, f, indent=2, ensure_ascii=False)

print("✅ Preprocessing completed successfully")
print(f"✅ Products written: {len(cleaned_products)}")
print(f"✅ Output format: MongoDB‑ready JSON")
