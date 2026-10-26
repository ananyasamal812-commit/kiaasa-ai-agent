"""Order tracking conversation, handled before shopping or Gemini."""
import re
from shiprocket_client import shiprocket, ShiprocketError
from production import tracking_allowed

tracking_sessions = {}
TRACKING_INTENT = re.compile(
    r"\b(?:track(?:ing)?\s+(?:(?:my|an|the|a)\s+)?order|order\s+(?:tracking|status|id|number)|where\s+is\s+my\s+order|(?:track|locate)\s+(?:my\s+)?(?:delivery|package|shipment)|awb|tracking\s+(?:id|number))\b",
    re.I,
)
SHOPPING_INTENT = re.compile(
    r"\b(?:shop|shopping|kurtas?|kurtis?|outfits?|dress(?:es)?|festive|arrivals?|styles?|recommend|browse|buy)\b", re.I
)


def tracking_reply(reply, **extra):
    return {"reply": reply, "intent": "order_tracking", "products": [], "matches": 0, **extra}


def extract_order_id(message):
    # Accept common numeric and prefixed references, including #12345 and KIA-12345.
    labelled = re.search(
        r"\b(?:order\s*(?:id|number|no\.?)|order)\s*(?:is|:|=)?\s*#?([A-Za-z0-9][A-Za-z0-9_-]{2,39})\b",
        message, re.I,
    )
    candidate = labelled.group(1) if labelled else message.strip().lstrip("#").strip()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,39}", candidate) and re.search(r"\d", candidate):
        return candidate
    return None


def handle_order_tracking(session_id, message, verification_token=None):
    """Return None for shopping, or a deterministic order-only response."""
    active = session_id in tracking_sessions
    text = message.strip()
    if active and text.lower() in {"cancel", "stop", "back", "back to shopping", "never mind", "nevermind"}:
        tracking_sessions.pop(session_id, None)
        return tracking_reply("Order tracking cancelled. What would you like to shop for?", tracking_state="cancelled")
    is_tracking = bool(TRACKING_INTENT.search(text) or re.search(r"\border\s*#?(?:[A-Za-z]{1,10}-?)?\d{3,}\b",text,re.I))
    if active and not is_tracking and SHOPPING_INTENT.search(text):
        tracking_sessions.pop(session_id, None)
        return None
    if not active and not is_tracking:
        return None
    awb_match = re.search(r"\b(?:awb|tracking\s+(?:id|number))\s*(?:is|:|=)?\s*#?([A-Za-z0-9][A-Za-z0-9_-]{2,39})\b", text, re.I)
    order_id = awb_match.group(1) if awb_match else extract_order_id(text)
    kind = "awb" if awb_match else "order"
    if order_id is None:
        tracking_sessions[session_id] = "awaiting_order_id"
        return tracking_reply(
            "Sure! Enter your order number from your confirmation email (for example, #12345), or type AWB followed by your courier tracking number. Type cancel to return to shopping.",
            tracking_state="awaiting_order_id",
        )
    if not tracking_allowed(order_id,kind,session_id,verification_token):
        tracking_sessions.pop(session_id,None)
        return tracking_reply("For your privacy, verify your order through Kiaasa's customer support before viewing shipment details here. You can also use the tracking link in your confirmation email.",
            tracking_state="verification_required",links=[{"label":"Kiaasa customer support","url":"https://www.kiaasa.in/contact-us"}])
    try:
        shipments = shiprocket.track(order_id, kind=kind)
    except ShiprocketError as error:
        tracking_sessions[session_id] = "awaiting_order_id"
        if error.code in {"not_found", "invalid_reference"}:
            reply = "I couldn't find shipment updates for that reference. Check your order number, or type AWB followed by the courier tracking number. A new order may not have shipment updates yet."
            state = "not_found"
        elif error.code == "rate_limited":
            reply = "The tracking service is busy. Please try again in a little while."
            state = "unavailable"
        else:
            reply = "Live tracking is temporarily unavailable. Please try again later or use the tracking link in your confirmation email."
            state = "unavailable"
        return tracking_reply(reply, tracking_state=state)
    tracking_sessions.pop(session_id, None)
    return tracking_reply(
        f"Here are the latest shipment updates for your {'AWB' if kind == 'awb' else 'order'} {order_id}.",
        tracking_state="found", tracking=shipments,
    )
