from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["flipkart_db"]
collection = db["products"]

data = collection.find(
    {},
    {
        "_id": 0,
        "category.level_1": 1,
        "category.level_2": 1,
        "category.level_3": 1
    }
)

tree = {}

for item in data:
    cat = item.get("category", {})

    l1 = cat.get("level_1")
    l2 = cat.get("level_2")
    l3 = cat.get("level_3")

    # -------------------------------------------------
    # ✅ 1. SKIP INVALID CATEGORY (PRODUCT TITLE CASE)
    # -------------------------------------------------
    if not l1:
        continue

    # ❗ detect product-like strings (dynamic)
    if l2 is None and l3 is None:
        # heuristic: product titles are long & messy
        if len(l1.split()) > 4:
            continue

    # -------------------------------------------------
    # ✅ 2. BUILD TREE SAFELY
    # -------------------------------------------------

    if l1 not in tree:
        tree[l1] = {}

    # ✅ case: only L1 exists
    if not l2:
        continue

    if l2 not in tree[l1]:
        tree[l1][l2] = set()

    # ✅ case: L1 + L2 (no L3)
    if not l3:
        continue

    tree[l1][l2].add(l3)

# -------------------------------------------------
# ✅ 3. CONVERT TO OUTPUT FORMAT
# -------------------------------------------------
result = []

for l1, l2_dict in tree.items():

    node_l1 = {"name": l1}

    if not l2_dict:
        result.append(node_l1)
        continue

    node_l1["children"] = []

    for l2, l3_set in l2_dict.items():

        node_l2 = {"name": l2}

        if not l3_set:
            node_l1["children"].append(node_l2)
            continue

        node_l2["children"] = [
            {"name": l3} for l3 in sorted(l3_set)
        ]

        node_l1["children"].append(node_l2)

    result.append(node_l1)

# ✅ FINAL CATEGORY TREE
print(result)