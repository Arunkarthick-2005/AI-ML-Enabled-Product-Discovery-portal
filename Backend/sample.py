import chromadb
import os
from sentence_transformers import SentenceTransformer

# ---------------------------------
# Paths (must match build script)
# ---------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PERSIST_DIR = os.path.join(BASE_DIR, "chroma_db")
MODEL_PATH = os.path.join(BASE_DIR, "models", "all-MiniLM-L6-v2")

# ---------------------------------
# Load local embedding model
# ---------------------------------
model = SentenceTransformer(MODEL_PATH)

# ---------------------------------
# Load persistent ChromaDB
# ---------------------------------
client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = client.get_collection("products")

print("✅ Total vectors in DB:", collection.count())

# ---------------------------------
# Fetch FIRST stored product
# ---------------------------------
result = collection.get(
    limit=1,
    include=["documents", "embeddings", "metadatas"]
)

document = result["documents"][0]
embedding = result["embeddings"][0]
metadata = result["metadatas"][0]

# ---------------------------------
# PRINT VERIFICATION OUTPUT
# ---------------------------------
print("\n================ PRODUCT DOCUMENT ================\n")
print(document)

print("\n================ PRODUCT METADATA ================\n")
for k, v in metadata.items():
    print(f"{k}: {v}")

print("\n================ EMBEDDING VECTOR ================\n")
print(embedding)  # ⚠️ LONG LIST (expected)

print("\n================ EMBEDDING INFO ==================\n")
print("Embedding length:", len(embedding))
print("First 20 values:", embedding[:])
print("Last 20 values:", embedding[-20:])