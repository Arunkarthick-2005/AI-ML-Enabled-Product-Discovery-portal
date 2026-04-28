import os
import uuid
import ast
import math
import html
import json
import re
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
    get_trending_categories,
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
    db_user = users_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": db_user["id"]})
    return {"access_token": token}


# =================================================
# ✅ PRODUCT SEARCH (FINAL DESIGN)
# =================================================
@app.get("/products/search", response_model=List[Product])
def search_products(
    q: str = Query(..., min_length=1),
    top_k: int = 30
):
    # ------------------------------------------------
    # 1. Semantic recall (ALWAYS)
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

    # ------------------------------------------------
    # 2. UNIFIED MATCHING + SCORING
    # ------------------------------------------------
    for rank, meta in enumerate(all_metadata):
        pid = meta.get("pid")
        if not pid:
            continue

        score = 1  # ✅ base score for semantic recall
        reasons = ["semantic"]

        # ✅ PRICE (MANDATORY)
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

        # ✅ BRAND MATCH
        if brand_intent:
            brand = meta.get("brand")
            if brand and normalize_text(brand) == normalize_text(brand_intent):
                score += 3
                reasons.append(f"brand_match:{brand_intent}")

        # ✅ CATEGORY MATCH
        for kw in keywords:
            for lvl in ["category_l1", "category_l2", "category_l3"]:
                if meta.get(lvl) and kw in meta[lvl].lower():
                    score += 2
                    reasons.append(f"category_match:{kw}")
                    break

        # ✅ SPECIFICATION MATCH
        for kw in keywords:
            for spec in meta.get("specifications", []):
                if kw in str(spec).lower():
                    score += 2
                    reasons.append(f"spec_match:{kw}")
                    break

        ranked_results.append({
            "pid": pid,
            "score": score,
            "semantic_rank": rank,
            "reasons": reasons
        })

    if not ranked_results:
        return []

    # ------------------------------------------------
    # 3. SORT BY SCORE (DESC) THEN SEMANTIC RANK
    # ------------------------------------------------
    ranked_results.sort(
        key=lambda x: (-x["score"], x["semantic_rank"])
    )

    final_pids = [r["pid"] for r in ranked_results]

    # ------------------------------------------------
    # DEBUG OUTPUT
    # ------------------------------------------------
    print("\n===== VERSION B RANKING DEBUG =====")
    for r in ranked_results:
        print(
            f"PID: {r['pid']} | "
            f"SCORE: {r['score']} | "
            f"REASONS: {r['reasons']}"
        )
    print("==================================\n")

    # ------------------------------------------------
    # 4. FETCH FULL PRODUCTS
    # ------------------------------------------------
    raw_products = list(
        products_collection.find(
            {"pid": {"$in": final_pids}},
            {"_id": 0}
        )
    )

    # Preserve ranking order
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
def trending_by_category(
    top_k: int = 5,
    category_level: str = "category_l2"
):
    """
    Returns top K trending categories with their top product.
    """
    try:
        category_map = get_trending_categories(
            top_k_categories=top_k,
            category_level=category_level
        )

        if not category_map:
            return {}

        product_ids = [
            pid
            for pids in category_map.values()
            for pid in pids
        ]

        products = list(
            products_collection.find(
                {"pid": {"$in": product_ids}},
                {"_id": 0}
            )
        )

        product_map = {p["pid"]: p for p in products}

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


from utils.als_trainer import recommend_for_user

@app.get("/recommendations/ml/{user_id}")
def als_recommendations(user_id: str):
    product_ids = recommend_for_user(user_id)

    if not product_ids:
        return []

    products = list(
        products_collection.find(
            {"pid": {"$in": product_ids}},
            {"_id": 0}
        )
    )

    product_map = {p["pid"]: p for p in products}
    return [product_map[pid] for pid in product_ids if pid in product_map]

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