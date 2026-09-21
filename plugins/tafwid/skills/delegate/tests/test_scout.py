import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import scout


class ScoutTests(unittest.TestCase):
    def test_openrouter_excludes_paid_unknown_prices_and_router(self):
        base = {'id': 'example/code:free', 'name': 'Example Code',
                'pricing': {'prompt': '0', 'completion': '0'},
                'context_length': 64000, 'supported_parameters': ['tools', 'reasoning'],
                'architecture': {'input_modalities': ['text']}}
        data = {'data': [base, {**base, 'id': 'example/paid', 'pricing': {'prompt': '.1', 'completion': '0'}},
                         {**base, 'id': 'example/unknown:free', 'pricing': {}},
                         {**base, 'id': 'openrouter/free'}]}
        rows = scout.openrouter_models(data)
        self.assertEqual([r['model'] for r in rows], ['openrouter/example/code:free'])
        self.assertIn('implementation', rows[0]['task_candidates'])
        self.assertEqual(rows[0]['confidence'], 'metadata_only')
        self.assertFalse(rows[0]['tested'])

    def test_no_tools_is_not_recommended_for_coding(self):
        row = scout.openrouter_models({'data': [{'id': 'example/text:free',
            'pricing': {'prompt': '0', 'completion': '0'}, 'supported_parameters': []}]})[0]
        self.assertNotIn('implementation', row['task_candidates'])
        self.assertEqual(row['dispatch'], 'tool_support_unverified')

    def test_zen_intersects_live_ids_with_free_catalogue_metadata(self):
        metadata = {'opencode': {'models': {
            'free-code': {'name': 'Code', 'cost': {'input': 0, 'output': 0}, 'tool_call': True,
                          'limit': {'context': 100000}, 'reasoning': True},
            'retired': {'cost': {'input': 0, 'output': 0}, 'tool_call': True},
            'paid': {'cost': {'input': 1, 'output': 2}, 'tool_call': True}}}}
        rows = scout.zen_models({'data': [{'id': 'free-code'}, {'id': 'paid'}, {'id': 'unknown'}]}, metadata)
        self.assertEqual([r['model'] for r in rows], ['opencode/free-code'])
        self.assertTrue(rows[0]['tools'])
        self.assertEqual(rows[0]['dispatch'], 'preflight_required')
        self.assertEqual(rows[0]['price_source'], 'models.dev')

    def test_cache_avoids_fetches_and_failed_refresh_is_explicitly_stale(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'CODEX_HOME': temp}):
            payload = {'data': [{'id': 'example/a:free', 'pricing': {'prompt': '0', 'completion': '0'}}]}
            with patch.object(scout, 'fetch_json', return_value=payload):
                first = scout.catalogue('openrouter', now=100)
            with patch.object(scout, 'fetch_json', side_effect=OSError('offline')):
                cached = scout.catalogue('openrouter', now=101)
                stale = scout.catalogue('openrouter', refresh=True, now=102)
            self.assertEqual(cached['checked_at'], first['checked_at'])
            self.assertFalse(cached['stale'])
            self.assertTrue(stale['stale'])
            self.assertIn('error', stale)
            self.assertEqual(stale['checked_at'], 100)

    def test_shortlist_is_bounded_and_keeps_observation_separate_from_acceptance(self):
        rows = scout.openrouter_models({'data': [{'id': f'example/code{i}:free',
            'pricing': {'prompt': '0', 'completion': '0'}, 'supported_parameters': ['tools']}
            for i in range(10)]})
        runs = [{'model_selection': {'requested_model': 'openrouter/example/code0:free'},
                 'status': 'completed'}]
        result = scout.shortlist(rows, runs, limit=2, task='implementation')
        self.assertEqual(len(result), 2)
        observed = next(r for r in result if r['model'].endswith('code0:free'))
        self.assertEqual(observed['observed_runs'], {'completed': 1})
        self.assertFalse(observed['tested'])
        self.assertEqual(observed['confidence'], 'metadata_only')


if __name__ == '__main__':
    unittest.main()
