# Deployment and operations

## Persistent Docker server

1. Supply a Linux server with Docker Compose, a real domain pointing to it and ports 80/443 available. No cloud resources are created by this repository.
2. Copy production.env.example to production.env. Set SITE_DOMAIN, explicit ALLOWED_HOSTS/ALLOWED_ORIGINS, a strong SESSION_SECRET, provider keys and merchant tracking-verification credentials. Generate secrets with python -c "import secrets; print(secrets.token_urlsafe(48))". Keep them in the server's secret store. Placeholder secrets are not suitable for deployment.
3. Run docker compose --env-file production.env up -d --build . Caddy obtains and renews HTTPS certificates for a valid configured domain. The backend is not published directly.
4. Verify https://your-domain/api/health/ready, chat session creation, collections, cart UI and privacy link. Verify session/verification enforcement and provider fallback in staging.

The catalogue volume is seeded from the container's backend/data directory on first use. It also holds the SQLite session/rate-limit database. Rebuilding an image does not overwrite the named volume. Apply reviewed catalogue-overrides.json changes to that volume explicitly on later releases. Backup before migration. Keep one worker/replica; shared multi-node persistence is not implemented.

## Release / rollback

Run tests, build the image, tag with the Git commit and deploy in staging first. Deploy the tested immutable tag. Preserve production.env, the catalogue volume, and Caddy certificate volumes. Roll back to the previous image tag if needed; do not delete volumes. No destructive database migrations are included.

## Backups and retention

Back up the catalogue/review metadata and SQLite database using SQLite's backup API while the service is running, or stop the app briefly before copying database/WAL files together. Do not copy only the main DB during writes. Encrypt backups, limit access, test restore, and choose a retention policy approved by the business. Session rows expire after 45 minutes idle and are removed on subsequent state access; monitoring, backups and infrastructure logs require their own retention policy.

## Monitoring

Poll readiness; alert if it fails. Monitor 5xx, 429 rates, request durations, provider fallbacks and catalogue/status staleness. Request logs contain correlation IDs/status/timing, not chat text or tracking references. Docker restart policies restart crashed processes, but healthcheck failures alone do not restart a running container; connect your host monitoring/orchestrator to alert and recover.

## Staging acceptance

- Real API key: English/Hinglish request, quota/timeout fallback, repeated-request throttling.
- Exact budget/colour/size/fabric filters; no invented products or stock; reviewed-colour exclusion.
- Catalogue sync success/failure/restart, newly published products, preserved source-review overrides.
- Session state survives app restart; cross-session token denied; expiry/delete works.
- Unauthorized tracking denied; merchant ownership verification accepted; real shipment errors and updates.
- Native merchant cart and checkout tested only after the team implements the contract; local assistant cart must remain clearly labelled meanwhile.
- Desktop and mobile browsers, keyboard navigation, screen reader labels, slow/offline network, empty image/size/stock cases.
- Privacy notice approved, secret scanning passed, backups restored, HTTPS/domain and monitoring verified.

Do not mark the public launch complete before merchant cart/auth, real shipment and real inventory checks are signed off by the website team.
