import os
import uuid
import ast
import math
import html
import traceback
import requests
from typing import List
from collections import defaultdict
import chromadb
from sentence_transformers import SentenceTransformer
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pymongo.errors import PyMongoError
from database import users_collection, products_collection
from models import UserRegister, UserLogin, Product
from auth import hash_password, verify_password, create_access_token

# =================================================
# SEMANTIC SEARCH SETUP (OFFLINE)
# =================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PERSIST_DIR = os.path.join(BASE_DIR, "chroma_db")
MODEL_PATH = os.path.join(BASE_DIR, "models", "all-MiniLM-L6-v2")

chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
chroma_collection = chroma_client.get_collection("products")

embedding_model = SentenceTransformer(MODEL_PATH)

# =================================================
# APP INIT
# =================================================
app = FastAPI(title="Product Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =================================================
# SAFE DB WRAPPER
# =================================================
def safe_find(cursor_fn, error_message="Database operation failed"):
    try:
        return cursor_fn()
    except PyMongoError:
        raise HTTPException(status_code=503, detail=error_message)

# =================================================
# NORMALIZATION HELPERS
# =================================================
def normalize_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}

def normalize_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []

def normalize_string(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return str(value)

import json
import re
import html

# =================================================
# PHASE-2: DYNAMIC INTENT HELPERS
# =================================================

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
    """
    Detect brand from query using word-boundary matching.
    Prevents false positives like 'w', 'ss', etc.
    """

    # Tokenize query into words
    query_words = set(re.findall(r'\b\w+\b', query_lower))

    for brand in brand_index:
        brand_lower = brand.lower().strip()

        # ✅ Ignore very short brand names (noise)
        if len(brand_lower) < 3:
            continue

        # ✅ Exact word match (recommended)
        if brand_lower in query_words:
            return brand_lower

        # ✅ Multi-word brand (e.g., 'wall design')
        if " " in brand_lower and brand_lower in query_lower:
            return brand_lower

    return None

def detect_price(query_lower: str):
    """
    Returns structured price intent.
    """
    # under / below / less than
    m = re.search(r'(under|below|less than)\s+(\d+)', query_lower)
    if m:
        return {"type": "max", "value": int(m.group(2))}

    # above / greater than / more than
    m = re.search(r'(above|greater than|more than)\s+(\d+)', query_lower)
    if m:
        return {"type": "min", "value": int(m.group(2))}

    # between X and Y
    m = re.search(r'between\s+(\d+)\s+and\s+(\d+)', query_lower)
    if m:
        low = int(m.group(1))
        high = int(m.group(2))
        if low > high:
            low, high = high, low
        return {"type": "range", "min": low, "max": high}

    return None

def build_price_filters(price_intent):
    """
    Returns a list of Chroma‑safe price filters
    """
    filters = []

    # ✅ Enforce price exists
    filters.append({"price": {"$gt": 0}})

    if price_intent["type"] == "max":
        filters.append({"price": {"$lte": price_intent["value"]}})

    elif price_intent["type"] == "min":
        filters.append({"price": {"$gte": price_intent["value"]}})

    elif price_intent["type"] == "range":
        filters.append({"price": {"$gte": price_intent["min"]}})
        filters.append({"price": {"$lte": price_intent["max"]}})

    return filters


def normalize_specifications(value):
    """
    Handles Flipkart-style Ruby-hash + HTML-escaped specification strings.
    Always returns:
    {
      "product_specification": [
        {"key": "...", "value": "..."},
        ...
      ]
    }
    or None
    """

    if not value:
        return None

    # ✅ Case 1: Already normalized
    if isinstance(value, dict) and "product_specification" in value:
        return value

    # ✅ Case 2: Already a list
    if isinstance(value, list):
        return {"product_specification": value}

    # ✅ Case 3: Ruby-hash-like string (YOUR CASE)
    if isinstance(value, str):
        try:
            # 1️⃣ HTML unescape
            cleaned = html.unescape(value)

            # 2️⃣ Replace Ruby hash operator => with :
            cleaned = cleaned.replace("=>", ":")

            # 3️⃣ Ensure valid JSON (wrap keys properly)
            # This regex fixes cases like {key: "Fabric"}
            cleaned = re.sub(r'([{,]\s*)(\w+)\s*:', r'\1"\2":', cleaned)

            # 4️⃣ Load as JSON
            parsed = json.loads(cleaned)

            specs = parsed.get("product_specification")
            if isinstance(specs, list):
                normalized = []
                for s in specs:
                    if isinstance(s, dict):
                        key = s.get("key", "").strip()
                        value = s.get("value", "").strip()
                        if key or value:
                            normalized.append({
                                "key": key,
                                "value": value
                            })

                return {"product_specification": normalized} if normalized else None

        except Exception as e:
            print("SPEC PARSE FAILED:", e)
            return None

    return None

def is_valid_semantic_intent(semantic_scores, query_text):
    """
    Returns True only if the semantic intent
    genuinely maps to the catalog.
    """

    if not semantic_scores:
        return False

    best = semantic_scores[0]

    token_count = len(re.findall(r"\b[a-z]{3,}\b", query_text.lower()))

    # Adaptive relevance bounds
    if token_count <= 1:
        return best <= 0.45
    elif token_count == 2:
        return best <= 0.55
    else:
        return best <= 0.62

def is_catalog_grounded(scores: list, q: str) -> bool:
    """
    Returns True if the query has strong grounding in the catalog.
    Uses semantic evidence, not vocabulary.
    """

    if not scores:
        return False

    # Best semantic match
    best = scores[0]

    # Query complexity adjustment
    token_count = len(re.findall(r"\b[a-z]{3,}\b", q.lower()))

    # Adaptive acceptance bounds
    if token_count <= 1:
        max_allowed = 0.45
    elif token_count == 2:
        max_allowed = 0.55
    else:
        max_allowed = 0.62

    if best > max_allowed:
        return False

    # Consistency check (avoid random clusters)
    if len(scores) >= 3:
        spread = scores[2] - scores[0]
        if spread < 0.04 and best > 0.48:
            return False

    return True

def semantic_threshold_for_query(q: str):
    token_count = len(re.findall(r"\b[a-z]{3,}\b", q.lower()))

    if token_count <= 1:
        return 0.42     # strict for single-word queries
    elif token_count == 2:
        return 0.52     # allow broader meaning
    else:
        return 0.60     # long queries are fuzzy

def is_semantically_confident(distances: list, q: str):
    if not distances:
        return False

    threshold = semantic_threshold_for_query(q)

    best = distances[0]

    if best > threshold:
        return False

    # Optional gap check
    if len(distances) > 1:
        gap = distances[1] - distances[0]
        if gap < 0.05 and best > 0.48:
            return False

    return True

# =================================================
# AUTH ROUTES
# =================================================
@app.post("/auth/register")
def register(user: UserRegister):
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    if users_collection.find_one({"mobile": user.mobile}):
        raise HTTPException(status_code=400, detail="Mobile number already registered")

    users_collection.insert_one({
        "id": str(uuid.uuid4()),
        "name": user.name,
        "email": user.email,
        "mobile": user.mobile,
        "password": hash_password(user.password),
    })

    return {"message": "User registered successfully"}

@app.post("/auth/login")
def login(user: UserLogin):
    db_user = users_collection.find_one({"email": user.email})

    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": db_user["id"]})
    return {"access_token": token, "token_type": "bearer"}

# =================================================
# PRODUCT SEARCH (✅ SEMANTIC SEARCH)
# =================================================
@app.get("/products/search", response_model=List[Product])
def search_products(
    q: str = Query(..., min_length=1),
    top_k: int = 20
):
    debug = {
        "query": q,
        "intent": {},
        "filters": [],
        "matched": []
    }

    # ------------------------------------------------
    # 1. Embed query (semantic part ONLY)
    # ------------------------------------------------
    query_embedding = embedding_model.encode(
        q,
        normalize_embeddings=True
    ).tolist()

    query_lower = q.lower()

    # ------------------------------------------------
    # 2. Intent extraction (brand + price)
    # ------------------------------------------------
    brand_intent = detect_brand(query_lower, BRAND_INDEX)
    price_intent = detect_price(query_lower)

    debug["intent"]["brand"] = brand_intent
    debug["intent"]["price"] = price_intent

    # ------------------------------------------------
    # ✅ 3. SEMANTIC VALIDATION (NO FILTERS HERE)
    # ------------------------------------------------
    semantic_results = chroma_collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["distances"]
    )

    scores = semantic_results.get("distances", [[]])[0]

    if not scores:
        print("DEBUG: No semantic scores returned")
        return []

    # ✅ Decide if query is catalog-grounded
    catalog_grounded = (
        brand_intent is not None
        or is_catalog_grounded(scores, q)
    )

    # 🚨 HARD STOP: meaningless query MUST NOT continue
    if not catalog_grounded:
        print(
            f"DEBUG: Rejected as non-grounded | "
            f"scores={scores[:3]} | query='{q}'"
        )
        return []

    # ------------------------------------------------
    # ✅ 4. Now build filters (SAFE)
    # ------------------------------------------------
    filters = []

    if brand_intent:
        filters.append({"brand": {"$eq": brand_intent}})

    if price_intent:
        filters.extend(build_price_filters(price_intent))

    debug["filters"] = filters

    # ------------------------------------------------
    # 5. Build where clause
    # ------------------------------------------------
    where_clause = None
    if len(filters) == 1:
        where_clause = filters[0]
    elif len(filters) > 1:
        where_clause = {"$and": filters}

    # ------------------------------------------------
    # 6. FINAL SEARCH (SEMANTIC + FILTERED)
    # ------------------------------------------------
    results = chroma_collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where_clause,
        include=["metadatas"]
    )

    if not results.get("metadatas"):
        print("DEBUG: No results after filtering")
        print(json.dumps(debug, indent=2))
        return []

    # ------------------------------------------------
    # 7. Debug matched metadata
    # ------------------------------------------------
    for meta in results["metadatas"][0]:
        debug["matched"].append({
            "pid": meta.get("pid"),
            "price": meta.get("price"),
            "brand": meta.get("brand")
        })

    print("\n===== SEARCH DEBUG TRACE =====")
    print(json.dumps(debug, indent=2))
    print("==============================\n")

    # ------------------------------------------------
    # 8. Fetch full products from MongoDB
    # ------------------------------------------------
    product_ids = [
        meta["pid"]
        for meta in results["metadatas"][0]
        if meta.get("pid")
    ]

    if not product_ids:
        return []

    raw_products = list(
        products_collection.find(
            {"pid": {"$in": product_ids}},
            {"_id": 0}
        )
    )

    # ------------------------------------------------
    # 9. Normalize for UI
    # ------------------------------------------------
    products: List[Product] = []
    for p in raw_products:
        p["brand"] = normalize_string(p.get("brand"))
        p["images"] = normalize_list(p.get("images"))
        p["category"] = normalize_dict(p.get("category"))
        p["price"] = normalize_dict(p.get("price"))
        p["rating"] = normalize_dict(p.get("rating"))
        p["specifications"] = normalize_specifications(
            p.get("specifications")
        )
        products.append(Product(**p))

    return products


