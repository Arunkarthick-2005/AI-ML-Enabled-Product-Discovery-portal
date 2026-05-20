import os
import uuid
import ast
import math
import html
import json
import numpy as np
from sklearn.cluster import KMeans
import re
from collections import Counter
from typing import Set
import traceback
import requests
from typing import List
from utils.retriever import retrieve_for_rag
from utils.context_builder import build_product_context
from utils.prompt import build_prompt
from utils.llm import generate
from utils.intent import detect_intent
import chromadb
from sentence_transformers import SentenceTransformer
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pymongo.errors import PyMongoError
from llama_cpp import Llama         
from utils.recommendation_engine import (
    log_product_event,
    get_trending_products_per_category_dynamic,
    get_user_recommendations
)
from pydantic import BaseModel
from typing import Optional
from database import users_collection, products_collection, product_view_events
from models import UserRegister, UserLogin, Product
from auth import hash_password, verify_password, create_access_token


class LogInteractionRequest(BaseModel):
    user_id: str
    product_id: str
    event_type: str          # view | search_view | search_impression
    source: Optional[str] = "unknown"


class ProductCopilotRequest(BaseModel):
    product_id: str
    question: str

class CopilotRequest(BaseModel):
    query: str

class CopilotResponse(BaseModel):
    answer: str
    sources: List[str]

class RecommendationRequest(BaseModel):
    query: str
    exclude_pids: List[str] = []

# =================================================
# HOME COLLECTION PROJECTION
# =================================================
HOME_PROJECTION = {
    "_id": 0,
    "pid": 1,
    "title": 1,
    "brand": 1,
    "price": 1,
    "images": 1,
    "category_l1": 1,
    "category_l2": 1,
    "category_l3": 1,
}

# =================================================
# SEMANTIC SEARCH SETUP
# =================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PERSIST_DIR = os.path.join(BASE_DIR, "chroma_db")
MODEL_PATH = os.path.join(BASE_DIR, "models", "all-MiniLM-L6-v2")

LLM_MODEL_PATH = r"C:\Users\arunkarthick.l\Documents\PoC\Backend\models\Quantized Mistral Model\mistral-7b-instruct-v0.3-q4_k_m.gguf"


chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
chroma_collection = chroma_client.get_collection("products")

embedding_model = SentenceTransformer(MODEL_PATH)

LLM = Llama(
    model_path=LLM_MODEL_PATH,
    n_ctx=4096,
    n_threads=8,
    temperature=0.3,
    verbose=False
)

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

TITLE_INDEX = {
    p["title"].lower(): p["pid"]
    for p in products_collection.find({}, {"title": 1, "pid": 1})
    if p.get("title") and p.get("pid")
}

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


def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())



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
    
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        normalized = []
        for item in value:
            if "=" in item:
                key, val = item.split("=", 1)
                key = key.strip()
                val = val.strip()
                if key or val:
                    normalized.append({"key": key, "value": val})

        return {"product_specification": normalized} if normalized else None


    # ✅ Case 1: Already normalized
    if isinstance(value, dict) and "product_specification" in value:
        return normalize_specifications(value["product_specification"])

    # ✅ Case 2: Already a list
    if isinstance(value, list):
        normalized = []
        for s in value:
            if isinstance(s, dict):
                key = str(s.get("key", "")).strip()
                val = str(s.get("value", "")).strip()
                if key or val:
                    normalized.append({"key": key, "value": val})
        return {"product_specification": normalized} if normalized else None

    # ✅ Case 3: Single spec dict
    if isinstance(value, dict):
        key = str(value.get("key", "")).strip()
        val = str(value.get("value", "")).strip()
        if key or val:
            return {
                "product_specification": [
                    {"key": key, "value": val}
                ]
            }
        return None

    # ✅ Case 4: Ruby-hash-like string
    if isinstance(value, str):
        try:
            # 1️⃣ HTML unescape
            cleaned = html.unescape(value)

            # 2️⃣ Ruby hash => JSON style
            cleaned = cleaned.replace("=>", ":")

            # 3️⃣ Quote unquoted keys
            cleaned = re.sub(r'([{,]\s*)(\w+)\s*:', r'\1"\2":', cleaned)

            parsed = json.loads(cleaned)

            return normalize_specifications(parsed)

        except Exception as e:
            print("SPEC PARSE FAILED:", e)
            return None

    return None

