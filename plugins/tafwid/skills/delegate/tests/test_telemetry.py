"""Token samples must retain timing, run ownership, and observed context drops."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import worker_registry as registry

START = 1750000000
SESSION = 'a0000000-0000-0000-0000-000000000001'
MODEL = 'claude-test-model'


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'HOME': str(self.home), 'CODEX_HOME': str(self.home / 'codex'),
                                         'CLAUDE_CONFIG_DIR': str(self.home / '.claude')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.out = self.home / 'out'
        self.out.mkdir()
        self.transcript = self.home / '.claude/projects/-workspace-project' / (SESSION + '.jsonl')
        self.transcript.parent.mkdir(parents=True)

    def snapshot(self, **changes):
        run_id = str(uuid.uuid4())
        row = {'id': run_id, 'output_dir': str(self.out), 'session_id': SESSION,
               'cwd': '/workspace/project', 'backend': 'claude', 'status': 'completed',
               'started_at': START, 'ended_at': START + 60}
        row.update(changes)
        registry.atomic_json(registry.state_root() / 'workers' / (run_id + '.json'), row)
        loaded = registry.load_record(run_id)
        self.assertIn('telemetry', loaded, 'Public run records must include bounded timestamped usage evidence')
        return loaded['telemetry']

    def write_lines(self, rows, path=None):
        (path or self.transcript).write_text(''.join(json.dumps(row) + '\n' for row in rows))

    def assistant(self, ident, seconds, input_tokens=100, output=10, **changes):
        from datetime import datetime, timezone
        row = {'type': 'assistant', 'sessionId': SESSION, 'cwd': '/workspace/project',
               'timestamp': datetime.fromtimestamp(START + seconds, timezone.utc).isoformat(),
               'message': {'id': ident, 'model': MODEL, 'content': [{'text': 'PRIVATE PROMPT'}],
                           'usage': {'input_tokens': input_tokens, 'output_tokens': output,
                                     'cache_read_input_tokens': 200, 'cache_creation_input_tokens': 50}}}
        row.update(changes)
        return row

    def step(self, ident, seconds, **changes):
        row = {'type': 'step_finish', 'timestamp': (START + seconds) * 1000, 'sessionID': 'ses_test',
               'part': {'id': ident, 'messageID': 'msg_' + ident, 'type': 'step-finish',
                        'tokens': {'input': 500, 'output': 20, 'reasoning': 5,
                                   'cache': {'read': 30, 'write': 10}}}}
        row.update(changes)
        return row

    def test_mid_run_samples_preserve_timestamps_and_never_create_baseline(self):
        self.write_lines([self.assistant('msg_a', 10), self.assistant('msg_b', 45)])
        result = self.snapshot()
        self.assertEqual([s['at'] for s in result['samples']], [START + 10, START + 45])
        self.assertEqual(result['coverage'], 'complete')
        self.assertNotIn('PRIVATE PROMPT', json.dumps(result))

    def test_resumes_clip_shared_transcript_to_each_invocation(self):
        self.write_lines([self.assistant('old', -20), self.assistant('first', 10),
                          self.assistant('second', 70)])
        first = self.snapshot()
        second = self.snapshot(started_at=START + 60, ended_at=START + 90)
        self.assertEqual(len(first['samples']), 1)
        self.assertEqual(len(second['samples']), 1)
        self.assertEqual(first['samples'][0]['at'], START + 10)
        self.assertEqual(second['samples'][0]['at'], START + 70)
        self.assertNotEqual(first['samples'][0]['id'], second['samples'][0]['id'])

    def test_streamed_duplicates_keep_final_usage_without_hiding_compaction_drop(self):
        self.write_lines([self.assistant('a', 10, input_tokens=700, output=1),
                          self.assistant('a', 11, input_tokens=700, output=50),
                          self.assistant('b', 20, input_tokens=100, output=10)])
        (self.out / 'result.json').write_text(json.dumps({'modelUsage': {MODEL: {'contextWindow': 2000}}}))
        samples = self.snapshot()['samples']
        self.assertEqual(len(samples), 2)
        self.assertEqual([s['output'] for s in samples], [50, 10])
        self.assertEqual([s['context_tokens'] for s in samples], [1000, 360])
        self.assertEqual([s['context_percent'] for s in samples], [50, 18])

    def test_unknown_limits_and_invalid_token_fields_remain_unknown(self):
        invalid = self.assistant('bad', 20)
        invalid['message']['usage']['cache_read_input_tokens'] = -1
        self.write_lines([self.assistant('a', 10), invalid])
        samples = self.snapshot()['samples']
        self.assertEqual(samples[0]['context_tokens'], 360)
        self.assertIsNone(samples[0]['context_limit'])
        self.assertIsNone(samples[0]['context_percent'])
        self.assertIsNone(samples[1]['cache_read'])
        self.assertIsNone(samples[1]['context_tokens'])

    def test_invalid_timestamps_and_partial_tail_cannot_invent_samples(self):
        self.write_lines([self.assistant('good', 10), self.assistant('bad', 20, timestamp='invalid')])
        with self.transcript.open('a') as stream:
            stream.write('{"type":"assistant"')
        result = self.snapshot()
        self.assertEqual(len(result['samples']), 1)
        self.assertEqual(result['coverage'], 'partial')
        self.assertTrue(result['truncated'])

    def test_only_exact_registered_session_and_cwd_are_read(self):
        self.write_lines([self.assistant('other-session', 10, sessionId=str(uuid.uuid4())),
                          self.assistant('other-cwd', 10, cwd='/private/unrelated')])
        self.write_lines([self.assistant('secret', 10)], self.transcript.with_name('unrelated.jsonl'))
        self.assertEqual(self.snapshot()['samples'], [])
        self.transcript.unlink()
        result = self.snapshot()
        self.assertEqual(result['samples'], [])
        self.assertEqual(result['coverage'], 'unavailable')

    def test_opencode_deduplicates_steps_and_uses_only_selected_model_limit(self):
        event = self.step('step1', 10)
        self.write_lines([event, event, self.step('step2', 40)], self.out / 'events.jsonl')
        (self.out / 'request.json').write_text(json.dumps({'config': {
            'model': 'local-demo/chosen', 'provider': {'local-demo': {'models': {
                'benchmark': {'limit': {'context': 999999}},
                'chosen': {'limit': {'context': 1000}}}}}}}))
        result = self.snapshot(backend='opencode', session_id='ses_test')
        self.assertEqual([s['at'] for s in result['samples']], [START + 10, START + 40])
        self.assertEqual(result['samples'][0]['context_tokens'], 560)
        self.assertEqual(result['samples'][0]['context_limit'], 1000)
        self.assertEqual(result['samples'][0]['context_percent'], 56)
        self.assertEqual(result['samples'][0]['model'], 'local-demo/chosen')

    def test_missing_start_time_does_not_attribute_full_shared_session(self):
        self.write_lines([self.assistant('a', 10)])
        result = self.snapshot(started_at=None)
        self.assertEqual(result['samples'], [])
        self.assertEqual(result['coverage'], 'unavailable')

    def test_empty_completed_artifact_does_not_claim_zero_usage(self):
        self.transcript.write_text('')
        result = self.snapshot()
        self.assertEqual(result['coverage'], 'unavailable')
        self.assertEqual(result['samples'], [])

    def test_complete_last_record_without_newline_is_valid(self):
        self.transcript.write_text(json.dumps(self.assistant('last', 10)))
        result = self.snapshot()
        self.assertEqual(len(result['samples']), 1)
        self.assertEqual(result['coverage'], 'complete')

    def test_bounds_keep_recent_samples_and_mark_missing_history(self):
        import telemetry
        self.write_lines([self.assistant('first', 10), self.assistant('second', 20),
                          self.assistant('last', 30)])
        with patch.object(telemetry, 'MAX_SAMPLES', 2):
            result = self.snapshot()
        self.assertEqual([s['at'] for s in result['samples']], [START + 20, START + 30])
        self.assertTrue(result['truncated'])
        self.assertEqual(result['coverage'], 'partial')

    def test_oversized_artifact_tail_retains_recent_whole_records(self):
        import telemetry
        lines = [json.dumps(self.assistant(str(i), i + 1)) + '\n' for i in range(12)]
        self.transcript.write_text(''.join(lines))
        with patch.object(telemetry, 'MAX_BYTES', len(''.join(lines[-3:]).encode()) + 40):
            result = self.snapshot()
        self.assertEqual([s['at'] for s in result['samples']], [START + 10, START + 11, START + 12])
        self.assertTrue(result['truncated'])

    def test_appended_usage_invalidates_cache_and_results_do_not_mutate_cache(self):
        self.write_lines([self.assistant('first', 10)])
        initial = self.snapshot()
        initial['samples'][0]['input'] = 999
        self.assertEqual(self.snapshot()['samples'][0]['input'], 100)
        with self.transcript.open('a') as stream:
            stream.write(json.dumps(self.assistant('second', 20)) + '\n')
        self.assertEqual(len(self.snapshot()['samples']), 2)

    def test_zero_usage_is_an_observation_but_sidechain_usage_is_excluded(self):
        row = self.assistant('zero', 10, input_tokens=0, output=0)
        row['message']['usage'].update(cache_read_input_tokens=0, cache_creation_input_tokens=0)
        self.write_lines([row, self.assistant('helper', 15, isSidechain=True)])
        result = self.snapshot()
        self.assertEqual(len(result['samples']), 1)
        self.assertEqual(result['samples'][0]['context_tokens'], 0)
        self.assertEqual(result['samples'][0]['input'], 0)

    def test_other_model_capacity_cannot_be_used_for_selected_worker(self):
        self.write_lines([self.assistant('a', 10)])
        (self.out / 'result.json').write_text(json.dumps({'modelUsage': {'other-model': {'contextWindow': 9999}}}))
        self.assertIsNone(self.snapshot()['samples'][0]['context_limit'])

    def test_symlink_transcript_cannot_escape_registered_project(self):
        target = self.home / 'unrelated.jsonl'
        self.write_lines([self.assistant('private', 10)], target)
        self.transcript.symlink_to(target)
        self.assertEqual(self.snapshot()['samples'], [])

    def test_normal_worker_history_remains_cached_across_dashboard_refresh(self):
        import telemetry
        records = []
        for i in range(40):
            session = str(uuid.uuid4())
            self.write_lines([self.assistant('a', 10, sessionId=session)],
                             self.transcript.with_name(session + '.jsonl'))
            row = {'backend': 'claude', 'session_id': session, 'cwd': '/workspace/project',
                   'output_dir': str(self.out), 'status': 'completed',
                   'started_at': START, 'ended_at': START + 60}
            records.append(row)
            self.assertEqual(len(telemetry.for_record(row)['samples']), 1)
        # The metadata signature remains readable, but reopening transcripts is
        # unavailable: a refresh should serve unchanged history from its cache.
        with patch.object(Path, 'open', side_effect=OSError('artifact temporarily unavailable')):
            self.assertEqual(len(telemetry.for_record(records[0])['samples']), 1)


if __name__ == '__main__':
    unittest.main()
