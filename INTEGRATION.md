# Kiaasa tech-team handoff

## Embed and route

Recommended: host the standalone frontend at /assistant/ on the merchant origin and reverse proxy /assistant/api/ to the app's /api/. Relative assets and API URLs support a path prefix. An iframe may use that route and must be allowed by your site's frame policy. For a separate origin configure ALLOWED_ORIGINS and ALLOWED_HOSTS explicitly. The supplied Caddy configuration allows only same-origin framing; update frame-ancestors to the exact merchant host if needed.

The current UI is a standalone page, not a drop-in script that can safely overwrite the merchant page's global CSS. Use an isolated iframe or refactor to a shadow-root component before direct DOM embedding.

## Session and chat

1. POST /api/session returns session_id and session_token. The token is an unguessable signed session capability, not customer-account authentication. Keep it in page memory. It expires after 24 hours; conversation data expires after 45 minutes idle.
2. POST /api/chat with X-Session-Token and JSON {"session_id":"...","message":"festive under 2000","action":null}. Optional actions: new_arrivals, festive, everyday, reset.
3. Responses include reply, products, intent and profile. Product facts are selected server-side; render text with textContent rather than HTML injection. language_model reports groq/openai/local for interpreted shopping requests.
4. DELETE /api/chat/{session_id}, with its matching X-Session-Token, clears persisted shopping state.
5. Handle 401 by starting a new session, 413/422 by correcting input, 429 by waiting at least Retry-After, and 5xx with a retry message. Do not automatically replay mutations into the merchant cart.

## Native merchant cart (integration required)

The existing Add to Cart icon saves a browser-local selection. frontend/cart.js contains attachControls and the current CartStore. Replace the add handler only after wiring the merchant's supported cart API.

Resolve the catalogue URL and selected size to the merchant's real product/variant/store IDs on the merchant server. Use the customer's authenticated or guest website session. Recheck price, size and stock before mutation. Return the real cart ID and item count only on success. Use an idempotency key to prevent duplicate adds on timeout/retry. Show sold-out/authentication/price-change errors. Never accept price from the widget as authoritative or place merchant credentials in JS.

Required merchant contract: resolveProduct(productUrl,size), addItem(variantId,quantity,customerSession,idempotencyKey), getCart(customerSession), updateQuantity and removeItem. No compatible public cart contract or admin permission was supplied, so no private cart endpoint is reverse-engineered or falsely advertised here.

## Verified order tracking (integration required)

Production rejects unverified reference lookups. First verify that the logged-in customer owns the reference using the merchant order database, or issue an OTP to the contact already on the order. Rate-limit verification, use generic error messages and avoid revealing whether an order exists.

After verification the merchant backend signs a short-lived proof (recommended 5 minutes):

```json
{"sid":"assistant-session-id","reference":"123456","kind":"order","exp":1790000000}
```

Exact token format: base64url(UTF-8 compact JSON), without padding, followed by a dot and lowercase hex HMAC-SHA256 of "tracking." + that base64url body. Key: TRACKING_VERIFICATION_SECRET, shared only by trusted servers. The Python reference implementation is production.sign_token(payload,"tracking"). Include only the exact verified reference and session; never wildcard claims. Use a fresh expiry timestamp, not the example number above.

POST /api/chat with tracking_token plus the tracking message. For GET /api/tracking/{awb}, use X-Session-Token and X-Tracking-Token; the proof must use kind=awb and that exact AWB. This differs from an order proof. The existing auto-refresh UI will not bypass missing verification: add the verified AWB token to its request headers through your customer-auth integration before enabling it in production. Tracking proofs and records must never be passed to the shopping LLM or logged.

## Operations and acceptance

- GET /api/health/live: process liveness.
- GET /api/health/ready: catalogue loaded; this is not a claim that merchant cart/auth are integrated.
- GET /api/catalogue/status: last sync, counts, source and failures. Alert on last_error or a last_success_at more than 48 hours old.
- GET /api/llm/status: configured provider/model; configuration alone does not prove live account connectivity.
- Run the test suite and staging acceptance checks in DEPLOYMENT.md before release.
