import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from catalogue_sync import CatalogueSync

class CatalogueSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
    def report(self, seconds=0, **extra):
        value = {"refreshed_at": datetime.fromtimestamp(__import__('time').time()-seconds, timezone.utc).isoformat(), **extra}
        (self.data/'catalogue-refresh.json').write_text(json.dumps(value))
    def test_missing_and_stale_snapshots_are_due(self):
        sync=CatalogueSync(self.data, interval=100)
        self.assertEqual(sync.seconds_until_due(),0)
        self.report(seconds=200)
        self.assertEqual(sync.seconds_until_due(),0)
    def test_fresh_snapshot_waits_and_cached_import_is_due(self):
        sync=CatalogueSync(self.data, interval=100)
        self.report()
        self.assertGreater(sync.seconds_until_due(),95)
        self.report(live_fetch=False)
        self.assertEqual(sync.seconds_until_due(),0)
    def test_live_fetch_and_new_product_category_readiness(self):
        def refresh(**kwargs):
            self.assertEqual(kwargs,{"use_cache":False})
            (self.data/'products.json').write_text(json.dumps([{"name":"New kurta","category":"Kurta","collections":["festive"]}]))
            self.report(imported_products=1,collection_counts={"festive":1})
        sync=CatalogueSync(self.data,refresh=refresh)
        self.assertTrue(sync.run_once())
        self.assertEqual(sync.status()['collection_counts'],{"festive":1})
    def test_failure_preserves_snapshot_and_records_error(self):
        snapshot=self.data/'products.json';snapshot.write_text('[{"name":"Existing"}]')
        def fail(**kwargs): raise RuntimeError('Website unavailable')
        sync=CatalogueSync(self.data, refresh=fail)
        self.assertFalse(sync.run_once())
        self.assertEqual(json.loads(snapshot.read_text())[0]['name'],'Existing')
        self.assertIn('Website unavailable',sync.status()['last_error'])
        self.assertFalse(sync.status()['running'])
    def test_disabled_and_stopped_workers(self):
        sync=CatalogueSync(self.data,enabled=False)
        sync.start();self.assertIsNone(sync._thread)
        event=threading.Event()
        sync=CatalogueSync(self.data,refresh=lambda **kw:event.set(),interval=100)
        sync.start();self.assertTrue(event.wait(2));sync.stop()
        self.assertFalse(sync._thread.is_alive())
    def test_overlapping_refresh_is_skipped(self):
        sync=CatalogueSync(self.data)
        sync._lock.acquire()
        try:self.assertFalse(sync.run_once())
        finally:sync._lock.release()

if __name__=='__main__': unittest.main()
