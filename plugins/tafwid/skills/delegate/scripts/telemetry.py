"""Bounded, metadata-only worker usage observations from registered artifacts.

Consumption is per completed message/step. Context is that same request's observed
input/cache/output occupancy, never a cumulative session sum or a guessed baseline.
"""
from collections import OrderedDict
from datetime import datetime
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import time
import threading

from metrics import number

MAX_BYTES = 8 * 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024
MAX_SAMPLES = 2048
TOKEN_FIELDS = ('input', 'output', 'cache_read', 'cache_write')
# Keep typical histories (many small worker sessions) warm across dashboard polls,
# but bound normalized sample memory independently of the number of files. Only
# the newest signature for each registered file is retained as workers append.
CACHE_FILES = 256
CACHE_SAMPLES = 32768
_sample_cache = OrderedDict()
_cache_lock = threading.Lock()
_cached_sample_count = 0


def timestamp(value):
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                return None
            value = parsed.timestamp()
        except (ValueError, OverflowError, OSError):
            return None
    value = number(value)
    if value is None:
        return None
    # OpenCode JSON events use milliseconds; registry times use seconds.
    if value >= 100_000_000_000:
        value /= 1000
    return value if 0 < value < 253_402_300_800 else None


def mapping(value):
    return value if isinstance(value, dict) else {}


def identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,250}', value) else None


def signature(path):
    try:
        if path.is_symlink() or not path.is_file():
            return None
        stat = path.stat()
        return (str(path), stat.st_size, stat.st_mtime_ns, stat.st_ino)
    except OSError:
        return None


@lru_cache(maxsize=64)
def evidence(path, size, modified, inode, backend):
    """Cache only selected model/limit metadata, never raw request or result data."""
    try:
        if size > MAX_LINE_BYTES:
            return None, {}
        with Path(path).open('rb') as stream:
            data = mapping(json.loads(stream.read(MAX_LINE_BYTES)))
        if backend == 'opencode':
            config = mapping(data.get('config'))
            model = identifier(config.get('model'))
            if not model or '/' not in model:
                return None, {}
            provider, model_id = model.split('/', 1)
            entry = mapping(mapping(mapping(config.get('provider')).get(provider)).get('models')).get(model_id)
            limit = number(mapping(mapping(entry).get('limit')).get('context'))
            return model, {model: limit} if limit else {}
        limits = {}
        for model, values in mapping(data.get('modelUsage')).items():
            limit = number(mapping(values).get('contextWindow'))
            if identifier(model) and limit:
                limits[model] = limit
        return None, limits
    except (OSError, ValueError, TypeError, RecursionError):
        return None, {}


def model_evidence(record):
    backend = record.get('backend', 'claude')
    out = Path(record['output_dir'])
    files = ['request.json'] if backend == 'opencode' else ['result.json', 'summary.json']
    limits = {}
    selected = None
    for name in files:
        sig = signature(out / name)
        if sig:
            model, found = evidence(*sig, backend)
            selected = selected or model
            for key, value in found.items():
                limits.setdefault(key, value)
    return selected, limits


def observation(row, backend, session, cwd):
    """Return usage-only data plus a flag for an unusable expected sample."""
    if backend == 'opencode':
        if row.get('type') != 'step_finish':
            return None, False
        part = mapping(row.get('part'))
        if (row.get('sessionID') not in (None, session)
                or part.get('sessionID') not in (None, session)):
            return None, True
        ident = identifier(part.get('id')) or identifier(part.get('messageID'))
        tokens = mapping(part.get('tokens'))
        cache = mapping(tokens.get('cache'))
        fields = {'input': tokens.get('input'), 'output': tokens.get('output'),
                  'cache_read': cache.get('read'), 'cache_write': cache.get('write')}
        model = identifier(part.get('model'))
    else:
        if row.get('type') != 'assistant' or row.get('isSidechain') is True:
            return None, False
        if row.get('sessionId') not in (None, session) or row.get('cwd') not in (None, cwd):
            return None, True
        message = mapping(row.get('message'))
        ident = identifier(message.get('id'))
        tokens = mapping(message.get('usage'))
        fields = {'input': tokens.get('input_tokens'), 'output': tokens.get('output_tokens'),
                  'cache_read': tokens.get('cache_read_input_tokens'),
                  'cache_write': tokens.get('cache_creation_input_tokens')}
        model = identifier(message.get('model'))
    at = timestamp(row.get('timestamp'))
    if not ident or at is None:
        return None, True
    sample = {key: number(value) for key, value in fields.items()}
    sample.update(id=f'{backend}:{session}:{ident}', at=at, model=model)
    return sample, any(sample[key] is None for key in TOKEN_FIELDS)


