# OpenAI shopping interpretation

Add your own API key to backend/.env (never frontend files):

```
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5-mini
OPENAI_ENABLED=true
```

Install backend dependencies and restart Uvicorn. GET /llm/status reports enabled/configured/model without exposing the key. This endpoint reports configuration, not a successful live provider connection. Set OPENAI_ENABLED=false to disable the integration.

The backend calls the OpenAI Responses API with a Pydantic structured output to interpret natural shopping requests, including Hindi/Hinglish. The current preferences, pending question and up to five displayed product names/categories provide context. No tracking records or credentials are sent. API response storage is disabled with store=False.

Product selection, prices, images, availability and links still come from the synced catalogue and hard filters. Explicit preferences in the original message take priority over the interpretation. Menu clicks, order tracking, policy answers and greetings use existing routes. The LLM never generates product records or shipment statuses.

A missing key, refusal, invalid response, timeout or API failure falls back to the existing local assistant. Requests time out after 12 seconds with no retries, and failures pause OpenAI calls for 60 seconds. Shopping responses include language_model=openai only when a valid interpretation was used.

Example: laal rang ka roz pehenne ke liye 2 hazaar tak -> red everyday wear under 2000.

Official reference: https://developers.openai.com/api/docs/guides/structured-outputs
