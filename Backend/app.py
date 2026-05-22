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
import csv
from fastapi import UploadFile, File
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

class ProductCreateRequest(BaseModel):
    title: str
    brand: Optional[str] = ""
    description: Optional[str] = ""
    
    price: dict
    category: dict

    images: List[str]

    specifications: Optional[List[dict]] = []

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

def safe_text(value):
    return value if isinstance(value, str) else ""

def safe_meta_str(value):
    return value.lower() if isinstance(value, str) else ""

def safe_meta_int(value):
    return value if isinstance(value, (int, float)) else 0


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
    top_k: int = 80
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

@app.get("/products/{pid}/alternatives", response_model=List[Product])
def get_next_best_alternatives(
    pid: str,
    query: str = "",
    limit: int = 5
):
    """
    Final Version:
    ✅ Dual similarity (product + query)
    ✅ Intent-aware pricing (FIXED)
    ✅ Proper fallback (no query → product only)
    ✅ Safe embedding handling
    ✅ Optimized DB calls
    ✅ Normalized output
    """

    # -----------------------------------------------------
    # ✅ 1. BASE PRODUCT
    # -----------------------------------------------------
    base_product = products_collection.find_one({"pid": pid})
    if not base_product:
        return []

    base_price = base_product.get("price", {}).get("selling", 0)

    base_category = (
        base_product.get("category", {}).get("level_3") or
        base_product.get("category", {}).get("level_2") or
        base_product.get("category", {}).get("level_1")
    )

    # -----------------------------------------------------
    # ✅ 2. INTENT DETECTION
    # -----------------------------------------------------
    query_lower = query.lower()
    keywords = extract_keywords(query_lower)
    brand_intent = detect_brand(query_lower, BRAND_INDEX)

    is_price_intent = any(k in query_lower for k in ["cheap", "budget", "under", "low","less than"])
    is_premium_intent = any(k in query_lower for k in ["best", "top", "premium","above","greater than"])

    # -----------------------------------------------------
    # ✅ 3. DYNAMIC WEIGHTS (FIXED)
    # -----------------------------------------------------
    weights = {
        "similarity": 0.4,
        "price": 0.2,
        "brand": 0.2,
        "spec": 0.2
    }

    if is_price_intent:
        weights["price"] = 0.5
        weights["similarity"] = 0.3

    elif is_premium_intent:
        weights["price"] = 0.1   # ✅ reduce price effect
        weights["similarity"] = 0.5
        weights["spec"] = 0.4

    if brand_intent:
        weights["brand"] += 0.3

    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    # -----------------------------------------------------
    # ✅ 4. BASE EMBEDDING (SAFE)
    # -----------------------------------------------------
    base_result = chroma_collection.get(
        where={"pid": pid},
        include=["embeddings"]
    )

    if (
        base_result is None or
        "embeddings" not in base_result or
        base_result["embeddings"] is None or
        len(base_result["embeddings"]) == 0 or
        base_result["embeddings"][0] is None
    ):
        return []

    base_embedding = np.array(base_result["embeddings"][0])

    # -----------------------------------------------------
    # ✅ 5. QUERY EMBEDDING (OPTIONAL)
    # -----------------------------------------------------
    query_embedding = None
    if query.strip():
        query_embedding = np.array(
            embedding_model.encode(query, normalize_embeddings=True)
        )

    # -----------------------------------------------------
    # ✅ 6. RETRIEVE CANDIDATES
    # -----------------------------------------------------
    similar = chroma_collection.query(
        query_embeddings=[base_embedding.tolist()],
        n_results=20,
        include=["metadatas", "distances", "embeddings"]
    )

    if (
        similar is None or
        "metadatas" not in similar or
        similar["metadatas"] is None or
        len(similar["metadatas"]) == 0
    ):
        return []

    if (
        "embeddings" not in similar or
        similar["embeddings"] is None or
        len(similar["embeddings"]) == 0
    ):
        return []

    candidates = similar["metadatas"][0]
    distances = similar.get("distances", [[]])[0]
    candidate_embeddings = similar["embeddings"][0]

    # -----------------------------------------------------
    # ✅ 7. BATCH FETCH PRODUCTS
    # -----------------------------------------------------
    candidate_pids = [
        meta.get("pid")
        for meta in candidates
        if meta.get("pid") and meta.get("pid") != pid
    ]

    products_data = list(
        products_collection.find(
            {"pid": {"$in": candidate_pids}},
            {"_id": 0}
        )
    )

    product_map = {p["pid"]: p for p in products_data}

    scored_products = []

    # -----------------------------------------------------
    # ✅ 8. SCORING LOOP
    # -----------------------------------------------------
    for meta, dist, cand_emb in zip(candidates, distances, candidate_embeddings):

        candidate_pid = meta.get("pid")
        if not candidate_pid or candidate_pid == pid:
            continue

        product = product_map.get(candidate_pid)
        if not product:
            continue

        # ✅ CATEGORY FILTER
        category = (
            product.get("category", {}).get("level_3") or
            product.get("category", {}).get("level_2") or
            product.get("category", {}).get("level_1")
        )

        if category != base_category:
            continue

        price = product.get("price", {}).get("selling", 0)
        brand = (product.get("brand") or "").lower()
        specs = product.get("specifications", {})

        if price == 0:
            continue

        # -------------------------------------------------
        # ✅ 9. DUAL SIMILARITY (WITH FALLBACK)
        # -------------------------------------------------
        sim_product = 1 / (1 + dist) if dist is not None else 0

        if query_embedding is not None and cand_emb is not None:
            cand_vec = np.array(cand_emb)
            sim_query = float(np.dot(query_embedding, cand_vec))
            final_similarity = 0.6 * sim_product + 0.4 * sim_query
        else:
            final_similarity = sim_product

        # -------------------------------------------------
        # ✅ 10. FIXED PRICE LOGIC (IMPORTANT ✅)
        # -------------------------------------------------
        if is_price_intent:
            # ✅ prefer cheaper
            price_score = max(0, (base_price - price) / base_price)
        elif is_premium_intent:
            # ✅ allow higher price products
            price_score = (price - base_price) / base_price if base_price else 0
        else:
            # ✅ balanced
            price_score = (base_price - price) / base_price if base_price else 0

        # ✅ clamp values
        price_score = max(-0.5, min(price_score, 0.5))

        # -------------------------------------------------
        # ✅ 11. BRAND + SPEC
        # -------------------------------------------------
        brand_score = 1 if (brand_intent and brand_intent in brand) else 0

        normalized_specs = normalize_specifications(specs)
        spec_text = specs_to_text(normalized_specs).lower() if normalized_specs else ""

        spec_match_score = 0
        for kw in keywords:
            if kw in spec_text:
                spec_match_score += 1

        if keywords:
            spec_match_score /= len(keywords)

        # -------------------------------------------------
        # ✅ 12. FINAL SCORE
        # -------------------------------------------------
        final_score = (
            final_similarity * weights["similarity"] +
            price_score * weights["price"] +
            brand_score * weights["brand"] +
            spec_match_score * weights["spec"]
        )

        scored_products.append((product, final_score))

    if not scored_products:
        return []

    # -----------------------------------------------------
    # ✅ SORT
    # -----------------------------------------------------
    scored_products.sort(key=lambda x: x[1], reverse=True)
    top_products = [p for p, _ in scored_products[:limit]]

    # -----------------------------------------------------
    # ✅ NORMALIZATION
    # -----------------------------------------------------
    normalized_products = []

    for p in top_products:
        p["brand"] = normalize_string(p.get("brand"))
        p["images"] = normalize_list(p.get("images"))
        p["category"] = normalize_dict(p.get("category"))
        p["price"] = normalize_dict(p.get("price"))
        p["specifications"] = normalize_specifications(
            p.get("specifications")
        )

        normalized_products.append(Product(**p))

    return normalized_products


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


