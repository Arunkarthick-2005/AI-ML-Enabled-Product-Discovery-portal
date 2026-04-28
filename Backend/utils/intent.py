
def detect_intent(query: str) -> str:
    q = query.lower()

    if "compare" in q or "vs" in q:
        return "compare"

    if "alternative" in q or "similar" in q:
        return "alternative"

    if "category" in q or "which category" in q:
        return "recommend_category"

    if "recommend" in q or "suggest" in q:
        return "recommend"

    if "explain" in q or "what is" in q:
        return "explain"

    return "qa"