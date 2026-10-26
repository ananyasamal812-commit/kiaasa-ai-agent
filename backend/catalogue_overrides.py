"""Reviewed source-data discrepancies kept separate from automatic imports."""
import json
from pathlib import Path
from urllib.parse import urlsplit

OVERRIDES_FILE = Path(__file__).resolve().parent / 'data/catalogue-overrides.json'

def product_key(url):
    parsed=urlsplit(str(url))
    return (parsed.hostname or '').lower().removeprefix('www.') + parsed.path.rstrip('/')

def apply_catalogue_overrides(products):
    try:
        overrides=json.loads(OVERRIDES_FILE.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return products
    # Malformed review data must not silently re-enable disputed colour matches.
    indexed={product_key(url):value for url,value in overrides.items()}
    return [{**product, **indexed.get(product_key(product.get('url','')), {})} for product in products]
