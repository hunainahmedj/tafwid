"""Local provider integration uses a loopback HTTP fixture, never live inference."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import opencode_providers as providers
import opencode_worker as worker
import paths


class LocalProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'CODEX_HOME': self.temp.name, 'LOCAL_TEST_KEY': 'fixture-secret'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.requests = []
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append((self.path, self.headers.get('Authorization')))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'data': [{'id': 'Qwen/test', 'max_model_len': 32768}]}).encode())
            def log_message(self, *args): pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.profile = {'kind': 'vllm', 'base_url': f'http://127.0.0.1:{self.server.server_port}/v1',
                        'model': 'Qwen/test', 'context_length': 32768, 'output_limit': 4096,
                        'tool_call': True, 'api_key_env': 'LOCAL_TEST_KEY'}
        self.write_profile()

    def write_profile(self):
        root = paths.state_root()
        root.mkdir(parents=True, exist_ok=True)
        (root / 'local-models.json').write_text(json.dumps({'version': 1, 'connections': {'desk': self.profile}}))

    def test_local_launch_uses_only_named_endpoint_and_keeps_credentials_out_of_artifacts(self):
        model = 'local-desk/Qwen/test'
        self.assertEqual(providers.provider_id(model), 'local-desk')
        info = providers.model_info(model)
        providers.validate_model(model, info)
        self.assertEqual(self.requests, [('/v1/models', 'Bearer fixture-secret')])
        self.assertEqual(info['context_length'], 32768)
        config = worker.configuration(model, info, 'edit', {'effective': 'scoped'}, ['python *'], 'worker')
        self.assertEqual(config['enabled_providers'], ['local-desk'])
        local = config['provider']['local-desk']
        self.assertEqual(local['options']['baseURL'], self.profile['base_url'])
        self.assertEqual(local['options']['apiKey'], '{env:LOCAL_TEST_KEY}')
        self.assertEqual(local['whitelist'], ['Qwen/test'])
        self.assertNotIn('fixture-secret', json.dumps(info) + json.dumps(config))
        self.assertEqual(providers.check_auth('local-desk'), 'environment')

    def test_lmstudio_requires_no_key_and_preserves_configured_context_limit(self):
        self.profile.update(kind='lmstudio', api_key_env=None, context_length=8192)
        self.write_profile()
        info = providers.model_info('local-desk/Qwen/test')
        self.assertEqual(info['context_length'], 8192)
        self.assertEqual(providers.check_auth('local-desk'), 'none')
        self.assertIsNone(self.requests[0][1])

    def test_key_file_is_used_without_copying_secret_into_worker_config(self):
        key = Path(self.temp.name) / 'server.key'
        key.write_text('local-file-secret\n')
        self.profile.update(api_key_env=None, api_key_file=str(key))
        self.write_profile()
        info = providers.model_info('local-desk/Qwen/test')
        config = providers.provider_config('local-desk/Qwen/test', info)
        self.assertEqual(self.requests[0][1], 'Bearer local-file-secret')
        self.assertEqual(config['options']['apiKey'], '{file:' + str(key) + '}')
        self.assertNotIn('local-file-secret', json.dumps(info) + json.dumps(config))

    def test_local_redirects_never_forward_the_auth_header(self):
        class Redirect(BaseHTTPRequestHandler):
            def do_GET(inner):
                inner.send_response(302)
                inner.send_header('Location', self.profile['base_url'] + '/models')
                inner.end_headers()
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.profile['base_url'] = f'http://127.0.0.1:{server.server_port}/v1'
        self.write_profile()
        with self.assertRaisesRegex(ValueError, 'redirected'):
            providers.model_info('local-desk/Qwen/test')
        self.assertEqual(self.requests, [])

    def test_absent_model_tools_or_invalid_limits_stop_preflight(self):
        for changes in ({'model': 'missing'}, {'tool_call': False}, {'context_length': 65536},
                        {'output_limit': 999999}, {'api_key_env': 'UNSET_TAFWID_TEST_KEY'}):
            with self.subTest(changes=changes):
                original = self.profile.copy()
                self.profile.update(changes)
                self.write_profile()
                with self.assertRaises(ValueError):
                    info = providers.model_info('local-desk/' + self.profile['model'])
                    providers.validate_model('local-desk/' + self.profile['model'], info)
                self.profile = original

    def test_profiles_reject_public_destinations_credentials_and_bad_names(self):
        for url in ('https://example.com/v1', 'http://user:secret@127.0.0.1/v1',
                    'http://127.0.0.1/v1?key=secret', 'file:///tmp/models', 'http://169.254.169.254/v1'):
            with self.subTest(url=url):
                self.profile['base_url'] = url
                self.write_profile()
                with self.assertRaises(ValueError): providers.model_info('local-desk/Qwen/test')
        with self.assertRaises(ValueError): providers.model_info('local-unknown/Qwen/test')
        self.assertEqual(self.requests, [])


if __name__ == '__main__': unittest.main()
