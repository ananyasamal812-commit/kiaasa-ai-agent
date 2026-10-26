import json
import unittest
from unittest.mock import patch
import urllib.error
from shiprocket_client import ShiprocketClient, ShiprocketError, normalise_tracking, safe_tracking_url
from order_tracking import handle_order_tracking, tracking_sessions

CONFIG = {'SHIPROCKET_EMAIL': 'api@example.test', 'SHIPROCKET_PASSWORD': 'test-only',
          'SHIPROCKET_TOKEN': '', 'SHIPROCKET_CHANNEL_ID': '42'}
TRACKING = {'tracking_data': {'track_status': 1, 'etd': '2026-10-10',
    'shipment_track': [{'id': 1, 'awb_code': '123456789', 'current_status': 'In Transit',
                        'courier_name': 'Example Courier', 'consignee_name': 'PRIVATE NAME',
                        'destination': 'PRIVATE ADDRESS'}],
    'shipment_track_activities': [{'date': '2026-10-07', 'activity': 'Shipment picked up', 'location': 'Jhansi courier hub'}],
    'track_url': 'https://app.shiprocket.in/tracking/awb/123456789'}}

class ShiprocketTests(unittest.TestCase):
    def tearDown(self):
        tracking_sessions.clear()

    def test_response_shapes_and_private_fields(self):
        for payload in [TRACKING, [TRACKING], {'123456789': TRACKING}]:
            result = normalise_tracking(payload)
            self.assertEqual(result[0]['status'], 'In Transit')
            self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertEqual(len(normalise_tracking([TRACKING, TRACKING])), 1)

    def test_latest_scan_location_and_missing_location(self):
        import copy
        payload = copy.deepcopy(TRACKING)
        payload['tracking_data']['shipment_track_activities'].append({'date': '2026-10-08', 'activity': 'Departed', 'location': 'Lucknow hub'})
        result = normalise_tracking(payload)[0]
        self.assertEqual(result['latest_location'], 'Lucknow hub')
        self.assertEqual(result['location_updated_at'], '2026-10-08')
        self.assertEqual(result['activities'][0]['location'], 'Lucknow hub')
        payload['tracking_data']['shipment_track_activities'] = [{'date': '2026-10-08', 'activity': 'In transit'}]
        self.assertIsNone(normalise_tracking(payload)[0]['latest_location'])

    def test_no_fabricated_status(self):
        self.assertEqual(normalise_tracking({'tracking_data': {'track_status': 0, 'error': 'missing'}}), [])
        self.assertEqual(normalise_tracking({'tracking_data': {'track_status': 1, 'shipment_track': [{}]}}), [])
        self.assertEqual(normalise_tracking(None), [])

    def test_tracking_links(self):
        self.assertIsNone(safe_tracking_url('javascript:alert(1)'))
        self.assertIsNone(safe_tracking_url('https://app.shiprocket.in.evil.test/track'))
        self.assertIsNone(safe_tracking_url('https://user:secret@app.shiprocket.in/'))
        self.assertTrue(safe_tracking_url('https://app.shiprocket.in/tracking/awb/123'))

    @patch('shiprocket_client.configuration', return_value=CONFIG)
    def test_login_cache_and_channel_lookup(self, config):
        client = ShiprocketClient()
        with patch.object(client, '_request', side_effect=[{'token': 'TEST_TOKEN'}, [TRACKING], [TRACKING]]) as call:
            self.assertEqual(client.track('KIA-123')[0]['awb'], '123456789')
            client.track('KIA-123')
            self.assertEqual(call.call_count, 3)
            self.assertEqual(call.call_args_list[1].args[0], 'courier/track?order_id=KIA-123&channel_id=42')

    @patch('shiprocket_client.configuration', return_value=CONFIG)
    def test_refresh_expired_auth_once(self, config):
        client = ShiprocketClient()
        with patch.object(client, '_request', side_effect=[{'token': 'OLD'}, ShiprocketError('authentication'), {'token': 'NEW'}, TRACKING]) as call:
            self.assertEqual(client.track('123')[0]['status'], 'In Transit')
            self.assertEqual(call.call_count, 4)

    @patch('shiprocket_client.configuration', return_value=dict(CONFIG, SHIPROCKET_TOKEN='DIRECT'))
    def test_awb_and_direct_token(self, config):
        client = ShiprocketClient()
        with patch.object(client, '_request', return_value=TRACKING) as call:
            client.track('AB/123', kind='awb')
            call.assert_called_once_with('courier/track/awb/AB%2F123', token='DIRECT')

    def test_missing_configuration(self):
        with self.assertRaises(ShiprocketError) as error:
            ShiprocketClient()._get_token(dict.fromkeys(CONFIG, ''))
        self.assertEqual(error.exception.code, 'not_configured')

    def test_timeout_and_http_error_are_sanitised(self):
        client = ShiprocketClient()
        for failure, expected in [(TimeoutError('SECRET'), 'unavailable'),
                (urllib.error.HTTPError('https://example.test', 429, 'SECRET', {}, None), 'rate_limited')]:
            with patch.object(client._opener, 'open', side_effect=failure):
                with self.assertRaises(ShiprocketError) as error:
                    client._request('courier/track?order_id=123')
                self.assertEqual(str(error.exception), expected)

    @patch('order_tracking.shiprocket.track', return_value=normalise_tracking(TRACKING))
    def test_chat_prompt_lookup_and_cancel(self, track):
        result = handle_order_tracking('test', 'I want to track my order')
        self.assertEqual(result['tracking_state'], 'awaiting_order_id')
        result = handle_order_tracking('test', '#12345')
        track.assert_called_once_with('12345', kind='order')
        self.assertEqual(result['tracking_state'], 'found')
        self.assertEqual(result['products'], [])
        handle_order_tracking('test', 'track my order')
        self.assertEqual(handle_order_tracking('test', 'cancel')['tracking_state'], 'cancelled')

    @patch('order_tracking.shiprocket.track', return_value=normalise_tracking(TRACKING))
    def test_explicit_awb(self, track):
        result = handle_order_tracking('test', 'AWB 123456789')
        track.assert_called_once_with('123456789', kind='awb')
        self.assertEqual(result['tracking_state'], 'found')

    @patch('order_tracking.shiprocket.track', side_effect=ShiprocketError('not_found'))
    def test_lookup_error_and_return_to_shopping(self, track):
        result = handle_order_tracking('test', 'track order KIA-123')
        self.assertEqual(result['tracking_state'], 'not_found')
        self.assertIsNone(handle_order_tracking('test', 'show me kurtas'))
        self.assertNotIn('test', tracking_sessions)

if __name__ == '__main__':
    unittest.main()
