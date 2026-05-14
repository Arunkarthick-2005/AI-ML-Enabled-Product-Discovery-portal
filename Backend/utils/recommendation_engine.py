from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple
import math
from collections import defaultdict

# ✅ IMPORT EXISTING COLLECTION
from database import product_view_events,products_collection

def ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts
# =================================================
# CONFIGURATION
# =================================================

EVENT_WEIGHTS = {
    "view": 1.0,               # normal product view
    "search_view": 2.5,        # strong intent
    "similar_view": 1.8        # Medium signal
}

# Higher value = recent days matter more
TIME_DECAY_LAMBDA = 0.12

# =================================================
# LOG INTERACTION (UPDATED LOGIC)
# =================================================

def log_product_event(
    user_id: str,
    product_id: str,
    event_type: str,
    source: str = "unknown"
):
    """
    Stores product interaction events.
    Works with view / search_view / search_impression.
    """

    product_view_events.insert_one({
        "user_id": user_id.lower(),   # ✅ normalize
        "product_id": product_id,
        "event_type": event_type,     # ✅ explicit
        "source": source,
        "timestamp": datetime.now(timezone.utc)
    })

# =================================================
# TIME DECAY FUNCTION
# =================================================

def _time_decay(timestamp: datetime) -> float:
    now = datetime.now(timezone.utc)

    # ✅ FIX: make Mongo timestamp timezone-aware
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    age_days = max((now - timestamp).days, 0)
    return math.exp(-TIME_DECAY_LAMBDA * age_days)

def get_trending_products_per_category_dynamic(
    top_n_per_category: int = 3,
    lookback_days: int = 7,
    consensus_ratio: float = 0.3,
):
    now = datetime.now(timezone.utc)
    lookback_cutoff = now - timedelta(days=lookback_days)

    product_scores = defaultdict(float)
    product_users = defaultdict(set)
    active_users = set()

    cursor = product_view_events.find({
        "event_type": {"$in": ["view", "search_view", "similar_view"]},
        "timestamp": {"$gte": lookback_cutoff}
    })

    for doc in cursor:
        pid = doc.get("product_id")
        uid = doc.get("user_id")
        event_type = doc.get("event_type")
        ts = doc.get("timestamp")

        if not pid or not uid or not ts:
            continue

        # ✅ FIX: normalize timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        weight = EVENT_WEIGHTS.get(event_type)
        if not weight:
            continue

        active_users.add(uid)
        product_users[pid].add(uid)

        age_days = max((now - ts).days, 0)
        decay = math.exp(-TIME_DECAY_LAMBDA * age_days)

        product_scores[pid] += weight * decay

    if not active_users or not product_scores:
        return {}

    # ✅ dynamic consensus
    min_users = max(2, math.ceil(len(active_users) * consensus_ratio))

    eligible_products = {
        pid: score
        for pid, score in product_scores.items()
        if len(product_users[pid]) >= min_users
    }

    if not eligible_products:
        return {}

    product_docs = products_collection.find(
        {"pid": {"$in": list(eligible_products.keys())}},
        {"pid": 1, "category": 1}
    )

    category_to_products = defaultdict(list)

    for p in product_docs:
        pid = p.get("pid")
        category_obj = p.get("category") or {}

        category = (
            category_obj.get("level_3")
            or category_obj.get("level_2")
            or category_obj.get("level_1")
        )

        if not category:
            continue

        category_to_products[category].append(
            (pid, eligible_products[pid])
        )

    result = {}
    for category, products in category_to_products.items():
        products.sort(key=lambda x: x[1], reverse=True)
        result[category] = [
            pid for pid, _ in products[:top_n_per_category]
        ]

    return result


def get_user_recommendations(
    user_id: str,
    limit: int = 10
) -> List[str]:
    scores = {}

    # Track whether user has any strong interaction
    has_any_strong_event = False

    # Track strong-view products
    strong_products = set()

    cursor = product_view_events.find({
        "user_id": user_id.lower()
    })

    for doc in cursor:
        pid = doc.get("product_id")
        event_type = doc.get("event_type")
        ts = doc.get("timestamp")

        if not pid or not event_type or not ts:
            continue

        # Track event presence
        if event_type in ("view", "search_view","similar_view"):
            has_any_strong_event = True
            strong_products.add(pid)

        # Scoring (always include all events)
        base_weight = EVENT_WEIGHTS.get(event_type)
        if not base_weight:
            continue

        score = base_weight * _time_decay(ts)
        scores[pid] = scores.get(pid, 0.0) + score

    if not scores:
        return []

    # ✅ DISPLAY RULE
    if has_any_strong_event:
        # Show only strongly interacted products
        visible_scores = {
            pid: score
            for pid, score in scores.items()
            if pid in strong_products
        }

    if not visible_scores:
        return []

    ranked = sorted(
        visible_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return [pid for pid, _ in ranked[:limit]]