def exact_word_match(text: str, word: str) -> bool:
    if not text:
        return False
    pattern = rf"\b{re.escape(word.lower())}\b"
    return bool(re.search(pattern, text.lower()))


def extract_primary_product_type(products):
    """
    Infer dominant product type token from search results.
    """
    tokens = []

    for p in products:
        text = " ".join(
            str(p.get(k, "")).lower()
            for k in ("title", "category_l1", "category_l2", "category_l3")
        )

        for t in re.findall(r"[a-z]{4,}", text):
            tokens.append(t)

    if not tokens:
        return None

    return Counter(tokens).most_common(1)[0][0]
def specs_to_text(specs):
    if not specs or "product_specification" not in specs:
        return "Not available"

    lines = []
    for item in specs["product_specification"]:
        key = item.get("key")
        val = item.get("value")
        if key or val:
            lines.append(f"- {key}: {val}")

    return "\n".join(lines) if lines else "Not available"

# =================================================
# SEARCH HELPERS
# =================================================
def extract_keywords(query: str):
    return [
        token for token in re.findall(r"[a-zA-Z0-9]+", query.lower())
        if len(token) > 2
    ]

def detect_gender_intent(keywords: list[str]) -> str | None:
    """
    Detects explicit gender intent in query.
    Returns 'men', 'women', or None
    """
    if any(k in ("men","men's", "mens", "boy", "boys") for k in keywords):
        return "men"
    if any(k in ("women", "womens","women's", "girl", "girls", "female") for k in keywords):
        return "women"
    return None

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
        "password": hash_password(user.password)
    })
    return {"message": "User registered successfully"}


@app.post("/auth/login")
def login(user: UserLogin):

    # ✅ ✅ ADMIN LOGIN CHECK
    if user.email == "admin@gmail.com" and user.password == "Admin@123":
        token = create_access_token({"sub": "admin"})

        return {
            "access_token": token,
            "user_id": "admin",
            "username": "Admin",
            "role": "admin"
        }

    # ✅ ✅ NORMAL USER LOGIN
    db_user = users_collection.find_one({"email": user.email})

    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": db_user["id"]})

    return {
        "access_token": token,
        "user_id": db_user["id"],
        "username": db_user.get("name", ""),
        "role": "user"
    }


