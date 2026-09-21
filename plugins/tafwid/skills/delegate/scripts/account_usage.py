"""Read Claude's native subscription usage without sending model messages.

The control protocol is version-sensitive. Credentials remain owned by Claude;
only normalized quota observations and an opaque account fingerprint are saved.
"""
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import tempfile
import threading
import time

import paths

REFRESH_SECONDS = 60
HISTORY_SECONDS = 7 * 86400
MAX_HISTORY = 10080


def filename():
    return paths.state_root() / 'account-usage.json'


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def timestamp(value):
    try:
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                return None
            value = parsed.timestamp()
        return math.floor(value) if numeric(value) else None
    except (ValueError, OverflowError):
        return None


def normalize(data):
    if not isinstance(data, dict) or data.get('rate_limits_available') is not True:
        raise ValueError('Claude subscription limits unavailable')
    limits = data.get('rate_limits')
    if not isinstance(limits, dict):
        raise ValueError('Claude subscription limits unavailable')
    windows = []
    def add(key, label, row):
        if not isinstance(row, dict) or not numeric(row.get('utilization')):
            return
        value = row['utilization']
        if value > 100:
            return  # Subscription windows use 0..100; spend/credit caps are separate.
        windows.append({'key':key, 'label':label, 'used_percent':value,
                        'resets_at':timestamp(row.get('resets_at'))})
    add('five_hour', 'Five-hour allowance', limits.get('five_hour'))
    add('seven_day', 'Weekly allowance', limits.get('seven_day'))
    seen = set()
    for row in limits.get('model_scoped') or []:
        if not isinstance(row, dict):
            continue
        name = row.get('display_name')
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            continue
        key = name.strip().casefold()
        if key not in seen:
            add('model:' + key, name.strip() + ' allowance', row)
            seen.add(key)
    for model in ('opus', 'sonnet'):
        if model not in seen:
            add('model:' + model, model.title() + ' allowance', limits.get('seven_day_' + model))
    # New opaque/internal provider keys are not guessed to be model names.
    return {'subscription_type':data.get('subscription_type') if data.get('subscription_type') in
            ('pro', 'max', 'team', 'enterprise') else None, 'windows':windows}


def query_native(executable, timeout=20):
    command = [executable, '-p', '--input-format', 'stream-json', '--output-format', 'stream-json',
        '--verbose', '--no-session-persistence', '--setting-sources', '', '--strict-mcp-config',
        '--mcp-config', '{"mcpServers":{}}', '--tools', '', '--disable-slash-commands',
        '--settings', '{"disableAllHooks":true}']
    # --bare must NOT be used: it disables subscription/keychain authentication.
    with tempfile.TemporaryDirectory(prefix='tafwid-account-') as cwd:
        proc = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            for rid, request in [('initialize', {'subtype':'initialize'}),
                                 ('usage', {'subtype':'get_usage', 'skip_behaviors':True})]:
                proc.stdin.write((json.dumps({'type':'control_request','request_id':rid,'request':request})+'\n').encode())
            proc.stdin.flush()
            buffer = b''
            received = 0
            deadline = time.monotonic() + timeout
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                while time.monotonic() < deadline:
                    if not selector.select(min(.25, max(0, deadline-time.monotonic()))):
                        continue
                    chunk = os.read(proc.stdout.fileno(), 65536)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > 2_000_000:
                        raise ValueError('Claude usage response exceeded size limit')
                    buffer += chunk
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        try:
                            row = json.loads(line)
                        except (ValueError, UnicodeError):
                            continue
                        response = row.get('response') if isinstance(row, dict) else None
                        if not isinstance(row, dict) or row.get('type') != 'control_response' or not isinstance(response, dict):
                            continue
                        if response.get('request_id') != 'usage':
                            continue
                        if response.get('subtype') != 'success' or not isinstance(response.get('response'), dict):
                            raise ValueError('Claude usage control unavailable')
                        return response['response']
            raise ValueError('Claude usage query did not complete')
        finally:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=2)
            proc.stdin.close()
            proc.stdout.close()


