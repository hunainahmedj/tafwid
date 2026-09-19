"""Read public Codex activity for one known conversation, incrementally and locally.

This is an adapter for the observed local rollout format, not a stable Codex API.
Activity excludes reasoning, user messages, raw tool outputs, and instruction context.
A separate endpoint exposes bounded user-request previews for time filtering.
"""
from collections import deque
import json
from datetime import datetime
import re
from pathlib import Path
import threading
import uuid
import worker_registry as registry

MAX_EVENTS = 5000
TEXT_LIMIT = 6000


def clipped(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text[:TEXT_LIMIT] + ('\n[Excerpt truncated.]' if len(text) > TEXT_LIMIT else '')


def request_preview(payload):
    """Extract request text from observed UI wrappers, excluding injected context."""
    text = '\n'.join(part.get('text', '') for part in payload.get('content', [])
                     if isinstance(part, dict) and part.get('type') == 'input_text').strip()
    if '## My request:' in text:
        text = text.split('## My request:', 1)[1].strip()
    elif text.startswith(('# AGENTS.md instructions', '<environment_context>', '<recommended_plugins>', '<skill>', '<INSTRUCTIONS>')):
        return None
    else:
        text = re.sub(r'<in-app-browser-context\b[^>]*>.*?</in-app-browser-context>', '', text, flags=re.S).strip()
    if text.startswith('<send_user_message_question_reply>'):
        try:
            replies = json.loads(text.split('>', 1)[1].rsplit('</', 1)[0])
            text = '; '.join(str(reply.get('answer', '')) for reply in replies if isinstance(reply, dict))
        except (ValueError, TypeError):
            return None
    text = re.sub(r'<image\b[^>]*>.*?</image>', '', text, flags=re.S).strip()
    return ' '.join(text.split())[:240] or None


class ActivityReader:
    def __init__(self):
        self.cache = {}
        self.lock = threading.Lock()

    def _locate(self, thread):
        root = registry.state_root().parents[1]
        candidates = []
        for directory in (root / 'sessions', root / 'archived_sessions'):
            for path in directory.glob(f'**/*-{thread}.jsonl'):
                try:
                    if not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()):
                        candidates.append(path)
                except OSError:
                    continue
        return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None

    def _consume(self, state, row):
        payload = row.get('payload')
        if not isinstance(payload, dict):
            return
        kind = row.get('type')
        subtype = payload.get('type')
        stamp = row.get('timestamp')
        event = None
        if kind == 'turn_context':
            state['model'] = payload.get('model')
            state['effort'] = payload.get('effort')
        elif kind == 'event_msg' and subtype in ('task_started', 'task_complete', 'turn_aborted'):
            state['turn_status'] = {'task_started':'running','task_complete':'completed','turn_aborted':'interrupted'}[subtype]
            event = {'kind':'turn','name':subtype,'text':state['turn_status']}
        elif kind == 'response_item':
            if subtype == 'message' and payload.get('role') == 'user':
                preview = request_preview(payload)
                if preview:
                    try:
                        timestamp = datetime.fromisoformat(stamp.replace('Z', '+00:00')).timestamp()
                    except (ValueError, TypeError, AttributeError):
                        return
                    state['messages'].append({'line':state['line'], 'timestamp':timestamp, 'preview':preview})
            phase = payload.get('phase') or payload.get('channel')
            if phase == 'final_answer':
                phase = 'final'
            if subtype == 'message' and payload.get('role') == 'assistant' and payload.get('channel') != 'analysis' and phase in ('commentary','final'):
                content = payload.get('content', [])
                text = '\n'.join(p.get('text', '') for p in content if isinstance(p, dict) and p.get('type') == 'output_text')
                if text:
                    event = {'kind':'message','name':phase,'text':clipped(text)}
            elif subtype in ('function_call','custom_tool_call'):
                call = payload.get('call_id')
                event = {'kind':'tool','name':str(payload.get('name') or 'tool'),
                         'text':clipped(payload.get('arguments', payload.get('input', ''))),
                         'call_id':call,'state':'requested'}
                if call:
                    state['calls'][call] = event
            elif subtype in ('function_call_output','custom_tool_call_output'):
                event_ref = state['calls'].pop(payload.get('call_id'), None)
                if event_ref is not None:
                    event_ref['state'] = 'returned'
                    event_ref['returned_at'] = stamp
                    state['last_activity'] = stamp
        if event is not None:
            event.update(line=state['line'], timestamp=stamp)
            if len(state['events']) == MAX_EVENTS:
                evicted = state['events'][0]
                state['calls'].pop(evicted.get('call_id'), None)
                state['history_truncated'] = True
            state['events'].append(event)
            state['last_activity'] = stamp

    def read(self, thread, query='', kind='', before=None, limit=100):
        if str(uuid.UUID(thread)) != thread:
            raise ValueError('Invalid conversation ID')
        with self.lock:
            state = self.cache.get(thread)
            path = state['path'] if state and state['path'].exists() else self._locate(thread)
            unavailable = {'thread_id':thread,'availability':'unavailable','events':[],
                           'model':None,'turn_status':'unknown','total':0,'has_more':False}
            if path is None or path.is_symlink():
                return unavailable
            stat = path.stat()
            if state is None or state['path'] != path or state['inode'] != stat.st_ino or stat.st_size < state['offset'] or (stat.st_size == state['offset'] and stat.st_mtime_ns != state['mtime']):
                with path.open('rb') as f:
                    try:
                        first = json.loads(f.readline())
                    except (ValueError, UnicodeError):
                        return unavailable
                if not isinstance(first, dict) or first.get('type') != 'session_meta' or first.get('payload', {}).get('id') != thread:
                    return unavailable
                state = {'path':path,'inode':stat.st_ino,'offset':0,'mtime':None,'line':0,
                         'model':None,'effort':None,'turn_status':'unknown','last_activity':None,
                         'events':deque(maxlen=MAX_EVENTS),'messages':deque(maxlen=200),'calls':{},'history_truncated':False}
                self.cache[thread] = state
            with path.open('rb') as f:
                f.seek(state['offset'])
                while True:
                    line = f.readline()
                    if not line or not line.endswith(b'\n'):
                        break  # Do not consume a partially appended record.
                    state['offset'] = f.tell()
                    state['line'] += 1
                    try:
                        row = json.loads(line)
                        if isinstance(row, dict):
                            self._consume(state, row)
                    except (ValueError, TypeError, UnicodeError):
                        continue
            state['mtime'] = stat.st_mtime_ns
            q = query.strip().lower()
            matches = [e for e in reversed(state['events']) if (not kind or e['kind'] == kind)
                       and (not q or q in (e['name']+' '+e['text']).lower())]
            page = [e for e in matches if before is None or e['line'] < before]
            limit = min(max(int(limit),1),200)
            return {'thread_id':thread,'availability':'available','model':state['model'],
                    'effort':state['effort'],'turn_status':state['turn_status'],
                    'last_activity':state['last_activity'],'source_path':str(path),
                    'events':[dict(e) for e in page[:limit]],'total':len(matches),
                    'has_more':len(page)>limit,'next_before':page[limit-1]['line'] if len(page)>limit else None,
                    'history_truncated':state['history_truncated']}

    def messages(self, thread):
        data = self.read(thread)
        with self.lock:
            state = self.cache.get(thread) if data['availability'] == 'available' else None
            return {'thread_id':thread, 'availability':data['availability'],
                    'messages':[dict(m) for m in reversed(state['messages'])] if state else []}
