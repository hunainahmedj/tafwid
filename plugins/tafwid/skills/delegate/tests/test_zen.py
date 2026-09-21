"""Zen provider boundaries; no network or actual model calls."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import opencode_providers as providers

ZEN_INFO = {'id': 'free-coder', 'pricing': {'prompt': 0, 'completion': 0},
            'supported_parameters': ['tools'], 'context_length': 64000,
            'npm': '@ai-sdk/openai-compatible'}


class ZenProviderTests(unittest.TestCase):
    def test_zen_preflight_cross_checks_live_id_and_current_pricing(self):
        metadata = {'opencode': {'models': {'free-coder': {'cost': {'input': 0, 'output': 0},
                    'tool_call': True, 'limit': {'context': 64000, 'output': 8000}}}}}
        with patch.object(providers, 'fetch_json', side_effect=[{'data': [{'id': 'free-coder'}]}, metadata]):
            info = providers.model_info('opencode/free-coder')
        providers.validate_model('opencode/free-coder', info)
        self.assertEqual(info['context_length'], 64000)
        for change in ({'pricing': {'prompt': 1, 'completion': 0}}, {'pricing': {}},
                       {'supported_parameters': []}, {'id': 'other'}, {'npm': 'untrusted-sdk'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                providers.validate_model('opencode/free-coder', {**info, **change})
        with patch.object(providers, 'fetch_json', side_effect=[{'data': []}, metadata]):
            absent = providers.model_info('opencode/free-coder')
        with self.assertRaises(ValueError): providers.validate_model('opencode/free-coder', absent)

    def test_unavailable_catalogue_never_uses_scout_cache(self):
        with patch.object(providers, 'fetch_json', side_effect=OSError('offline')):
            with self.assertRaisesRegex(ValueError, 'no worker started'):
                providers.model_info('opencode/free-coder')

    def test_auth_is_provider_specific_and_public_is_zen_only(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            'XDG_DATA_HOME': temp, 'OPENCODE_API_KEY': '', 'OPENROUTER_API_KEY': ''}):
            self.assertEqual(providers.check_auth('opencode'), 'public')
            with self.assertRaises(ValueError): providers.check_auth('openrouter')
            folder = Path(temp) / 'opencode'
            folder.mkdir()
            (folder / 'auth.json').write_text(json.dumps({'opencode': {'type': 'api', 'key': 'fixture-key'}}))
            self.assertEqual(providers.check_auth('opencode'), 'opencode')
            with self.assertRaises(ValueError): providers.check_auth('openrouter')

    def test_zen_configuration_pins_transport_and_model_allowlist(self):
        config = providers.provider_config('opencode/free-coder', ZEN_INFO)
        self.assertEqual(config['whitelist'], ['free-coder'])
        self.assertEqual(config['options']['baseURL'], 'https://opencode.ai/zen/v1')
        self.assertNotIn('apiKey', config['options'])
        self.assertEqual(config['models']['free-coder']['provider']['npm'], '@ai-sdk/openai-compatible')
        self.assertNotIn('provider', config['models']['free-coder'].get('options', {}))


if __name__ == '__main__': unittest.main()