def fetch_native():
    executable = shutil.which('claude')
    if not executable:
        raise ValueError('Claude Code is unavailable')
    with tempfile.TemporaryDirectory(prefix='tafwid-account-auth-') as cwd:
        result = subprocess.run([executable, 'auth', 'status'], cwd=cwd, capture_output=True, timeout=10)
    if result.returncode or len(result.stdout) > 100_000:
        raise ValueError('Claude subscription authentication unavailable')
    auth = json.loads(result.stdout)
    if (not isinstance(auth, dict) or auth.get('loggedIn') is not True
            or auth.get('authMethod') != 'claude.ai' or auth.get('apiProvider') != 'firstParty'
            or not isinstance(auth.get('email'), str) or not auth['email']):
        raise ValueError('Claude subscription authentication unavailable')
    account = json.dumps([auth.get('orgId'), auth['email']], separators=(',', ':'))
    data = normalize(query_native(executable))
    data['account_id'] = hashlib.sha256(account.encode()).hexdigest()[:24]
    return data


def valid_cache(saved):
    def windows(rows):
        return isinstance(rows, list) and len(rows) <= 64 and all(
            isinstance(w, dict) and isinstance(w.get('key'), str) and isinstance(w.get('label'), str)
            and numeric(w.get('used_percent')) and w['used_percent'] <= 100
            and (w.get('resets_at') is None or numeric(w['resets_at'])) for w in rows)
    return (saved.get('status') in ('available', 'stale', 'unavailable')
            and all(saved.get(key) is None or numeric(saved[key]) for key in ('observed_at','checked_at'))
            and (saved.get('account_id') is None or isinstance(saved['account_id'], str))
            and windows(saved.get('windows')) and isinstance(saved.get('history'), list)
            and len(saved['history']) <= MAX_HISTORY and all(isinstance(s, dict)
                and numeric(s.get('at')) and isinstance(s.get('account_id'), str)
                and windows(s.get('windows')) for s in saved['history']))


class AccountReader:
    def __init__(self, fetch=fetch_native, clock=time.time):
        self.fetch, self.clock = fetch, clock
        self.lock = threading.RLock()
        self.worker = None
        self.data = {'status':'unavailable', 'account_id':None, 'observed_at':None,
                     'checked_at':None, 'subscription_type':None, 'windows':[], 'history':[], 'error':None}
        try:
            path = filename()
            if not path.is_symlink() and path.stat().st_size <= 8_000_000:
                saved = json.loads(path.read_text())
                if (isinstance(saved, dict) and saved.get('version') == 1
                        and valid_cache(saved)):
                    self.data.update({key:saved[key] for key in self.data if key in saved})
        except (OSError, ValueError, TypeError):
            pass

    def snapshot(self):
        with self.lock:
            data = json.loads(json.dumps(self.data))
            now = self.clock()
            if data['observed_at'] is not None and (
                    now-data['observed_at'] > REFRESH_SECONDS*2 or
                    any(numeric(w.get('resets_at')) and w['resets_at'] <= now for w in data['windows'])):
                data['status'] = 'stale'
            if self.worker is not None and self.worker.is_alive() and data['observed_at'] is None:
                data['status'] = 'refreshing'
            data['history'] = [s for s in data['history'] if numeric(s.get('at')) and now-HISTORY_SECONDS <= s['at'] <= now]
            return data

    def refresh_now(self):
        from worker_registry import atomic_json
        try:
            fresh = self.fetch()
            now = self.clock()
            with self.lock:
                history = self.data['history'] if self.data['account_id'] == fresh['account_id'] else []
                history = [s for s in history if numeric(s.get('at')) and now-HISTORY_SECONDS <= s['at'] < now]
                history.append({'at':now,'account_id':fresh['account_id'],'windows':fresh['windows']})
                self.data.update(fresh, status='available', observed_at=now, checked_at=now,
                                 history=history[-MAX_HISTORY:], error=None)
        except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
            now = self.clock()
            with self.lock:
                self.data.update(status='stale' if self.data['observed_at'] is not None else 'unavailable',
                    checked_at=now, error='Could not refresh Claude subscription limits. Check Claude sign-in and version; no model request was made.')
        with self.lock:
            try:
                atomic_json(filename(), dict(self.data, version=1))
            except OSError:
                self.data['error'] = 'Account observations could not be saved; history may be incomplete.'

    def read(self):
        with self.lock:
            now = self.clock()
            checked = self.data['checked_at']
            if (self.worker is None or not self.worker.is_alive()) and (checked is None or checked > now or now-checked >= REFRESH_SECONDS):
                self.worker = threading.Thread(target=self.refresh_now, daemon=True)
                self.worker.start()
            return self.snapshot()