@app.post("/admin/products")
def create_product(product: ProductCreateRequest):

    try:

        # ✅ GENERATE PID
        pid = str(uuid.uuid4())

        # ✅ NORMALIZE SPECIFICATIONS (SAME AS SCRIPT)
        normalized_specs = normalize_specifications(
            product.specifications
        )

        spec_text = specs_to_text(normalized_specs)

        spec_kv_list = [
            f"{s['key']}={s['value']}"
            for s in normalized_specs.get("product_specification", [])
            if s.get("key") and s.get("value")
        ] if normalized_specs else None

        # =====================================
        # ✅ SAVE TO MONGODB
        # =====================================
        new_product = {
            "pid": pid,
            "title": product.title,
            "brand": product.brand,
            "description": product.description,

            "images": product.images,

            "price": {
                "selling": product.price.get("selling", 0),
                "retail": product.price.get("retail", 0),
            },

            "category": {
                "level_1": product.category.get("level_1"),
                "level_2": product.category.get("level_2"),
                "level_3": product.category.get("level_3"),
            },

            "specifications": {
                "product_specification": product.specifications or []
            }
        }

        products_collection.insert_one(new_product)

        # =====================================
        # ✅ BUILD DOCUMENT (SAME AS SCRIPT)
        # =====================================
        document = " ".join(filter(None, [
            safe_text(new_product.get("title")),
            safe_text(new_product.get("brand")),
            safe_text(new_product.get("description")),
            safe_text(new_product["category"].get("level_1")),
            safe_text(new_product["category"].get("level_2")),
            safe_text(new_product["category"].get("level_3")),
            spec_text
        ])).strip()

        # ✅ SAFETY CHECK
        if not document:
            return {"message": "Product created but skipped embedding"}

        # =====================================
        # ✅ CREATE EMBEDDING
        # =====================================
        embedding = embedding_model.encode(
            document,
            normalize_embeddings=True
        ).tolist()

        # =====================================
        # ✅ METADATA (MATCH SCRIPT EXACTLY)
        # =====================================
        metadata = {
            "pid": pid,
            "title": safe_meta_str(new_product.get("title")),
            "brand": safe_meta_str(new_product.get("brand")),
            "description": safe_meta_str(new_product.get("description")),

            "category_l1": safe_meta_str(new_product["category"].get("level_1")),
            "category_l2": safe_meta_str(new_product["category"].get("level_2")),
            "category_l3": safe_meta_str(new_product["category"].get("level_3")),

            "price": safe_meta_int(new_product["price"].get("selling")),

            "specifications": spec_kv_list  # ✅ MUST BE list[str]
        }

        # =====================================
        # ✅ UPSERT INTO CHROMADB
        # =====================================
        chroma_collection.upsert(
            ids=[pid],
            documents=[document],
            embeddings=[embedding],
            metadatas=[metadata]
        )

        return {
            "message": "Product created successfully",
            "pid": pid
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/products/upload-csv")
async def upload_products_csv(file: UploadFile = File(...)):

    try:
        contents = await file.read()
        decoded = contents.decode("utf-8").splitlines()
        reader = csv.DictReader(decoded)

        inserted_count = 0
        skipped_count = 0

        for row in reader:

            # =========================================
            # ✅ SKIP NULL/INVALID ROWS
            # =========================================
            if (
                not row.get("title") or
                not row.get("price_selling") or
                not row.get("category_l1")
            ):
                skipped_count += 1
                continue

            # =========================================
            # ✅ GENERATE PID
            # =========================================
            pid = str(uuid.uuid4())

            # =========================================
            # ✅ IMAGE HANDLING (FIXED ✅)
            # =========================================
            raw_images = row.get("images")

            if raw_images and isinstance(raw_images, str):
                images = [
                    img.strip()
                    for img in raw_images.split(",")
                    if img.strip()
                ]
            else:
                images = []

            # ✅ optional fallback (prevents UI crash)
            if not images:
                images = ["https://via.placeholder.com/150"]

            # =========================================
            # ✅ SPECIFICATIONS PARSE
            # =========================================
            specs_list = []

            raw_specs = row.get("specifications", "")
            for item in raw_specs.split(","):
                if ":" in item:
                    key, val = item.split(":", 1)
                    specs_list.append({
                        "key": key.strip(),
                        "value": val.strip()
                    })

            normalized_specs = normalize_specifications({
                "product_specification": specs_list
            })

            spec_text = specs_to_text(normalized_specs)

            spec_kv_list = [
                f"{s['key']}={s['value']}"
                for s in normalized_specs.get("product_specification", [])
                if s.get("key") and s.get("value")
            ] if normalized_specs else None

            # =========================================
            # ✅ BUILD PRODUCT (MONGODB STRUCTURE ✅)
            # =========================================
            product_doc = {
                "pid": pid,
                "title": row.get("title"),
                "brand": row.get("brand"),
                "description": row.get("description"),

                "images": images,

                "price": {
                    "selling": int(float(row.get("price_selling", 0))),
                    "retail": int(float(
                        row.get("price_retail", row.get("price_selling", 0))
                    ))
                },

                "category": {
                    "level_1": row.get("category_l1"),
                    "level_2": row.get("category_l2"),
                    "level_3": row.get("category_l3")
                },

                "specifications": {
                    "product_specification": specs_list
                }
            }

            # =========================================
            # ✅ INSERT INTO MONGODB
            # =========================================
            products_collection.insert_one(product_doc)

            # =========================================
            # ✅ BUILD EMBEDDING DOCUMENT (MATCH SCRIPT ✅)
            # =========================================
            document = " ".join(filter(None, [
                safe_text(product_doc.get("title")),
                safe_text(product_doc.get("brand")),
                safe_text(product_doc.get("description")),
                safe_text(product_doc["category"].get("level_1")),
                safe_text(product_doc["category"].get("level_2")),
                safe_text(product_doc["category"].get("level_3")),
                spec_text
            ])).strip()

            if not document:
                continue

            # =========================================
            # ✅ CREATE EMBEDDING
            # =========================================
            embedding = embedding_model.encode(
                document,
                normalize_embeddings=True
            ).tolist()

            # =========================================
            # ✅ METADATA (MATCH SCRIPT EXACTLY ✅)
            # =========================================
            metadata = {
                "pid": pid,
                "title": safe_meta_str(product_doc.get("title")),
                "brand": safe_meta_str(product_doc.get("brand")),
                "description": safe_meta_str(product_doc.get("description")),

                "category_l1": safe_meta_str(product_doc["category"].get("level_1")),
                "category_l2": safe_meta_str(product_doc["category"].get("level_2")),
                "category_l3": safe_meta_str(product_doc["category"].get("level_3")),

                "price": safe_meta_int(product_doc["price"].get("selling")),

                "specifications": spec_kv_list
            }

            # =========================================
            # ✅ UPSERT INTO CHROMADB ✅
            # =========================================
            chroma_collection.upsert(
                ids=[pid],
                documents=[document],
                embeddings=[embedding],
                metadatas=[metadata]
            )

            inserted_count += 1

        return {
            "message": "CSV upload completed successfully",
            "inserted": inserted_count,
            "skipped": skipped_count
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

@app.delete("/admin/products/{pid}")
def delete_product(pid: str):

    try:
        # ✅ DELETE FROM MONGODB
        result = products_collection.delete_one({"pid": pid})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")

        # ✅ ✅ DELETE FROM CHROMADB
        chroma_collection.delete(ids=[pid])

        return {"message": "Product deleted successfully"}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/admin/products/{pid}")
def update_product(pid: str, product: dict):

    try:
        # ✅ REMOVE images (as per your design)
        update_data = {
            key: value for key, value in product.items()
            if key != "images"
        }

        # ✅ UPDATE MONGODB
        result = products_collection.update_one(
            {"pid": pid},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")

        # ✅ FETCH UPDATED PRODUCT
        updated_product = products_collection.find_one(
            {"pid": pid},
            {"_id": 0}
        )

        if not updated_product:
            raise HTTPException(status_code=404, detail="Product not found")

        # ✅ NORMALIZE DATA
        updated_product["brand"] = normalize_string(updated_product.get("brand"))
        updated_product["images"] = normalize_list(updated_product.get("images"))
        updated_product["category"] = normalize_dict(updated_product.get("category"))
        updated_product["price"] = normalize_dict(updated_product.get("price"))
        updated_product["specifications"] = normalize_specifications(
            updated_product.get("specifications")
        )

        # =====================================
        # ✅ REBUILD EMBEDDING TEXT
        # =====================================
        specs_text = specs_to_text(updated_product.get("specifications"))

        embedding_text = f"""
        {updated_product.get("title")}
        Brand: {updated_product.get("brand")}
        Category: {updated_product.get("category", {}).get("level_1")} 
                  {updated_product.get("category", {}).get("level_2")} 
                  {updated_product.get("category", {}).get("level_3")}
        Description: {updated_product.get("description")}
        Specifications:
        {specs_text}
        """

        # ✅ CREATE NEW EMBEDDING
        embedding = embedding_model.encode(
            embedding_text,
            normalize_embeddings=True
        ).tolist()

        # =====================================
        # ✅ UPDATE CHROMADB (VERY IMPORTANT)
        # =====================================
        chroma_collection.update(
            ids=[pid],
            embeddings=[embedding],
            metadatas=[{
                "pid": pid,
                "title": updated_product.get("title"),
                "brand": updated_product.get("brand"),
                "price": updated_product.get("price", {}).get("selling"),

                "category_l1": updated_product.get("category", {}).get("level_1"),
                "category_l2": updated_product.get("category", {}).get("level_2"),
                "category_l3": updated_product.get("category", {}).get("level_3"),

                "specifications": specs_text
            }]
        )

        return {"message": "Product updated successfully"}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# =================================================
# IMAGE PROXY
# =================================================
@app.get("/image-proxy")
def image_proxy(url: str):

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        r = requests.get(url, headers=headers, stream=True, timeout=5)

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