from utils.intent import detect_intent
from utils.search_helpers import extract_keywords, detect_price
from collections import defaultdict

TOP_K = 25
SIMILARITY_THRESHOLD = 0.75
DEBUG_RETRIEVER = True


def dbg(msg: str):
    if DEBUG_RETRIEVER:
        print(msg)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def extract_product_mentions(query: str, title_index: dict) -> list:
    """
    Explicit product grounding via exact title match.
    This is authoritative.
    """
    q = query.lower()
    matched = []

    for title, pid in title_index.items():
        if title in q:
            matched.append(pid)
            dbg(f"[TITLE MATCH] '{title}' → PID={pid}")

    return list(set(matched))


def satisfies_price(meta: dict, price_intent: dict) -> bool:
    price = meta.get("price")
    if not isinstance(price, (int, float)):
        return False

    t = price_intent["type"]
    if t == "max":
        return price <= price_intent["value"]
    if t == "min":
        return price >= price_intent["value"]
    if t == "range":
        return price_intent["min"] <= price <= price_intent["max"]

    return True


def is_ungrounded_reference(query: str) -> bool:
    """
    Queries that reference a product without grounding it.
    Must be blocked.
    """
    q = query.lower()
    return any(
        phrase in q
        for phrase in [
            "this product",
            "that product",
            "the product",
            "above product",
            "this item",
            "that item",
        ]
    )


def is_attribute_comparison(intent: str, explicit_pids: list, mentioned_brands: set) -> bool:
    """
    Attribute/type comparison:
    - intent == compare
    - no explicit product
    - no brand grounding
    """
    return intent == "compare" and not explicit_pids and not mentioned_brands


