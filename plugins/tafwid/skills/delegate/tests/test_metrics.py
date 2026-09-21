import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import metrics
import worker_registry as registry


class MetricsTests(unittest.TestCase):
    def test_claude_normalizes_cache_without_double_counting_model_usage(self):
        result = {'usage': {'input_tokens': 100, 'output_tokens': 20,
                  'cache_read_input_tokens': 300, 'cache_creation_input_tokens': 40},
                  'total_cost_usd': .03, 'duration_ms': 10000, 'duration_api_ms': 3000,
                  'modelUsage': {'opus': {'inputTokens': 999}}}
        stats = metrics.claude_usage(result)
        self.assertEqual(stats['input'], 100)
        self.assertEqual(stats['output'], 20)
        self.assertEqual(stats['cache_read'], 300)
        self.assertEqual(stats['cache_write'], 40)
        self.assertEqual(stats['cost_usd'], .03)
        self.assertEqual(stats['cost_kind'], 'api_equivalent')
        self.assertEqual(stats['duration_seconds'], 10)

    def test_missing_and_invalid_values_stay_unknown_not_zero(self):
        result = metrics.claude_usage({'usage': {'input_tokens': -1, 'output_tokens': True},
                                      'total_cost_usd': float('nan')})
        self.assertIsNone(result['input'])
        self.assertIsNone(result['output'])
        self.assertIsNone(result['cost_usd'])

    def test_legacy_registry_hydrates_result_and_does_not_mutate_record(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'CODEX_HOME': temp}):
            out = Path(temp) / 'run'
            out.mkdir()
            (out / 'result.json').write_text(json.dumps({'type': 'result', 'usage': {
                'input_tokens': 123, 'output_tokens': 45}, 'total_cost_usd': .2}))
            with registry.Tracker(out, 'task', 'session', 'Worker', {}, temp) as tracker:
                tracker.finish({'status': 'completed'})
            original = tracker.path.read_bytes()
            rows = registry.list_runs()
            self.assertEqual(rows[0]['usage']['input'], 123)
            self.assertEqual(registry.details(tracker.id)['runs'][0]['usage']['output'], 45)
            self.assertEqual(tracker.path.read_bytes(), original)

    def test_opencode_existing_summary_is_used_without_recounting_session(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out / 'summary.json').write_text(json.dumps({'backend': 'opencode', 'usage': {
                'input': 20, 'output': 10, 'cost_usd': 0}}))
            stats = metrics.for_record({'output_dir': temp, 'backend': 'opencode'})
            self.assertEqual(stats['cost_usd'], 0)
            self.assertEqual(stats['cost_kind'], 'reported')
            self.assertEqual(stats['input'], 20)

    def test_legacy_failed_run_with_only_default_zeros_is_not_verified_zero_usage(self):
        stats = metrics.for_record({'backend': 'opencode', 'status': 'error', 'usage': {
            'input': 0, 'output': 0, 'reasoning': 0, 'cache_read': 0, 'cache_write': 0, 'cost_usd': 0}})
        self.assertIsNone(stats['input'])
        self.assertIsNone(stats['cost_usd'])
        self.assertTrue(stats['partial'])


if __name__ == '__main__':
    unittest.main()