# =================================================
# ✅ PRODUCT SEARCH (FINAL DESIGN)
# =================================================
@app.get("/products/search", response_model=List[Product])
def search_products(
    q: str = Query(..., min_length=1),
    top_k: int = 30
):
    # ------------------------------------------------
    # 1. Semantic Recall (Candidate Generation)
    # ------------------------------------------------
    query_embedding = embedding_model.encode(
        q,
        normalize_embeddings=True
    ).tolist()

    keywords = extract_keywords(q)
    price_intent = detect_price(q.lower())
    brand_intent = detect_brand(q.lower(), BRAND_INDEX)

    results = chroma_collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["metadatas"]
    )

    if not results or not results.get("metadatas"):
        return []

    all_metadata = results["metadatas"][0]
    ranked_results = []
    gender_intent = detect_gender_intent(keywords)

    # ------------------------------------------------
    # 2. Scoring (Semantic + Exact Intent Signals)
    # ------------------------------------------------
    for rank, meta in enumerate(all_metadata):
        pid = meta.get("pid")
        if not pid:
            continue

        score = 1  # ✅ base semantic score
        reasons = ["semantic"]

        
        title    = (meta.get("title") or "").lower()
        cat1     = (meta.get("category_l1") or "").lower()
        cat2     = (meta.get("category_l2") or "").lower()
        cat3     = (meta.get("category_l3") or "").lower()

        full_text = f"{title} {cat1} {cat2} {cat3}"
        if gender_intent == "men":
            if re.search(r"\bwomen\b|\bwomens\b|\bgirl\b|\bfemale\b", full_text):
                continue

        if gender_intent == "women":
            if re.search(r"\bmen\b|\bmens\b|\bboy\b|\bmale\b", full_text):
                continue


        # ✅ PRICE FILTER (MANDATORY)
        if price_intent:
            price = meta.get("price", 0)
            t = price_intent["type"]

            if t == "max" and price > price_intent["value"]:
                continue
            if t == "min" and price < price_intent["value"]:
                continue
            if t == "range":
                if not (price_intent["min"] <= price <= price_intent["max"]):
                    continue

            reasons.append("price_ok")

        # ✅ BRAND MATCH (EXACT WORD)
        if brand_intent:
            brand = meta.get("brand", "")
            if exact_word_match(brand, brand_intent):
                score += 3
                reasons.append(f"brand_match:{brand_intent}")

        # ✅ CATEGORY MATCH (EXACT WORD)
        for kw in keywords:
            for lvl in ("category_l1", "category_l2", "category_l3"):
                if exact_word_match(meta.get(lvl, ""), kw):
                    score += 2
                    reasons.append(f"category_match:{kw}")
                    break

        # ✅ SPECIFICATION MATCH (EXACT WORD)
        for kw in keywords:
            for spec in meta.get("specifications", []):
                if exact_word_match(str(spec), kw):
                    score += 2
                    reasons.append(f"spec_match:{kw}")
                    break
        # ✅ TITLE MATCH (LOW WEIGHT — SUPPORTING SIGNAL ONLY)
        for kw in keywords:
            if exact_word_match(meta.get("title", ""), kw):
                score += 1
                reasons.append(f"title_match:{kw}")
                break   

        ranked_results.append({
            "pid": pid,
            "score": score,
            "semantic_rank": rank,
            "reasons": reasons
        })

    # ------------------------------------------------
    # ✅ FILTER: Remove Pure-Semantic Results
    # ------------------------------------------------
    ranked_results = [
        r for r in ranked_results
        if r["score"] > 1
    ]

    if not ranked_results:
        return []

    # ------------------------------------------------
    # 3. Sort by Score then Semantic Rank
    # ------------------------------------------------
    ranked_results.sort(
        key=lambda x: (-x["score"], x["semantic_rank"])
    )

    final_pids = [r["pid"] for r in ranked_results]

    # ------------------------------------------------
    # 4. Fetch Full Product Docs
    # ------------------------------------------------
    raw_products = list(
        products_collection.find(
            {"pid": {"$in": final_pids}},
            {"_id": 0}
        )
    )

    product_map = {p["pid"]: p for p in raw_products}

    products: List[Product] = []
    for pid in final_pids:
        p = product_map.get(pid)
        if not p:
            continue

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




@app.get("/products/trending-by-category")
def trending_by_category(top_n_per_category: int = 3):
    """
    Returns top-N trending products for every category
    using dynamic consensus logic.
    """

    try:
        # ✅ Call the dynamic consensus algorithm
        category_map = get_trending_products_per_category_dynamic(
            top_n_per_category=top_n_per_category
        )

        if not category_map:
            return {}

        # ✅ Flatten product ids
        product_ids = [
            pid
            for pids in category_map.values()
            for pid in pids
        ]

        # ✅ Fetch product documents
        products = products_collection.find(
            {"pid": {"$in": product_ids}},
            {"_id": 0}
        )

        product_map = {p["pid"]: p for p in products}

        # ✅ Build response: category → products[]
        response = {}
        for category, pids in category_map.items():
            response[category] = [
                product_map[pid]
                for pid in pids
                if pid in product_map
            ]

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

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



@app.post("/recommendations/log-interaction")
def log_interaction_api(req: LogInteractionRequest):
    """
    Logs a user-product interaction.
    """
    try:
        log_product_event(
            user_id=req.user_id,
            product_id=req.product_id,
            event_type=req.event_type,
            source=req.source
        )
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/products/{pid}/similar", response_model=List[Product])
def get_similar_products(pid: str, limit: int = 6):
    """
    Retrieve products similar to the given product
    using embedding cosine similarity.
    """

    # 1️⃣ Fetch embedding for the given product
    result = chroma_collection.get(
        where={"pid": pid},
        include=["embeddings"]
    )

    # ✅ SAFE CHECK (NO boolean ambiguity)
    if (
        result is None
        or "embeddings" not in result
        or result["embeddings"] is None
        or len(result["embeddings"]) == 0
        or result["embeddings"][0] is None
    ):
        return []

    query_embedding = result["embeddings"][0]

    # 2️⃣ Query for nearest neighbors
    similar = chroma_collection.query(
        query_embeddings=[query_embedding],
        n_results=limit + 1,  # +1 because original product may appear
        include=["metadatas"]
    )

    if (
        similar is None
        or "metadatas" not in similar
        or similar["metadatas"] is None
        or len(similar["metadatas"]) == 0
    ):
        return []

    # 3️⃣ Extract similar product IDs (exclude the same product)
    similar_pids = []
    for meta in similar["metadatas"][0]:
        if meta and meta.get("pid") != pid:
            similar_pids.append(meta["pid"])

    if not similar_pids:
        return []

    # 4️⃣ Fetch full product records from MongoDB
    products = list(
        products_collection.find(
            {"pid": {"$in": similar_pids}},
            {"_id": 0}
        )
    )

    product_map = {p["pid"]: p for p in products}

    # Preserve similarity order
    ordered_products = [
        Product(**product_map[pid])
        for pid in similar_pids
        if pid in product_map
    ]

    return ordered_products

