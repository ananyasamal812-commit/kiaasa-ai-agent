"""Read-only Shiprocket tracking; credentials and tokens remain server-side."""
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from dotenv import dotenv_values

BASE_URL = 'https://apiv2.shiprocket.in/v1/external/'
ENV_FILE = Path(__file__).with_name('.env')

class ShiprocketError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def configuration():
    local = dotenv_values(ENV_FILE)
    return {key: os.environ.get(key, local.get(key, '')) or '' for key in
            ['SHIPROCKET_EMAIL', 'SHIPROCKET_PASSWORD', 'SHIPROCKET_TOKEN', 'SHIPROCKET_CHANNEL_ID']}

def safe_tracking_url(value):
    try:
        url = urllib.parse.urlsplit(str(value or ''))
        if url.scheme == 'https' and url.hostname in {'app.shiprocket.in', 'shiprocket.in', 'www.shiprocket.in', 'tracking.shiprocket.in'} and not url.username and not url.password:
            return urllib.parse.urlunsplit((url.scheme, url.netloc, url.path, url.query, ''))
    except ValueError:
        pass
    return None

def normalise_tracking(payload):
    shipments, seen = [], set()
    def visit(node, depth=0):
        if depth > 6:
            return
        if isinstance(node, list):
            for entry in node:
                visit(entry, depth + 1)
        elif isinstance(node, dict):
            if isinstance(node.get('tracking_data'), dict):
                data = node['tracking_data']
                if str(data.get('track_status')) != '1':
                    return
                tracks = data.get('shipment_track') or []
                activities = data.get('shipment_track_activities') or []
                if not isinstance(tracks, list):
                    return
                if not isinstance(activities, list):
                    activities = []
                events = [{'date': str(a.get('date') or ''), 'activity': str(a.get('activity') or '')[:240],
                           'location': str(a.get('location') or '').strip()[:240]}
                          for a in activities if isinstance(a, dict) and a.get('activity')]
                events.sort(key=lambda event: event['date'], reverse=True)
                latest_location = next((event for event in events if event['location']), None)
                for track in tracks:
                    if not isinstance(track, dict):
                        continue
                    status = str(track.get('current_status') or '').strip()
                    awb = str(track.get('awb_code') or '').strip()
                    identity = (awb, str(track.get('id') or ''), status)
                    if not status or identity in seen:
                        continue
                    seen.add(identity)
                    # Include courier scan locations; exclude customer contact details and addresses.
                    shipments.append({
                        'status': status, 'awb': awb,
                        'courier': str(track.get('courier_name') or track.get('courier_company_name') or data.get('courier_name') or ''),
                        'latest_location': latest_location['location'] if latest_location else None,
                        'location_updated_at': latest_location['date'] if latest_location else None,
                        'estimated_delivery': data.get('etd') or None,
                        'delivered_at': track.get('delivered_date') or None,
                        'tracking_url': safe_tracking_url(data.get('track_url')),
                        'activities': events[:5],
                    })
                return
            for value in node.values():
                if isinstance(value, (dict, list)):
                    visit(value, depth + 1)
    visit(payload)
    return shipments

class ShiprocketClient:
    def __init__(self):
        self._token, self._expires_at, self._fingerprint = None, 0, None
        self._lock = threading.Lock()
        self._opener = urllib.request.build_opener(NoRedirect())

    def _request(self, path, token=None, body=None):
        headers = {'Accept': 'application/json', 'User-Agent': 'Kiaasa-Order-Tracking/1.0'}
        raw = None
        if token:
            headers['Authorization'] = 'Bearer ' + token
        if body is not None:
            headers['Content-Type'] = 'application/json'
            raw = json.dumps(body).encode('utf-8')
        request = urllib.request.Request(BASE_URL + path, data=raw, headers=headers)
        try:
            with self._opener.open(request, timeout=12) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            codes = {401: 'authentication', 403: 'authentication', 404: 'not_found',
                     400: 'invalid_reference', 422: 'invalid_reference', 429: 'rate_limited'}
            raise ShiprocketError(codes.get(error.code, 'unavailable')) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ShiprocketError('unavailable') from None
        except (ValueError, TypeError):
            raise ShiprocketError('invalid_response') from None

    def _get_token(self, config, refresh=False):
        fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).digest()
        with self._lock:
            if fingerprint != self._fingerprint:
                self._token, self._expires_at = None, 0
                self._fingerprint = fingerprint
            if not refresh and self._token and time.monotonic() < self._expires_at:
                return self._token
            if config['SHIPROCKET_TOKEN'] and not refresh:
                self._token = config['SHIPROCKET_TOKEN'].strip()
                self._expires_at = time.monotonic() + 3600
                return self._token
            if not config['SHIPROCKET_EMAIL'] or not config['SHIPROCKET_PASSWORD']:
                raise ShiprocketError('authentication' if config['SHIPROCKET_TOKEN'] else 'not_configured')
            payload = self._request('auth/login', body={'email': config['SHIPROCKET_EMAIL'], 'password': config['SHIPROCKET_PASSWORD']})
            token = payload.get('token') if isinstance(payload, dict) else None
            if not isinstance(token, str) or not token.strip():
                raise ShiprocketError('authentication')
            self._token, self._expires_at = token, time.monotonic() + 9 * 24 * 60 * 60
            return token

    def track(self, reference, kind='order'):
        config = configuration()
        token = self._get_token(config)
        if kind == 'awb':
            path = 'courier/track/awb/' + urllib.parse.quote(reference, safe='')
        else:
            query = {'order_id': reference}
            if config['SHIPROCKET_CHANNEL_ID']:
                query['channel_id'] = config['SHIPROCKET_CHANNEL_ID']
            path = 'courier/track?' + urllib.parse.urlencode(query)
        try:
            payload = self._request(path, token=token)
        except ShiprocketError as error:
            if error.code != 'authentication':
                raise
            token = self._get_token(config, refresh=True)
            payload = self._request(path, token=token)
        shipments = normalise_tracking(payload)
        if not shipments:
            raise ShiprocketError('not_found')
        return shipments

shiprocket = ShiprocketClient()
