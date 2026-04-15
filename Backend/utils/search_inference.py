import re

def infer_price(query: str):
    nums = re.findall(r"\d{4,6}", query)
    return int(nums[0]) if nums else None

def infer_brand(query: str, known_brands: set):
    q = query.lower()
    for brand in known_brands:
        if brand in q:
            return brand
    return None

def infer_categories(query: str, known_categories: dict):
    q = query.lower()
    matches = []

    for level, values in known_categories.items():
        for v in values:
            if v in q:
                matches.append((level, v))

    return matches