# Security and supported deployment

Never commit backend/.env, production.env, API keys, shipping credentials, customer records, runtime databases or full cached storefront pages. The repository and Docker context exclude these by default. GitHub Actions also checks tracked filenames and common credential patterns. Rotate exposed credentials; deleting them from the latest commit is not enough after publication.

Production must set APP_ENV=production, explicit ALLOWED_HOSTS and ALLOWED_ORIGINS, and a strong SESSION_SECRET. TRACKING_REQUIRE_VERIFICATION must stay true. Never share TRACKING_VERIFICATION_SECRET with browsers or use a session token as proof of customer/order ownership.

Request throttling is per client IP and persists in SQLite. The supplied proxy is the sole public entrypoint. Trust forwarded client addresses only from your own proxy; the container command trusts proxy headers because its app port is private on the Compose network. If publishing the app port directly, remove that trust configuration and configure allowed proxy IPs explicitly.

The client-side assistant cart contains no payment credentials and is not an authoritative order. Catalogue-derived values are not proof of price/stock. The merchant server must revalidate before a real checkout mutation.

Report vulnerabilities privately to the repository owner or designated tech-team security contact. Do not publish secrets, real AWBs, customer addresses or exploit details in public issues. The business must name a security contact and approve legal/privacy wording before launch.
