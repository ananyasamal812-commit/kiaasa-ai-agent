# Automatic catalogue updates

Start the backend normally. A background worker checks the last successful refresh and fetches the public Kiaasa sitemap and product pages if the snapshot is older than six hours. It repeats every six hours while the backend runs. A fresh saved snapshot delays the first fetch until it is due. No API key is required.

The assistant keeps answering from the previous catalogue during a refresh. A complete, validated import atomically replaces products.json; subsequent chat requests pick it up without restarting. A failed import preserves the existing catalogue and retries at the next interval. The worker starts again after backend restarts. Keep one Uvicorn worker for this local app.

The importer preserves published product categories, photos, prices, fabrics and sizes. Festive and everyday groups follow published occasion/category/title labels, falling back to descriptions. New Arrivals contains the newest published season, rather than treating sitemap order as a launch date. Store-specific stock is not exposed by this public source; the assistant does not invent it.

Configuration in backend/.env:

```
CATALOGUE_AUTO_SYNC=true
CATALOGUE_SYNC_INTERVAL_SECONDS=21600
```

The minimum configurable interval is five minutes. Set CATALOGUE_AUTO_SYNC=false to disable automatic updates. This only runs while the backend is running.

Read http://127.0.0.1:8000/catalogue/status for the last successful sync, current sync state, errors, and collection counts. A refresh can take several minutes because it fetches all public product pages.

Force a live refresh from the project root:

```
.\backend\venv\Scripts\python.exe backend/refresh_catalogue.py
```

The --cached option is for offline development only; automatic syncing always uses the live website.
