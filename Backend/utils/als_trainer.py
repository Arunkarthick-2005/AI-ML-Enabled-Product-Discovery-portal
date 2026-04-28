import math
import numpy as np
import scipy.sparse as sparse
from implicit.als import AlternatingLeastSquares
from pymongo import MongoClient
from collections import defaultdict
from datetime import datetime, timezone

# ====================================================
# CONFIGURATION
# ====================================================
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "product_db"
INTERACTIONS_COLLECTION = "user_interactions"

# Event base weights
EVENT_WEIGHTS = {
    "view": 1.0,
    "search_view": 2.0,
    "search_impression": 0.3
}

# Time decay settings
TIME_DECAY_LAMBDA = 0.05  # exponential decay factor

# ALS hyperparameters
ALS_FACTORS = 50
ALS_ITERATIONS = 20
ALS_REGULARIZATION = 0.1

# ====================================================
# DATABASE CONNECTION
# ====================================================
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
interactions_col = db[INTERACTIONS_COLLECTION]

# ====================================================
# TIME DECAY FUNCTION
# ====================================================
def time_decay(timestamp: datetime) -> float:
    """
    Applies exponential time decay based on interaction age.
    """
    now = datetime.now(timezone.utc)
    age_days = (now - timestamp).days
    return math.exp(-TIME_DECAY_LAMBDA * age_days)

# ====================================================
# BUILD USER × PRODUCT MATRIX
# ====================================================
def build_interaction_matrix():
    user_index = {}
    product_index = {}
    interaction_strength = defaultdict(float)

    users, products = set(), set()

    interactions = interactions_col.find({})

    for i in interactions:
        user_id = i["user_id"]
        product_id = i["product_id"]
        event_type = i["event_type"]
        timestamp = i.get("timestamp")

        base_weight = EVENT_WEIGHTS.get(event_type)
        if base_weight is None or not timestamp:
            continue

        decay = time_decay(timestamp)
        final_weight = base_weight * decay

        users.add(user_id)
        products.add(product_id)
        interaction_strength[(user_id, product_id)] += final_weight

    # Assign matrix indices
    for idx, user in enumerate(users):
        user_index[user] = idx
    for idx, product in enumerate(products):
        product_index[product] = idx

    rows, cols, values = [], [], []

    for (u, p), score in interaction_strength.items():
        rows.append(user_index[u])
        cols.append(product_index[p])
        values.append(score)

    matrix = sparse.csr_matrix(
        (values, (rows, cols)),
        shape=(len(users), len(products))
    )

    return user_index, product_index, matrix

# ====================================================
# TRAIN ALS MODEL
# ====================================================
def train_als_model():
    user_index, product_index, matrix = build_interaction_matrix()

    model = AlternatingLeastSquares(
        factors=ALS_FACTORS,
        iterations=ALS_ITERATIONS,
        regularization=ALS_REGULARIZATION
    )

    # implicit ALS expects item × user matrix
    model.fit(matrix.T)

    return model, user_index, product_index, matrix

# ====================================================
# INITIALIZE MODEL (ON APP START)
# ====================================================
_model, _user_index, _product_index, _matrix = train_als_model()

_reverse_product_index = {
    idx: pid for pid, idx in _product_index.items()
}

# ====================================================
# USER‑PERSONALIZED RECOMMENDATIONS
# ====================================================
def recommend_for_user(user_id: str, limit: int = 10):
    if user_id not in _user_index:
        return []

    user_idx = _user_index[user_id]

    recommendations = _model.recommend(
        userid=user_idx,
        user_items=_matrix,
        N=limit
    )

    return [
        _reverse_product_index[item_idx]
        for item_idx, _ in recommendations
    ]

# ====================================================
# MOST VISITED / SEARCHED PRODUCTS (GLOBAL)
# ====================================================
def most_popular_products(limit: int = 10):
    """
    Computes global product popularity from ALS latent factors.
    """
    scores = _model.item_factors.sum(axis=1)
    top_indices = np.argsort(scores)[-limit:][::-1]

    return [
        _reverse_product_index[idx]
        for idx in top_indices
    ]
