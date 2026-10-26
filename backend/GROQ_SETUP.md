# Groq setup

Create a Groq account and API key at https://console.groq.com/keys . Keep the account on its Free tier if you want to stay within free-tier limits. Model access and rate limits depend on your account; the project does not upgrade your plan or add a payment method.

Set these in backend/.env and restart the backend:

```
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=openai/gpt-oss-20b
GROQ_ENABLED=true
```

The openai/gpt-oss-20b model is hosted by Groq. It uses a Groq key and Groq quota, not an OpenAI API key or OpenAI billing. The existing openai Python SDK connects to the fixed Groq endpoint https://api.groq.com/openai/v1 . No additional SDK is required.

GET /llm/status reports the selected provider, model and whether a key is configured. Configuration does not verify model access or a successful live request. Shopping responses report language_model=groq only after successful interpretation.

Groq interprets the latest shopping message with only the current shopping preferences, pending question and up to five displayed product names/categories. Prices, images, links, filters and product recommendations still come from the synced catalogue. Order tracking, service responses, greetings and collection buttons bypass the LLM.

The response is schema-validated. Missing keys, refusals, incomplete responses, invalid JSON, provider errors, quotas and timeouts all fall back to local shopping logic. Calls time out after 12 seconds, without retries. Provider failures cause a 60-second cooldown, or a longer numeric Retry-After value (capped at 24 hours). No automatic fallback to paid OpenAI calls occurs.

Use LLM_PROVIDER=local to disable hosted models. Use LLM_PROVIDER=openai with your OpenAI settings to switch back explicitly. Never put API keys in frontend files or commit backend/.env.

Official docs:
- https://console.groq.com/docs/structured-outputs
- https://console.groq.com/docs/openai
- https://console.groq.com/docs/rate-limits