# =================================================
# PRODUCT DETAIL
# =================================================
@app.get("/products/{pid}", response_model=Product)
def get_product(pid: str):
    product = safe_find(
        lambda: products_collection.find_one({"pid": pid}, {"_id": 0}),
        "Failed to fetch product"
    )

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product["brand"] = normalize_string(product.get("brand"))
    product["images"] = normalize_list(product.get("images"))
    product["category"] = normalize_dict(product.get("category"))
    product["price"] = normalize_dict(product.get("price"))
    product["rating"] = normalize_dict(product.get("rating"))
    product["specifications"] = normalize_specifications(product.get("specifications"))

    return Product(**product)

# =================================================
# IMAGE PROXY (BEST-EFFORT)
# =================================================
@app.get("/image-proxy")
def image_proxy(url: str = Query(...)):
    try:
        response = requests.get(
            url,
            stream=True,
            timeout=5,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "image/*",
                "Referer": "https://www.flipkart.com/"
            },
            allow_redirects=True
        )

        if response.status_code != 200:
            return StreamingResponse(iter([]), status_code=204)

        return StreamingResponse(
            response.iter_content(chunk_size=1024),
            media_type=response.headers.get("Content-Type", "image/jpeg")
        )

    except Exception:
        return StreamingResponse(iter([]), status_code=204)

# =================================================
# GLOBAL ERROR HANDLER
# =================================================
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."}
    )