def read_samples(path, size, modified, inode, backend, session, cwd):
    global _cached_sample_count
    key = (path, backend, session, cwd)
    version = (size, modified, inode)
    with _cache_lock:
        previous = _sample_cache.get(key)
        if previous and previous[0] == version:
            _sample_cache.move_to_end(key)
            return previous[1]
    result = parse_samples(path, size, backend, session, cwd)
    with _cache_lock:
        previous = _sample_cache.pop(key, None)
        if previous:
            _cached_sample_count -= len(previous[1][0])
        _sample_cache[key] = (version, result)
        _cached_sample_count += len(result[0])
        while len(_sample_cache) > CACHE_FILES or _cached_sample_count > CACHE_SAMPLES:
            _, removed = _sample_cache.popitem(last=False)
            _cached_sample_count -= len(removed[1][0])
    return result


def parse_samples(path, size, backend, session, cwd):
    """Read a bounded tail and retain only a bounded number of normalized samples."""
    samples = {}
    truncated = size > MAX_BYTES
    partial = truncated
    try:
        with Path(path).open('rb') as stream:
            remaining = MAX_BYTES
            if truncated:
                stream.seek(size - MAX_BYTES)
                # Discard any cut first record within the same byte budget.
                remaining -= len(stream.readline(min(MAX_LINE_BYTES + 1, remaining)))
            while remaining > 0:
                line = stream.readline(min(MAX_LINE_BYTES + 1, remaining))
                if not line:
                    break
                remaining -= len(line)
                if len(line) > MAX_LINE_BYTES:
                    partial = truncated = True
                    # Skip the rest of an oversized record without unbounded reads.
                    while not line.endswith(b'\n') and remaining > 0:
                        line = stream.readline(min(MAX_LINE_BYTES + 1, remaining))
                        if not line:
                            break
                        remaining -= len(line)
                    continue
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        partial = True
                        continue
                    sample, invalid = observation(row, backend, session, cwd)
                    partial = partial or invalid
                    if sample:
                        # Claude streaming blocks repeat one message ID. The last
                        # block contains final usage; counting blocks inflates cost.
                        samples.pop(sample['id'], None)
                        samples[sample['id']] = sample
                        if len(samples) > MAX_SAMPLES:
                            samples.pop(next(iter(samples)))
                            partial = truncated = True
                except (ValueError, TypeError, RecursionError):
                    partial = True
                    truncated = truncated or not line.endswith(b'\n')
    except OSError:
        return (), True, truncated
    return tuple(samples.values()), partial, truncated


def transcript_path(record):
    session, cwd = record.get('session_id'), record.get('cwd')
    if not isinstance(session, str) or not re.fullmatch(r'[0-9a-fA-F-]{36}', session):
        return None
    if not isinstance(cwd, str) or not cwd.startswith('/'):
        return None
    root = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude').expanduser()
    project = root / 'projects' / re.sub(r'[^a-zA-Z0-9]', '-', cwd)
    if project.is_symlink():
        return None
    # Do not scan projects, subagents, or unrelated sessions to fill missing data.
    return project / (session + '.jsonl')


def for_record(record):
    backend = record.get('backend', 'claude')
    result = {'samples': [], 'source': 'OpenCode step events' if backend == 'opencode' else 'Claude session transcript',
              'truncated': False, 'coverage': 'unavailable'}
    if backend not in ('claude', 'opencode'):
        return result
    start = timestamp(record.get('started_at'))
    end = timestamp(record.get('ended_at'))
    active = record.get('status') in ('running', 'starting')
    if start is None or (not active and end is None) or (end is not None and end < start):
        return result
    session = identifier(record.get('session_id'))
    if not session or not record.get('output_dir'):
        return result
    path = Path(record['output_dir']) / 'events.jsonl' if backend == 'opencode' else transcript_path(record)
    sig = signature(path) if path else None
    if not sig:
        return result
    samples, partial, truncated = read_samples(*sig, backend, session, record.get('cwd'))
    selected, limits = model_evidence(record)
    until = end if end is not None else time.time()
    for sample in samples:
        # Resume runs share the full Claude transcript. Each invocation owns only
        # the observations between its own recorded start and completion.
        if not start <= sample['at'] < until:
            continue
        sample = dict(sample)
        model = sample['model'] or selected
        sample['model'] = model
        limit = limits.get(model)
        context = sum(sample[key] for key in TOKEN_FIELDS) if all(sample[key] is not None for key in TOKEN_FIELDS) else None
        sample.update(context_tokens=context, context_limit=limit,
                      context_percent=context * 100 / limit if context is not None and limit else None)
        result['samples'].append(sample)
    result['samples'].sort(key=lambda sample: (sample['at'], sample['id']))
    result['truncated'] = truncated
    if result['samples']:
        result['coverage'] = 'partial' if partial or record.get('status') in ('running', 'starting', 'interrupted', 'error', 'timeout') else 'complete'
    elif partial:
        result['coverage'] = 'partial'
    return result
