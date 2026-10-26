"""Non-blocking, periodic refresh of the public catalogue snapshot."""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from refresh_catalogue import main as import_catalogue

log = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent / 'data'


class CatalogueSync:
    def __init__(self, data_dir=DATA_DIR, refresh=import_catalogue, interval=None, enabled=None):
        self.data_dir = Path(data_dir)
        self.refresh = refresh
        if interval is None:
            try:
                interval = max(300, float(os.getenv('CATALOGUE_SYNC_INTERVAL_SECONDS', '21600')))
            except ValueError:
                interval = 21600
        self.interval = interval
        self.enabled = (os.getenv('CATALOGUE_AUTO_SYNC', 'true').lower() not in {'0', 'false', 'no'}) if enabled is None else enabled
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._last_attempt = None
        self._last_error = None
        self._running = False

    def report(self):
        try:
            value = json.loads((self.data_dir / 'catalogue-refresh.json').read_text(encoding='utf-8'))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def seconds_until_due(self):
        report = self.report()
        if report.get('live_fetch') is False:
            return 0
        try:
            last = datetime.fromisoformat(report['refreshed_at']).timestamp()
            return max(0, min(self.interval, last + self.interval - time.time()))
        except (KeyError, ValueError, TypeError):
            return 0

    def run_once(self):
        if not self._lock.acquire(blocking=False):
            return False
        self._running = True
        self._last_attempt = datetime.now(timezone.utc).isoformat()
        try:
            self.refresh(use_cache=False)
            self._last_error = None
            return True
        except Exception as error:
            self._last_error = str(error)
            log.warning('Catalogue sync failed; serving the previous snapshot: %s', error)
            return False
        finally:
            self._running = False
            self._lock.release()

    def _loop(self):
        delay = self.seconds_until_due()
        while not self._stop.wait(delay):
            self.run_once()
            delay = self.interval

    def start(self):
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name='kiaasa-catalogue-sync', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def status(self):
        report = self.report()
        return {
            'enabled': self.enabled,
            'running': self._running,
            'interval_seconds': self.interval,
            'last_attempt_at': self._last_attempt,
            'last_success_at': report.get('refreshed_at'),
            'last_error': self._last_error,
            'source': report.get('source', 'https://www.kiaasa.in/sitemap/products.xml'),
            'products': report.get('imported_products'),
            'collection_counts': report.get('collection_counts', {}),
            'new_arrivals_rule': report.get('new_arrivals_rule'),
        }


catalogue_sync = CatalogueSync()
