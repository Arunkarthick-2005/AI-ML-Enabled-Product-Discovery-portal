from datetime import datetime, timezone
from typing import Dict, List, Tuple
import math
from collections import defaultdict

# ✅ IMPORT EXISTING COLLECTION
from database import product_view_events,products_collection

# =================================================
# CONFIGURATION
# =================================================

EVENT_WEIGHTS = {
    "view": 1.0,               # normal product view
    "search_view": 2.5,        # strong intent
    "search_impression": 0.3   # weak signal
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


def _compute_scores(cursor) -> Dict[str, float]:
    scores: Dict[str, float] = {}

    for doc in cursor:
        product_id = doc.get("product_id")
        event_type = doc.get("event_type")
        timestamp = doc.get("timestamp")

        if not product_id or not event_type or not timestamp:
            continue

        base_weight = EVENT_WEIGHTS.get(event_type)
        if not base_weight:
            continue

        score = base_weight * _time_decay(timestamp)
        scores[product_id] = scores.get(product_id, 0.0) + score

    return scores
def extract_category(product: dict) -> str | None:
    """
    Returns the most specific available category.
    Priority: level_3 > level_2 > level_1
    """
    category = product.get("category") or {}

    return (
        category.get("level_3")
        or category.get("level_2")
        or category.get("level_1")
    )

def get_trending_categories(
    top_k_categories: int = 5,
    category_level: str = "category_l2"
):
    print("🟡 STEP 0: ENTER get_trending_categories")

    from collections import defaultdict
    product_scores = defaultdict(float)
    has_strong_event = defaultdict(bool)

    cursor = list(product_view_events.find({}))
    print(f"🟡 STEP 1: total events found = {len(cursor)}")

    for doc in cursor:
        pid = doc.get("product_id")
        event_type = doc.get("event_type")
        ts = doc.get("timestamp")

        print(f"  ▶ EVENT: pid={pid}, type={event_type}")

        if not pid or not event_type or not ts:
            continue

        if event_type in ("view", "search_view"):
            has_strong_event[pid] = True

        weight = EVENT_WEIGHTS.get(event_type, 0)
        score = weight * _time_decay(ts)
        product_scores[pid] += score

    print(f"🟡 STEP 2: product_scores = {dict(product_scores)}")
    print(f"🟡 STEP 2: has_strong_event = {dict(has_strong_event)}")

    if not product_scores:
        print("🔴 EXIT: No product scores")
        return {}

    any_strong_exists = any(has_strong_event.values())
    print(f"🟡 STEP 3: any_strong_exists = {any_strong_exists}")

    if any_strong_exists:
        visible_products = {
            pid: score
            for pid, score in product_scores.items()
            if has_strong_event.get(pid)
        }
    else:
        visible_products = product_scores

    print(f"🟡 STEP 4: visible_products = {visible_products}")

    if not visible_products:
        print("🔴 EXIT: visible_products empty")
        return {}

    product_docs = list(
        products_collection.find(
            {"pid": {"$in": list(visible_products.keys())}},
            {"pid": 1, "category": 1}
        )
    )

    print(f"🟡 STEP 5: product_docs = {len(product_docs)}")

    category_top_product = {}

    for p in product_docs:
        pid = p.get("pid")
        category_obj = p.get("category") or {}

        category = (
            category_obj.get("level_3")
            or category_obj.get("level_2")
            or category_obj.get("level_1")
        )

        print(f"  ▶ PRODUCT: pid={pid}, category={category}")

        if not category:
            continue

        score = visible_products.get(pid, 0)

        if (
            category not in category_top_product
            or score > category_top_product[category][1]
        ):
            category_top_product[category] = (pid, score)

    print(f"🟡 STEP 6: category_top_product = {category_top_product}")

    if not category_top_product:
        print("🔴 EXIT: No category mapping")
        return {}

    ranked = sorted(
        category_top_product.items(),
        key=lambda x: x[1][1],
        reverse=True
    )

    print(f"🟢 STEP 7: ranked categories = {ranked}")

    result = {
        category: [pid]
        for category, (pid, _) in ranked[:top_k_categories]
    }

    print(f"✅ FINAL RESULT = {result}")
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

    # Track impression-only products
    impression_products = set()

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
        if event_type in ("view", "search_view"):
            has_any_strong_event = True
            strong_products.add(pid)
        elif event_type == "search_impression":
            impression_products.add(pid)

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
    else:
        # No views yet → show impression products
        visible_scores = {
            pid: score
            for pid, score in scores.items()
            if pid in impression_products
        }

    if not visible_scores:
        return []

    ranked = sorted(
        visible_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return [pid for pid, _ in ranked[:limit]]