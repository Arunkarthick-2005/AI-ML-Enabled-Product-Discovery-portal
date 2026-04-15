from sentence_transformers import SentenceTransformer
import chromadb
from Backend.database import products_collection

import os
import html
import re

# ------------------------------
# CONFIG
# ------------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

MODEL_PATH = os.path.join(BASE_DIR, "models", "all-MiniLM-L6-v2")
CHROMA_PERSIST_DIR = r"C:\Users\arunkarthick.l\Documents\PoC\Backend\chroma_db"
COLLECTION_NAME = "products"

BATCH_SIZE = 1000
DEBUG_LIMIT = 10   # set to 0 to disable spec debug logs

# ------------------------------
# LOAD EMBEDDING MODEL (OFFLINE)
# ------------------------------
print("Loading embedding model...")
model = SentenceTransformer(MODEL_PATH)

# ------------------------------
# INIT CHROMADB (OFFLINE)
# ------------------------------
client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"}
)

# ------------------------------
# HELPER FUNCTIONS
# ------------------------------
def safe_text(value):
    return value if isinstance(value, str) else ""

def safe_meta_str(value):
    return value.lower() if isinstance(value, str) else ""

def safe_meta_int(value):
    return value if isinstance(value, (int, float)) else 0


def normalize_specifications(value):
    """
    Parses Flipkart-style Ruby-hash specification strings.

    Returns:
      {
        "product_specification": [
          {"key": "...", "value": "..."},
          ...
        ]
      }
    or
      None (if specs are nil / missing)
    """

    if not value or not isinstance(value, str):
        return None

    text = html.unescape(value)

    # ✅ Ruby nil → valid "no specs" case
    if re.search(r'"product_specification"\s*=>\s*nil', text):
        return None

    # ✅ Robust regex extractor (no JSON parsing)
    pattern = re.compile(
        r'"key"\s*=>\s*"([^"]*)"\s*,\s*"value"\s*=>\s*"([^"]*)"'
    )

    matches = pattern.findall(text)
    if not matches:
        return None

    specs = []
    for key, val in matches:
        key = key.strip()
        val = val.strip()
        if key or val:
            specs.append({
                "key": key,
                "value": val
            })

    return {"product_specification": specs} if specs else None


def specs_to_text(normalized_specs):
    """
    Converts specs to embedding-friendly text:
    Fabric: Cotton. Type: Wall Sticker. Height: 120 cm
    """
    if not normalized_specs:
        return ""

    parts = []
    for s in normalized_specs["product_specification"]:
        key = s.get("key", "").strip()
        val = s.get("value", "").strip()
        if key and val:
            parts.append(f"{key}: {val}")
        elif val:
            parts.append(val)

    return ". ".join(parts)


def specs_to_kv_list(normalized_specs):
    """
    Converts specs to ChromaDB-safe metadata format:
    ["Fabric=Cotton", "Type=Wall Sticker", ...]
    """
    if not normalized_specs:
        return None

    return [
        f"{s['key']}={s['value']}"
        for s in normalized_specs["product_specification"]
        if s.get("key") and s.get("value")
    ]


# ------------------------------
# FETCH PRODUCTS FROM MONGODB
# ------------------------------
print("Fetching products from MongoDB...")
products = products_collection.find({}, {"_id": 0})

documents = []
metadatas = []
ids = []

debug_count = 0

for product in products:
    pid = product.get("pid")
    if not pid:
        continue

    # ✅ SPEC PARSING
    raw_specs = product.get("specifications")
    normalized_specs = normalize_specifications(raw_specs)
    spec_text = specs_to_text(normalized_specs)
    spec_kv_list = specs_to_kv_list(normalized_specs)


    # ✅ BUILD EMBEDDING TEXT (PHASE‑1 CORE)
    text = " ".join(filter(None, [
        safe_text(product.get("title")),
        safe_text(product.get("brand")),
        safe_text(product.get("description")),
        safe_text(product.get("category", {}).get("level_1")),
        safe_text(product.get("category", {}).get("level_2")),
        safe_text(product.get("category", {}).get("level_3")),
        spec_text
    ])).strip()

    if not text:
        continue

    documents.append(text)
    ids.append(pid)

    # ✅ METADATA (CHROMA‑SAFE)
    metadatas.append({
        "pid": pid,
        "brand": safe_meta_str(product.get("brand")),
        "category_l1": safe_meta_str(product.get("category", {}).get("level_1")),
        "category_l2": safe_meta_str(product.get("category", {}).get("level_2")),
        "category_l3": safe_meta_str(product.get("category", {}).get("level_3")),
        "price": safe_meta_int(product.get("price", {}).get("selling")),
        "specifications": spec_kv_list  # ✅ list[str] – valid for ChromaDB
    })

print(f"\n✅ Prepared {len(documents)} products for embedding")

# ------------------------------
# CREATE EMBEDDINGS
# ------------------------------
embeddings = model.encode(
    documents,
    batch_size=32,
    normalize_embeddings=True,
    show_progress_bar=True
)

# ------------------------------
# UPSERT INTO CHROMADB ✅
# ------------------------------
print("Storing embeddings into ChromaDB...")

total = len(ids)

for i in range(0, total, BATCH_SIZE):
    end = min(i + BATCH_SIZE, total)

    collection.upsert(
        ids=ids[i:end],
        documents=documents[i:end],
        metadatas=metadatas[i:end],
        embeddings=embeddings[i:end]
    )

    print(f"✅ Upserted {end}/{total}")

print("✅ Vector DB updated successfully!")
print(f"✅ Stored {len(ids)} product embeddings")