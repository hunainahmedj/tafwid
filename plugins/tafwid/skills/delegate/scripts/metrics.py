"""Normalize per-run usage without estimating missing tokens or subscription bills."""
from functools import lru_cache
import json
import math
from pathlib import Path

FIELDS = ('input', 'output', 'reasoning', 'cache_read', 'cache_write', 'cost_usd', 'duration_seconds')


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def claude_usage(result):
    usage = result.get('usage') or {}
    if not isinstance(usage, dict):
        usage = {}
    fields = {'input': 'input_tokens', 'output': 'output_tokens',
              'cache_read': 'cache_read_input_tokens', 'cache_write': 'cache_creation_input_tokens'}
    stats = {k: number(usage.get(v)) for k, v in fields.items()}
    duration = number(result.get('duration_ms'))
    stats.update(reasoning=None, cost_usd=number(result.get('total_cost_usd')),
                 cost_kind='api_equivalent', duration_seconds=duration / 1000 if duration is not None else None,
                 source='Claude result', scope='current invocation; may include helper models')
    return stats


def normalize(usage, backend):
    stats = {key: number(usage.get(key)) for key in FIELDS}
    stats.update(cost_kind='reported' if backend == 'opencode' else 'api_equivalent',
                 partial=usage.get('partial') if isinstance(usage.get('partial'), bool) else None,
                 source=usage.get('source') or ('OpenCode steps' if backend == 'opencode' else 'Claude result'),
                 scope=usage.get('scope') or ('current run; main-worker steps only, helpers may be absent'
                                             if backend == 'opencode' else 'current invocation; may include helper models'))
    return stats


@lru_cache(maxsize=1024)
def read_usage(path, size, modified, backend, kind):
    # Cache keyed by file signature: dashboard refreshes don't reparse artifacts.
    try:
        if size > 8_000_000:
            return {}
        data = json.loads(Path(path).read_text())
        if kind == 'result' and isinstance(data, dict) and data.get('type') == 'result':
            return claude_usage(data)
        if isinstance(data, dict) and isinstance(data.get('usage'), dict) and data['usage']:
            return normalize(data['usage'], backend)
    except (OSError, ValueError, TypeError):
        pass
    return {}


def for_record(record):
    backend = record.get('backend', 'claude')
    def contextual(usage):
        stats = normalize(usage, backend)
        failed = record.get('status') in ('error', 'interrupted', 'timeout')
        if (backend == 'opencode' and failed and stats['partial'] is None
                and all(stats[key] == 0 for key in FIELDS if key != 'duration_seconds')):
            # Early adapter versions initialized counters to zero even when no
            # step finished. Those failed-run zeros are not provider evidence.
            for key in FIELDS:
                stats[key] = None
            stats['scope'] += '; legacy default zeros are unverified'
        stats['partial'] = bool(stats['partial'] or failed)
        return stats
    if isinstance(record.get('usage'), dict) and record['usage']:
        return contextual(record['usage'])
    out = record.get('output_dir')
    if not out or record.get('status') in ('running', 'starting'):
        return {}
    for filename, kind in [('summary.json', 'summary')] + ([] if backend == 'opencode' else [('result.json', 'result')]):
        path = Path(out) / filename
        try:
            if path.is_symlink():
                continue
            stat = path.stat()
            found = read_usage(str(path), stat.st_size, stat.st_mtime_ns, backend, kind)
            if found:
                return contextual(found)
        except OSError:
            continue
    return {}
