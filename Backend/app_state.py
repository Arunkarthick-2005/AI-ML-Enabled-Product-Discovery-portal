KNOWN_BRANDS = set()
KNOWN_CATEGORIES = {
    "level_1": set(),
    "level_2": set(),
    "level_3": set(),
}

def load_search_metadata(products_collection):
    global KNOWN_BRANDS, KNOWN_CATEGORIES

    KNOWN_BRANDS = set(
        b.lower()
        for b in products_collection.distinct("brand")
        if b
    )

    for p in products_collection.find({}, {
        "category.level_1": 1,
        "category.level_2": 1,
        "category.level_3": 1
    }):
        for level in KNOWN_CATEGORIES:
            val = p.get("category", {}).get(level)
            if val:
                KNOWN_CATEGORIES[level].add(val.lower())