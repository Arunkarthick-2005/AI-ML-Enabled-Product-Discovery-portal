import re
from database import products_collection

def extract_keywords(query: str):
    return [
        token for token in re.findall(r"[a-zA-Z0-9]+", query.lower())
        if len(token) > 2
    ]

def build_brand_index(products_collection):
    """
    Build a set of all brand names from MongoDB
    """
    return {
        b.lower()
        for b in products_collection.distinct("brand")
        if b
    }
BRAND_INDEX = build_brand_index(products_collection)

def detect_brand(query_lower: str, brand_index: set):
    query_words = set(re.findall(r'\b\w+\b', query_lower))
    for brand in brand_index:
        if len(brand) >= 2 and brand in query_words:
            return brand
    return None


def detect_price(query_lower: str):
    if m := re.search(r'(under|below|less than)\s+(\d+)', query_lower):
        return {"type": "max", "value": int(m.group(2))}
    if m := re.search(r'(above|greater than|more than)\s+(\d+)', query_lower):
        return {"type": "min", "value": int(m.group(2))}
    if m := re.search(r'between\s+(\d+)\s+and\s+(\d+)', query_lower):
        low, high = int(m.group(1)), int(m.group(2))
        return {"type": "range", "min": min(low, high), "max": max(low, high)}
    return None