@app.get("/recommendations/user/{user_id}")
def get_user_recommendations_api(user_id: str, limit: int = 10):
    try:
        print("USER ID:", user_id)

        product_ids = get_user_recommendations(
            user_id=user_id,
            limit=limit
        )

        print("PRODUCT IDS:", product_ids)

        if not product_ids:
            return []

        products = list(
            products_collection.find(
                {"pid": {"$in": product_ids}},
                {"_id": 0}
            )
        )

        print("PRODUCT DOCS:", len(products))

        product_map = {p["pid"]: p for p in products}

        return [
            product_map[pid]
            for pid in product_ids
            if pid in product_map
        ]

    except Exception as e:
        print("❌ RECOMMENDATION ERROR:", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/home/collections")
def get_home_collections(limit: int = 20):
    """
    Home discovery collections shown before search.

    Categories:
    - Electronics
    - Furniture
    - Clothing (50% Men's Apparel + 50% Women's Apparel)

    Guarantees:
    - Exact word matching
    - Apparel-only clothing
    - One product per brand
    """

    def one_per_brand(pipeline, limit):
        return list(
            products_collection.aggregate(
                pipeline + [
                    {
                        "$group": {
                            "_id": "$brand",
                            "product": {"$first": "$$ROOT"}
                        }
                    },
                    {"$replaceRoot": {"newRoot": "$product"}},
                    {"$limit": limit}
                ]
            )
        )

    # =================================================
    # ELECTRONICS
    # =================================================
    for_electronics = one_per_brand([
        {
            "$match": {
                "$or": [
                    {"category_l1": {"$regex": r"\bElectronics\b", "$options": "i"}},
                    {"category_l2": {"$regex": r"\bLaptop Accessories\b|\bMobiles & Accessories\b", "$options": "i"}},
                    {"category_l3": {"$regex": r"\bMobile\b|\bLaptop\b|\bCharger\b|\bPower Bank\b|\bMouse\b|\bKeyboard\b", "$options": "i"}},
                    {"title": {"$regex": r"\bMobile\b|\bLaptop\b|\bTablet\b|\bHeadphone\b|\bCharger\b", "$options": "i"}},
                ]
            }
        },
        {"$project": HOME_PROJECTION},
    ], limit)

    # =================================================
    # FURNITURE
    # =================================================
    for_furniture = one_per_brand([
        {
            "$match": {
                "$or": [
                    {"category_l1": {"$regex": r"\bFurniture\b", "$options": "i"}},
                    {"category_l2": {"$regex": r"\bFurniture\b|\bSofa\b|\bChair\b|\bTable\b|\bBed\b|\bWardrobe\b", "$options": "i"}},
                    {"category_l3": {"$regex": r"\bSofa\b|\bChair\b|\bTable\b|\bBed\b|\bDining\b|\bShelf\b", "$options": "i"}},
                    {"title": {"$regex": r"\bSofa\b|\bChair\b|\bTable\b|\bBed\b|\bFurniture\b", "$options": "i"}},
                ]
            }
        },
        {"$project": HOME_PROJECTION},
    ], limit)

    # =================================================
    # CLOTHING — MEN (APPAREL ONLY)
    # =================================================
    half = limit // 2

    men_clothing = one_per_brand([
        {
            "$match": {
                "$and": [
                    # ✅ Men's apparel
                    {
                        "$or": [
                            {"category_l2": {"$regex": r"\bMen's Clothing\b|\bMen Clothing\b", "$options": "i"}},
                            {"category_l3": {"$regex": r"\bMen's Clothing\b|\bMen Clothing\b", "$options": "i"}},
                            {"title": {"$regex": r"\bMen\b|\bMen's\b|\bMens\b", "$options": "i"}},
                        ]
                    },
                    # ✅ Only apparel types
                    {
                        "$or": [
                            {"category_l3": {"$regex": r"\bShirt\b|\bT-Shirt\b|\bJeans\b|\bTrouser\b|\bPant\b|\bKurta\b|\bJacket\b|\bHoodie\b", "$options": "i"}},
                            {"title": {"$regex": r"\bShirt\b|\bT-Shirt\b|\bJeans\b|\bTrouser\b|\bPant\b|\bKurta\b|\bJacket\b|\bHoodie\b", "$options": "i"}},
                        ]
                    },
                    # ❌ EXCLUDE women
                    {
                        "$nor": [
                            {"title": {"$regex": r"\bWomen\b|\bGirl\b|\bFemale\b", "$options": "i"}},
                        ]
                    },
                    # ❌ EXCLUDE watches, footwear, accessories
                    {
                        "$nor": [
                            {"title": {"$regex": r"\bWatch\b|\bWrist Watch\b|\bSlippers\b|\bSandals\b|\bShoes\b|\bSneakers\b", "$options": "i"}},
                            {"category_l3": {"$regex": r"\bWatch\b|\bFootwear\b|\bSlippers\b|\bShoes\b", "$options": "i"}},
                        ]
                    },
                ]
            }
        },
        {"$project": HOME_PROJECTION},
    ], half)

    # =================================================
    # CLOTHING — WOMEN (APPAREL ONLY)
    # =================================================
    women_clothing = one_per_brand([
        {
            "$match": {
                "$and": [
                    {
                        "$or": [
                            {"category_l2": {"$regex": r"\bWomen's Clothing\b|\bWomen Clothing\b", "$options": "i"}},
                            {"category_l3": {"$regex": r"\bWomen's Clothing\b|\bWomen Clothing\b", "$options": "i"}},
                            {"title": {"$regex": r"\bWomen\b|\bWomen's\b|\bGirl\b|\bFemale\b", "$options": "i"}},
                        ]
                    },
                    # ✅ Only apparel
                    {
                        "$or": [
                            {"category_l3": {"$regex": r"\bDress\b|\bKurti\b|\bTop\b|\bT-Shirt\b|\bJeans\b|\bLegging\b|\bSkirt\b|\bSaree\b", "$options": "i"}},
                            {"title": {"$regex": r"\bDress\b|\bKurti\b|\bTop\b|\bT-Shirt\b|\bJeans\b|\bLegging\b|\bSkirt\b|\bSaree\b", "$options": "i"}},
                        ]
                    },
                    # ❌ EXCLUDE watches & footwear
                    {
                        "$nor": [
                            {"title": {"$regex": r"\bWatch\b|\bWrist Watch\b|\bSlippers\b|\bSandals\b|\bShoes\b", "$options": "i"}},
                            {"category_l3": {"$regex": r"\bWatch\b|\bFootwear\b|\bSlippers\b|\bShoes\b", "$options": "i"}},
                        ]
                    },
                ]
            }
        },
        {"$project": HOME_PROJECTION},
    ], half)

    # =================================================
    # MERGED CLOTHING
    # =================================================
    clothings = men_clothing + women_clothing

    return {
        "for_electronics": for_electronics,
        "for_furniture": for_furniture,
        "for_clothings": clothings,
    }



@app.post("/copilot/chat")
def copilot_chat(req: CopilotRequest):
    intent = detect_intent(req.query)

    products = retrieve_for_rag(
        query=req.query,
        embedding_model=embedding_model,
        chroma_collection=chroma_collection,
        products_collection=products_collection,
        brand_index=BRAND_INDEX,
        title_index=TITLE_INDEX,
        max_context=6
    )

    # Intent‑aware fallback
    if not products:
        if intent in {"compare", "alternative", "recommend","explain"}:
            return {
                "answer": "I couldn’t find enough relevant products in the catalog to answer this request.",
                "sources": []
            }

        # explain / qa → allow answer without products
        prompt = build_prompt("", req.query)
        return {
            "answer": generate(prompt),
            "sources": []
        }

    # Build context safely
    blocks = []
    for p in products:
        raw_specs = p.get("specifications")
        specs_txt = specs_to_text(normalize_specifications(raw_specs))

        blocks.append(f"""
Product:
- Name: {p.get("title")}
- Brand: {p.get("brand")}
- Category: {p.get("category_l3") or p.get("category_l2") or p.get("category_l1")}
- Price: {p.get("price")}
- Specifications:
{specs_txt}
""".strip())

    context = "\n\n".join(blocks[:3])  # context budget
    prompt = build_prompt(context, req.query)

    return {
        "answer": generate(prompt),
        "sources": [p.get("title") for p in products]
    }
# -------------------------------------
# PRODUCT-SPECIFIC COPILOT
# -------------------------------------
@app.post("/copilot/chat/product")
def product_copilot_chat(req: ProductCopilotRequest):
    # ---------------------------------
    # 1️⃣ Fetch the exact product
    # ---------------------------------
    product = products_collection.find_one(
        {"pid": req.product_id},
        {"_id": 0}
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    # ---------------------------------
    # 2️⃣ DO NOT run semantic retrieval
    # ---------------------------------
    # This is intentional to prevent:
    # - alternatives
    # - hallucination
    # - cross-product leakage

    raw_specs = product.get("specifications")
    specs_txt = specs_to_text(
        normalize_specifications(raw_specs)
    )

    # ---------------------------------
    # 3️⃣ Build STRICT single-product context
    # ---------------------------------
    context = f"""
Product:
- Name: {product.get("title")}
- Brand: {product.get("brand")}
- Category: {product.get("category_l3") or product.get("category_l2") or product.get("category_l1")}
- Price: {product.get("price")}
- Specifications:
{specs_txt}
""".strip()

    # ---------------------------------
    # 4️⃣ Build product-scoped prompt
    # ---------------------------------
    prompt = build_prompt(context, req.question)

    # ---------------------------------
    # 5️⃣ Generate answer
    # ---------------------------------
    answer = generate(prompt)

    return {
        "answer": answer,
        "sources": [product.get("title")]
    }

@app.get("/admin/categories-tree")
def get_categories():

    data = list(
        products_collection.find(
            {},
            {
                "_id": 0,
                "category.level_1": 1,
                "category.level_2": 1,
                "category.level_3": 1
            }
        )
    )

    tree = {}

    for item in data:
        cat = item.get("category", {})

        l1 = cat.get("level_1")
        l2 = cat.get("level_2")
        l3 = cat.get("level_3")

        if not l1:
            continue

        # ✅ LEVEL 1
        if l1 not in tree:
            tree[l1] = {}

        # ✅ LEVEL 2
        if l2:
            if l2 not in tree[l1]:
                tree[l1][l2] = {}

            # ✅ LEVEL 3
            if l3:
                tree[l1][l2][l3] = {}
        else:
            # ✅ handle cases where only L1 exists
            tree[l1] = tree[l1] or {}

    # ✅ convert dict → tree recursively
    def build_tree(node):
        result = []
        for key, value in node.items():
            entry = {"name": key}

            children = build_tree(value)
            if children:
                entry["children"] = children

            result.append(entry)

        return result

    return build_tree(tree)




@app.get("/admin/products-by-name")
def products_by_name(name: str = Query(...)):

    # ✅ escape special regex characters safely
    safe_name = re.escape(name.strip())

    # ✅ case-insensitive + partial match
    regex = {"$regex": safe_name, "$options": "i"}

    products = list(
        products_collection.find(
            {
                "$or": [
                    {"category.level_1": regex},
                    {"category.level_2": regex},
                    {"category.level_3": regex}
                ]
            },
            {"_id": 0}
        )
    )

    return products

@app.delete("/admin/products/{pid}")
def delete_product(pid: str):

    result = products_collection.delete_one({"pid": pid})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")

    return {"message": "Product deleted successfully"}

@app.put("/admin/products/{pid}")
def update_product(pid: str, product: dict):

    update_data = {
        key: value for key, value in product.items()
        if key != "images"
    }

    result = products_collection.update_one(
        {"pid": pid},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")

    return {"message": "Product updated"}

# =================================================
# IMAGE PROXY
# =================================================
@app.get("/image-proxy")
def image_proxy(url: str = Query(...)):
    try:
        r = requests.get(url, stream=True, timeout=5)
        return StreamingResponse(
            r.iter_content(1024),
            media_type=r.headers.get("Content-Type", "image/jpeg")
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
        content={"detail": "Internal server error"}
    )