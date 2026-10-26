# Kiaasa Shopping Assistant

A catalogue-grounded shopping widget with product cards, an assistant selection cart, store finder, Groq/OpenAI language interpretation, and guarded Shiprocket tracking.

## Local setup (Windows / PowerShell)

Use Python 3.12 or newer and Node.js 20+ for the frontend checks.

```powershell
python -m venv backend/venv
.\backend\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item backend/.env.example backend/.env
```

Set GROQ_API_KEY in backend/.env, then run the complete app on one origin:

```powershell
.\backend\venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Open http://127.0.0.1:8000 . API routes are under /api. No API key is required for the catalogue, menus, local search, cart or stores. Without a working LLM key the assistant uses local shopping logic. Never commit .env or use provider keys in frontend code.

The older two-terminal setup still works with backend/main:app on port 8000 and the frontend static server on port 5500.

## Verification

```powershell
.\backend\venv\Scripts\python.exe -m unittest discover -s backend -p "test_*.py"
node frontend/tests/cart.test.cjs
node --check frontend/script.js
node --check frontend/cart.js
```

Tests cover shopping constraints, separate sessions, provider failures, cart state, tracking response privacy, production session proofs, request limits, persistence, expiry, oversized requests and catalogue source restrictions. External provider responses are mocked in automated tests; live account access is a separate deployment verification.

## Tech-team integration

Read [INTEGRATION.md](INTEGRATION.md) for endpoint examples and merchant-side work. Read [DEPLOYMENT.md](DEPLOYMENT.md) for Docker/HTTPS and operational checks. See [SECURITY.md](SECURITY.md) for configuration and reporting.

The frontend can be hosted under a same-origin path such as /assistant/ with its /assistant/api/ requests reverse-proxied to this app's /api/. For a separate origin, explicitly allow the website origin using ALLOWED_ORIGINS. Do not use wildcard credentialed CORS.

## Current capability and boundaries

- Live public catalogue sync every six hours while the persistent backend is running. It validates the source and atomically updates the last good snapshot. Published categories and attributes determine recommendations.
- Prices, images and variants come from the public catalogue. Public pages do not provide reliable store-level inventory. Product-page checkout remains authoritative.
- New Arrivals uses the newest published season, not an invented launch timestamp. Festive and Everyday use source labels/descriptions. Reviewed colour discrepancies survive syncs.
- Groq is the default provider; OpenAI remains selectable with LLM_PROVIDER. Missing keys, limits and failures use local shopping logic. Tracking records are not sent to the shopping model.
- The assistant cart is browser-local. It is **not the native Kiaasa website cart**. The team must connect its authenticated cart API before claiming direct add-to-cart or checkout.
- Production tracking is **blocked without a merchant-issued ownership proof**. The team must verify the logged-in customer or OTP through its own order system. No public endpoint mints these proofs.
- SQLite preserves shopping state for 45 minutes of inactivity. Use one application worker/instance with the supplied persistent volume. Multi-replica deployment needs a shared database and distributed request/session locks.

## Before public launch

The team must supply domain/server access, production secrets, real cart integration, order ownership verification and shipping credentials; approve the privacy notice and confirm stock/price behavior. Test real shipments and native checkout in staging. This repository does not claim those external integrations are complete.

Do not deploy this as a stateless serverless demo and assume the background sync or SQLite state will persist. Use the persistent-server package, or move sync to a scheduler and state to managed storage first.
