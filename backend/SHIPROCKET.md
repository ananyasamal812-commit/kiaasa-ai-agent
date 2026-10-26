# Shiprocket tracking

Track My Order accepts the website order number, or `AWB <tracking-number>`.
It uses Shiprocket's read-only tracking API. Status, available courier/ETA,
recent events and a tracking link are displayed. Customer names, addresses and
contact information are not returned to the browser.

Configure `SHIPROCKET_EMAIL` and `SHIPROCKET_PASSWORD` in `backend/.env` using
Shiprocket **API-user** credentials. Alternatively set `SHIPROCKET_TOKEN` to a
valid bearer token. If store order numbers overlap across channels, set
`SHIPROCKET_CHANNEL_ID` to Kiaasa's channel ID. Do not commit or share secrets.

Credentials are read server-side. Login tokens are cached only in memory;
expired authentication is retried once when email/password are configured.
No orders, shipments, courier assignments or payments are created or changed.

From `backend`, run offline checks with:
`venv\Scripts\python.exe -m unittest test_shiprocket.py`

Live validation requires valid API-user credentials and a known order or AWB.
Official documentation: https://apidocs.shiprocket.in/
