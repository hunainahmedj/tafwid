import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import account_usage


class AccountUsageTests(unittest.TestCase):
    def test_native_windows_include_named_model_without_double_counting(self):
        result = account_usage.normalize({'subscription_type':'max','rate_limits_available':True,
            'rate_limits':{'five_hour':{'utilization':5,'resets_at':'2026-09-21T16:10:00.191+00:00'},
            'seven_day':{'utilization':80,'resets_at':'2026-09-24T00:00:00Z'},
            'seven_day_opus':None,'internal_alias':{'utilization':0},
            'model_scoped':[{'display_name':'Fable','utilization':83,'resets_at':'2026-09-24T00:00:00Z'}],
            'limits':[{'kind':'session','percent':5}], 'spend':{'enabled':False}}})
        self.assertEqual([(w['label'], w['used_percent']) for w in result['windows']],
                         [('Five-hour allowance',5),('Weekly allowance',80),('Fable allowance',83)])
        self.assertEqual(result['windows'][0]['resets_at'],1790007000)
        self.assertNotIn('internal_alias',json.dumps(result))

    def test_unknown_invalid_and_missing_are_not_zero(self):
        with self.assertRaises(ValueError): account_usage.normalize({'rate_limits_available':False})
        data=account_usage.normalize({'subscription_type':'max','rate_limits_available':True,'rate_limits':{
            'five_hour':{'utilization':True,'resets_at':'bad'},'seven_day':{'utilization':-2},
            'model_scoped':[{'display_name':'Sonnet','utilization':0,'resets_at':None}]}})
        self.assertEqual(len(data['windows']),1)
        self.assertIsNone(data['windows'][0]['resets_at'])
        self.assertEqual(data['windows'][0]['used_percent'],0)

    def test_failed_refresh_retains_stale_last_observation_not_fake_current(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CODEX_HOME':tmp}):
            reader=account_usage.AccountReader(fetch=lambda:{'account_id':'one','subscription_type':'max',
                'windows':[{'key':'five_hour','label':'Five-hour allowance','used_percent':5,'resets_at':2000}]}, clock=lambda:1000)
            reader.refresh_now()
            self.assertEqual(reader.snapshot()['status'],'available')
            reader.fetch=lambda: (_ for _ in ()).throw(ValueError('private upstream error'))
            reader.clock=lambda:1100
            reader.refresh_now()
            data=reader.snapshot()
            self.assertEqual(data['status'],'stale');self.assertEqual(data['observed_at'],1000)
            self.assertEqual(data['checked_at'],1100);self.assertEqual(len(data['history']),1)
            self.assertNotIn('private upstream error',json.dumps(data))
            self.assertEqual((account_usage.filename().stat().st_mode & 0o777),0o600)

    def test_account_switch_clears_previous_history_and_restart_preserves_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CODEX_HOME':tmp}):
            sample={'account_id':'one','subscription_type':'max','windows':[]}
            reader=account_usage.AccountReader(fetch=lambda:sample.copy(),clock=lambda:1000)
            reader.refresh_now();sample['account_id']='two';reader.clock=lambda:1001;reader.refresh_now()
            saved=account_usage.AccountReader(fetch=lambda:sample.copy(),clock=lambda:1001).snapshot()
            self.assertEqual(saved['account_id'],'two');self.assertEqual(len(saved['history']),1)
            self.assertEqual(saved['history'][0]['account_id'],'two')

    def test_polling_is_throttled_and_does_not_wait_for_native_query(self):
        import threading
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CODEX_HOME':tmp}):
            entered=threading.Event();release=threading.Event();calls=[]
            def fetch():
                calls.append(1);entered.set();release.wait(2)
                return {'account_id':'one','subscription_type':'max','windows':[]}
            reader=account_usage.AccountReader(fetch=fetch,clock=lambda:1000)
            self.assertEqual(reader.read()['status'],'refreshing');self.assertTrue(entered.wait(1))
            for _ in range(10):self.assertEqual(reader.read()['status'],'refreshing')
            release.set();reader.worker.join(2)
            self.assertEqual(reader.read()['status'],'available');self.assertEqual(len(calls),1)

    def test_slow_refresh_is_stamped_when_observed_not_before_message_boundary(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CODEX_HOME':tmp}):
            clock=[1000]
            def fetch():
                clock[0]=1025
                return {'account_id':'one','subscription_type':'max','windows':[]}
            reader=account_usage.AccountReader(fetch=fetch,clock=lambda:clock[0])
            reader.refresh_now()
            self.assertEqual(reader.snapshot()['observed_at'],1025)
            self.assertEqual(reader.snapshot()['history'][0]['at'],1025)
            self.assertEqual(reader.snapshot()['checked_at'],1025)

    def test_expired_window_stays_stale_instead_of_resetting_to_zero(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CODEX_HOME':tmp}):
            reader=account_usage.AccountReader(fetch=lambda:{'account_id':'one','subscription_type':'max',
                'windows':[{'key':'five_hour','label':'Five-hour allowance','used_percent':80,'resets_at':1001}]},clock=lambda:1000)
            reader.refresh_now();reader.clock=lambda:1002
            self.assertEqual(reader.snapshot()['status'],'stale')
            self.assertEqual(reader.snapshot()['windows'][0]['used_percent'],80)

    def test_malformed_cache_is_ignored_without_breaking_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'CODEX_HOME':tmp}):
            path=account_usage.filename();path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'version':1,'windows':[None],'history':[None], 'observed_at':'bad'}))
            self.assertEqual(account_usage.AccountReader().snapshot()['status'],'unavailable')

    def test_protocol_sends_only_controls_never_a_model_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'claude';capture=Path(tmp)/'requests.jsonl'
            binary.write_text('#!/usr/bin/env python3\nimport sys,json\n'
                'for line in sys.stdin:\n'
                ' d=json.loads(line)\n'
                f' with open({str(capture)!r},"a") as f:f.write(line)\n'
                ' response={"rate_limits_available":True,"subscription_type":"max","rate_limits":{"five_hour":{"utilization":2}}} if d["request"]["subtype"]=="get_usage" else {}\n'
                ' print(json.dumps({"type":"control_response","response":{"subtype":"success","request_id":d["request_id"],"response":response}}),flush=True)\n')
            binary.chmod(0o700)
            data=account_usage.query_native(str(binary),timeout=2)
            self.assertEqual(data['subscription_type'],'max')
            requests=[json.loads(x) for x in capture.read_text().splitlines()]
            self.assertEqual([x['type'] for x in requests],['control_request','control_request'])
            self.assertEqual(requests[1]['request'],{'subtype':'get_usage','skip_behaviors':True})

    def test_protocol_timeout_is_bounded_and_cleanup_terminates_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'claude';binary.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n');binary.chmod(0o700)
            start=time.monotonic()
            with self.assertRaises(ValueError):account_usage.query_native(str(binary),timeout=.1)
            self.assertLess(time.monotonic()-start,3)
