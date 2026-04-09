from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List
from database import users_collection, products_collection
from models import UserRegister, UserLogin, Product
from auth import hash_password, verify_password, create_access_token
from pymongo.errors import PyMongoError
import uuid
import re
import ast
import math
import html
import requests
import traceback

# -------------------
# SAFE DB WRAPPER
# -------------------
def safe_find(cursor_fn, error_message="Database operation failed"):
    try:
        return cursor_fn()
    except PyMongoError:
        raise HTTPException(status_code=503, detail=error_message)

# -------------------
# APP INIT
# -------------------
app = FastAPI(title="Product Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------
# NORMALIZATION HELPERS
# -------------------
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

# ✅ FIXED SPECIFICATION NORMALIZATION
def normalize_specifications(value):
    if value is None:
        return None

    if isinstance(value, dict):
        return value

    if isinstance(value, list):
        valid = [
            {"key": s["key"], "value": s["value"]}
            for s in value
            if isinstance(s, dict) and "key" in s and "value" in s
        ]
        return {"product_specification": valid}

    if not isinstance(value, str):
        return None

    try:
        cleaned = html.unescape(value)
        cleaned = cleaned.replace("=>", ":")
        parsed = ast.literal_eval(cleaned)

        specs = parsed.get("product_specification", [])

        normalized = [
            {"key": item["key"], "value": item["value"]}
            for item in specs
            if isinstance(item, dict) and "key" in item and "value" in item
        ]

        return {"product_specification": normalized}

    except Exception:
        return None

# -------------------
# AUTH ROUTES
# -------------------
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

# -------------------
# PRODUCT SEARCH
# -------------------
@app.get("/products/search", response_model=List[Product])
def search_products(q: str = Query(..., min_length=1)):
    regex = re.compile(re.escape(q), re.IGNORECASE)

    query = {
        "$or": [
            {"title": regex},
            {"brand": regex},
            {"category.level_1": regex},
            {"category.level_2": regex},
            {"category.level_3": regex},
        ]
    }

    raw_products = safe_find(
        lambda: list(products_collection.find(query, {"_id": 0}).limit(20)),
        "Failed to fetch products"
    )

    products: List[Product] = []

    for p in raw_products:
        p["brand"] = normalize_string(p.get("brand"))
        p["images"] = normalize_list(p.get("images"))
        p["category"] = normalize_dict(p.get("category"))
        p["price"] = normalize_dict(p.get("price"))
        p["rating"] = normalize_dict(p.get("rating"))
        p["specifications"] = normalize_specifications(p.get("specifications"))

        products.append(Product(**p))

    return products

# -------------------
# PRODUCT DETAIL
# -------------------
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

# -------------------
# IMAGE PROXY
# -------------------
@app.get("/image-proxy")
def image_proxy(url: str = Query(...)):
    try:
        response = requests.get(
            url,
            stream=True,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Image not found")

        return StreamingResponse(
            response.iter_content(chunk_size=1024),
            media_type=response.headers.get("Content-Type", "image/jpeg")
        )
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=500, detail="Failed to fetch image")

# -------------------
# GLOBAL EXCEPTION HANDLER
# -------------------
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    print("Unhandled Exception:")
    traceback.print_exc()

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."}
    )