# =========================================================
# MAIN RETRIEVER
# =========================================================
def retrieve_for_rag(
    query: str,
    embedding_model,
    chroma_collection,
    products_collection,
    brand_index: set,
    title_index: dict,
    max_context: int = 6,
):
    dbg("\n=========== RAG RETRIEVER DEBUG ===========")
    dbg(f"QUERY: {query}")

    intent = detect_intent(query)
    query_lower = query.lower()
    keywords = extract_keywords(query)
    price_intent = detect_price(query_lower)

    dbg(f"Intent: {intent}")
    dbg(f"Keywords: {keywords}")
    dbg(f"Price intent: {price_intent}")

    # ------------------------------------------------
    # 🚨 Block ungrounded references
    # ------------------------------------------------
    explicit_pids = extract_product_mentions(query, title_index)
    if is_ungrounded_reference(query) and not explicit_pids:
        dbg("[ABORT] Ungrounded product reference")
        return None

    # ------------------------------------------------
    # 1️⃣ Explicit product resolution (authoritative)
    # ------------------------------------------------
    explicit_products = []
    if explicit_pids:
        explicit_products = list(
            products_collection.find(
                {"pid": {"$in": explicit_pids}},
                {"_id": 0},
            )
        )

        if len(explicit_products) < len(explicit_pids):
            dbg("[ABORT] Explicit product mentioned but missing in catalog")
            return None

    explicit_brands = {
        p.get("brand", "").lower()
        for p in explicit_products
        if p.get("brand")
    }

    # ------------------------------------------------
    # 2️⃣ Semantic recall
    # ------------------------------------------------
    query_embedding = embedding_model.encode(
        query,
        normalize_embeddings=True
    ).tolist()

    recall = chroma_collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K,
        include=["metadatas", "distances"],
    )

    metas = recall.get("metadatas", [[]])[0]
    dists = recall.get("distances", [[]])[0]

    dbg(f"Semantic recall candidates: {len(metas)}")

    if not metas:
        return explicit_products or None

    # ------------------------------------------------
    # ✅ Similarity guard (ONLY for ambiguous reference)
    # ------------------------------------------------
    if not explicit_pids and intent not in {
        "recommend", "recommend_category", "qa", "explain", "alternative", "compare"
    }:
        max_sim = max(1 - d for d in dists)
        dbg(f"Max semantic similarity: {max_sim:.3f}")

        if max_sim < SIMILARITY_THRESHOLD:
            dbg("[ABORT] Similarity below threshold (ambiguous reference)")
            return None
    else:
        dbg("Similarity guard skipped (explicit or discovery intent)")

    # ------------------------------------------------
    # 3️⃣ Simple scoring (no term weights)
    # ------------------------------------------------
    scored = []
    for idx, meta in enumerate(metas):
        score = 1
        reasons = []
        brand = (meta.get("brand") or "").lower()

        if brand and brand in query_lower and intent != "alternative":
            score += 3
            reasons.append("brand_match")

        for kw in keywords:
            for lvl in ["category_l1", "category_l2", "category_l3"]:
                if meta.get(lvl) and kw in meta[lvl].lower():
                    score += 1
                    reasons.append(f"category_match:{kw}")
                    break
        
        for kw in keywords:
            for spec in meta.get("specifications", []):
                if kw in spec.lower():
                    score += 1
                    reasons.append(f"spec_match:{kw}")
                    break

        scored.append({
            "meta": meta,
            "score": score,
            "rank": idx,
            "reasons": reasons,
        })

        dbg(f"PID={meta.get('pid')} | SCORE={score} | REASONS={reasons}")

    scored.sort(key=lambda x: (-x["score"], x["rank"]))

    # ------------------------------------------------
    # 4️⃣ Hard filtering (price)
    # ------------------------------------------------
    filtered = []
    for item in scored:
        meta = item["meta"]
        if price_intent and not explicit_pids:
            if not satisfies_price(meta, price_intent):
                dbg(f"[FILTERED] PID={meta.get('pid')} ❌ price")
                continue
        filtered.append(item)

    if not filtered:
        dbg("[ABORT] All candidates filtered")
        return None

    # =================================================
    # 5️⃣ INTENT‑AWARE SELECTION
    # =================================================
    selected = []
    seen_pids = set()
    seen_titles = set()

    # ✅ Explicit products always first
    for p in explicit_products:
        selected.append(p)
        seen_pids.add(p["pid"])
        seen_titles.add(p.get("title", "").lower())
        dbg(f"[SELECTED] Explicit → {p.get('title')}")

    # ------------------------------------------------
    # ✅ A. COMPARISON
    # ------------------------------------------------
    if intent == "compare":
        mentioned_brands = {
            b.lower()
            for b in brand_index
            if b.lower() in query_lower and len(b) >= 2
        }

        dbg(f"Compared brands detected: {mentioned_brands}")

        # ✅ ATTRIBUTE LEVEL COMPARISON
        if is_attribute_comparison(intent, explicit_pids, mentioned_brands):
            dbg("Attribute-level comparison detected")

            for item in filtered:
                meta = item["meta"]
                pid = meta["pid"]
                title = meta.get("title", "").lower()

                if pid in seen_pids or title in seen_titles:
                    continue

                selected.append(meta)
                seen_pids.add(pid)
                seen_titles.add(title)

                if len(selected) >= min(4, max_context):
                    break

            return selected

        # ✅ BRAND / PRODUCT COMPARISON
        if not mentioned_brands:
            dbg("Brand fallback: infer brands from results")
            mentioned_brands = {
                (m.get("brand") or "").lower()
                for m in metas if m.get("brand")
            }

        brand_buckets = defaultdict(list)
        for item in filtered:
            brand = (item["meta"].get("brand") or "").lower()
            if brand in mentioned_brands:
                brand_buckets[brand].append(item)

        # Round-robin brand coverage
        while len(selected) < max_context:
            progress = False
            for brand, items in brand_buckets.items():
                for item in items:
                    meta = item["meta"]
                    pid = meta["pid"]
                    title = meta.get("title", "").lower()

                    if pid in seen_pids or title in seen_titles:
                        continue

                    selected.append(meta)
                    seen_pids.add(pid)
                    seen_titles.add(title)
                    dbg(f"[SELECTED] Compare[{brand}] → {meta.get('title')}")
                    progress = True
                    break

                if len(selected) >= max_context:
                    break

            if not progress:
                break

    # ------------------------------------------------
    # ✅ B. ALTERNATIVES
    # ------------------------------------------------
    elif intent == "alternative":
        brand_count = defaultdict(int)

        for item in filtered:
            meta = item["meta"]
            brand = (meta.get("brand") or "").lower()
            pid = meta["pid"]
            title = meta.get("title", "").lower()

            if explicit_brands and brand in explicit_brands:
                continue
            if brand_count[brand] >= 1:
                continue
            if pid in seen_pids or title in seen_titles:
                continue

            selected.append(meta)
            seen_pids.add(pid)
            seen_titles.add(title)
            brand_count[brand] += 1
            dbg(f"[SELECTED] Alternative → {meta.get('title')}")

            if len(selected) >= max_context:
                break

    # ------------------------------------------------
    # ✅ C. DEFAULT (recommend / explain / qa)
    # ------------------------------------------------
    else:
        for item in filtered:
            meta = item["meta"]
            pid = meta["pid"]
            title = meta.get("title", "").lower()

            if pid in seen_pids or title in seen_titles:
                continue

            selected.append(meta)
            seen_pids.add(pid)
            seen_titles.add(title)
            dbg(f"[SELECTED] Semantic → {meta.get('title')}")

            if len(selected) >= max_context:
                break

    dbg("\nFINAL CONTEXT:")
    for p in selected:
        dbg(f" - {p.get('title')}")

    dbg("=========== END RETRIEVER DEBUG ===========\n")

    return selected[:max_context]