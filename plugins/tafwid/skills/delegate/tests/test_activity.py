import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import activity

THREAD='12345678-1234-4234-8234-123456789abc'
class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        env=patch.dict(os.environ,{'CODEX_HOME':str(self.home)});env.start();self.addCleanup(env.stop)
        self.path=self.home/'sessions/2026/09/17'/f'rollout-test-{THREAD}.jsonl'
        self.path.parent.mkdir(parents=True)
        self.append('session_meta',{'id':THREAD})
        self.reader=activity.ActivityReader()
    def append(self,kind,payload):
        with self.path.open('a') as f:f.write(json.dumps({'timestamp':'2026-09-17T10:00:00Z','type':kind,'payload':payload})+'\n')
    def test_only_public_assistant_messages_and_tool_actions_are_exported(self):
        self.append('turn_context',{'model':'gpt-6-astra','effort':'high','turn_id':'turn-one'})
        self.append('event_msg',{'type':'task_started','turn_id':'turn-one'})
        self.append('response_item',{'type':'reasoning','summary':[{'text':'SECRET REASONING'}]})
        self.append('response_item',{'type':'message','role':'assistant','channel':'analysis','content':[{'text':'SECRET ANALYSIS'}]})
        self.append('response_item',{'type':'message','role':'user','content':[{'text':'PRIVATE USER INPUT'}]})
        self.append('response_item',{'type':'message','role':'assistant','channel':'commentary','content':[{'type':'output_text','text':'I am checking the diff.'}]})
        self.append('response_item',{'type':'message','role':'assistant','phase':'commentary','content':[{'type':'output_text','text':'Recorded phase update.'}]})
        self.append('response_item',{'type':'message','role':'assistant','phase':'final_answer','content':[{'type':'output_text','text':'Verified the correction.'}]})
        self.append('response_item',{'type':'custom_tool_call','name':'exec','call_id':'call-one','input':'git diff --check'})
        self.append('response_item',{'type':'custom_tool_call_output','call_id':'call-one','output':'PRIVATE RAW OUTPUT'})
        data=self.reader.read(THREAD)
        self.assertEqual(data['model'],'gpt-6-astra')
        self.assertEqual(data['turn_status'],'running')
        text=json.dumps(data)
        self.assertIn('I am checking the diff.',text);self.assertIn('git diff --check',text)
        self.assertIn('Recorded phase update.',text)
        self.assertIn('Verified the correction.',text)
        for secret in ['SECRET REASONING','SECRET ANALYSIS','PRIVATE USER INPUT','PRIVATE RAW OUTPUT']:self.assertNotIn(secret,text)
        tool=[e for e in data['events'] if e['kind']=='tool'][0]
        self.assertEqual(tool['state'],'returned')
    def test_append_partial_line_pagination_search_and_completion(self):
        self.append('response_item',{'type':'function_call','name':'exec_command','call_id':'x','arguments':'{"cmd":"cat Archivist instructions"}'})
        first=self.reader.read(THREAD)
        with self.path.open('a') as f:f.write('{"timestamp":"now","type":"event_msg","payload":')
        self.assertEqual(self.reader.read(THREAD)['total'],first['total'])
        with self.path.open('a') as f:f.write('{"type":"task_complete","turn_id":"one"}}\n')
        second=self.reader.read(THREAD,query='archivist',limit=1)
        self.assertEqual(second['turn_status'],'completed');self.assertEqual(len(second['events']),1)
        self.assertEqual(second['events'][0]['name'],'exec_command')
        self.assertEqual(self.reader.read(THREAD,before=second['events'][0]['line'],query='archivist')['events'],[])
        self.assertEqual(self.reader.read(THREAD)['total'],first['total']+1)
    def test_missing_mismatched_and_symlink_logs_fail_closed(self):
        self.assertEqual(self.reader.read('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa')['availability'],'unavailable')
        self.path.write_text(json.dumps({'type':'session_meta','payload':{'id':'another'}})+'\n')
        self.assertEqual(self.reader.read(THREAD)['availability'],'unavailable')
        self.path.unlink(); self.path.symlink_to(self.home/'elsewhere')
        self.assertEqual(self.reader.read(THREAD)['availability'],'unavailable')
        with self.assertRaises(ValueError):self.reader.read('../../outside')

    def test_message_boundaries_strip_context_and_follow_appended_requests(self):
        self.append('response_item',{'type':'message','role':'user','content':[{'type':'input_text','text':'# AGENTS.md instructions for /private/project\nENVIRONMENT SECRET'}]})
        self.append('response_item',{'type':'message','role':'user','content':[{'type':'input_text','text':'<environment_context>ENVIRONMENT SECRET</environment_context>'}]})
        self.append('response_item',{'type':'message','role':'user','content':[{'type':'input_text','text':'<in-app-browser-context>PRIVATE TOKEN</in-app-browser-context>\n\n## My request:\nwork on slice 2<image name=\"screenshot\" path=\"/private/attachment.png\"> </image>'}]})
        self.assertTrue(callable(getattr(self.reader,'messages',None)))
        data=self.reader.messages(THREAD)
        self.assertEqual(len(data['messages']),1)
        self.assertEqual(data['messages'][0]['preview'],'work on slice 2')
        self.assertEqual(data['messages'][0]['timestamp'],1789639200)
        chosen=data['messages'][0]['line']
        self.append('response_item',{'type':'message','role':'user','content':[{'type':'input_text','text':'<send_user_message_question_reply>[{"question":"private question", "answer":"use the workstation"}]</send_user_message_question_reply>'}]})
        data=self.reader.messages(THREAD)
        self.assertEqual([m['preview'] for m in data['messages']],['use the workstation','work on slice 2'])
        self.assertEqual(data['messages'][1]['line'],chosen)
        for secret in ('PRIVATE TOKEN','ENVIRONMENT SECRET','private question','/private/attachment.png'):self.assertNotIn(secret,json.dumps(data))
        self.assertNotIn('work on slice 2',json.dumps(self.reader.read(THREAD)))
