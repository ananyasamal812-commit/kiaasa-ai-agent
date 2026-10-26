"""Deterministic collection browsing for the shopping menu."""

COLLECTION_MESSAGES = {
    "show me new arrivals": "new_arrivals", "new arrivals": "new_arrivals", "new arrival": "new_arrivals",
    "help me find festive wear": "festive", "festive wear": "festive",
    "help me find everyday styles": "everyday", "everyday styles": "everyday", "everyday style": "everyday", "daily wear kurta": "everyday",
}
COLLECTION_INTROS = {
    "new_arrivals": "Explore the newest season listed in Kiaasa's current catalogue. Tell me your preferred colour or budget to narrow the collection down.",
    "festive": "Explore Kiaasa's festive and occasion wear, including suit sets and kurtas. Tell me your preferred colour or budget to narrow them down.",
    "everyday": "Explore Kiaasa's casual and everyday styles. Tell me your preferred colour or budget to narrow them down.",
}


def collection_for_message(message, action=None):
    if action in COLLECTION_INTROS:
        return action
    return COLLECTION_MESSAGES.get(message.lower().strip().rstrip(".!?"))


def browse_collection(products, collection, limit=None):
    eligible = [p for p in products
                if "girl" not in p.get("name", "").lower()
                and "kids" not in str(p.get("category", "")).lower()
                and str(p.get("stock", "")).lower().strip() not in {"out of stock", "sold out", "unavailable"}
                and collection in p.get("collections", [])]
    eligible.sort(key=lambda p: p.get("latest_collection_rank", 10000))
    matches = eligible if limit is None else eligible[:limit]
    return {"reply": (COLLECTION_INTROS[collection] + f" {len(eligible)} styles found. Check the product page for current price and store availability.") if matches else "This collection currently has no available products in the catalogue.",
            "intent": "collection", "collection": collection, "products": matches, "matches": len(matches)}
