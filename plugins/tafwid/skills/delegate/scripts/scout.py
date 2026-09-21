#!/usr/bin/env python3
"""Read-only free-model scouting. Fetch/cache metadata; never invoke inference."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen

import paths
import worker_registry

OPENROUTER = 'https://openrouter.ai/api/v1/models'
ZEN = 'https://opencode.ai/zen/v1/models'
MODELS = 'https://models.dev/api.json'
TTL = 21600
TASKS = ('implementation', 'debugging', 'documentation', 'review', 'architecture', 'vision')


def fetch_json(url):
    request = Request(url, headers={'User-Agent': 'Tafwid model-scout', 'Accept': 'application/json'})
    with urlopen(request, timeout=20) as response:
        # Catalogues are data, never instructions. Bound the response size.
        raw = response.read(20_000_001)
    if len(raw) > 20_000_000:
        raise ValueError('Catalogue exceeds size limit')
    return json.loads(raw)


def zero_prices(prices, keys):
    try:
        return all(not isinstance(prices[k], bool) and float(prices[k]) == 0 for k in keys)
    except (KeyError, TypeError, ValueError):
        return False


def candidate(model, name, tools, reasoning, context, modalities, provider, source):
    context = context if isinstance(context, int) and not isinstance(context, bool) and context > 0 else None
    tasks = ['documentation']
    reasons = ['Text documentation drafts are candidates only; verify claims against source.']
    if tools:
        tasks += ['implementation', 'debugging', 'review']
        reasons.append('Advertised tool calling: eligible for bounded edits, diagnostics and review trials.')
    if tools and reasoning and context and context >= 64000:
        tasks.append('architecture')
        reasons.append('Reasoning support and >=64k context: candidate for architecture analysis, not proven quality.')
    if 'image' in modalities:
        tasks.append('vision')
        reasons.append('Advertised image input; browser/computer control is a separate harness capability.')
    return {'model': model, 'name': str(name or model)[:160], 'provider': provider,
            'tools': tools, 'reasoning': reasoning, 'context': context,
            'task_candidates': tasks, 'reasons': reasons, 'confidence': 'metadata_only',
            'tested': False, 'price_source': source, 'input_price': 0, 'output_price': 0,
            'dispatch': 'preflight_required' if tools else 'tool_support_unverified'}


def openrouter_models(data):
    rows = []
    for row in data['data']:
        model = row.get('id', '')
        # Exclude the random free router and unspecified/paid variants.
        if not model.endswith(':free') or not zero_prices(row.get('pricing', {}), ('prompt', 'completion')):
            continue
        params = row.get('supported_parameters') or []
        rows.append(candidate('openrouter/' + model, row.get('name'), 'tools' in params,
            'reasoning' in params, row.get('context_length'),
            (row.get('architecture') or {}).get('input_modalities') or [], 'openrouter', OPENROUTER))
    return rows


def zen_models(data, metadata):
    live = {r['id'] for r in data['data']}
    rows = []
    for model, row in metadata['opencode']['models'].items():
        if model not in live or not zero_prices(row.get('cost', {}), ('input', 'output')):
            continue
        rows.append(candidate('opencode/' + model, row.get('name'), row.get('tool_call') is True,
            row.get('reasoning') is True, (row.get('limit') or {}).get('context'),
            (row.get('modalities') or {}).get('input') or [], 'zen', 'models.dev'))
    return rows


def catalogue(provider, refresh=False, now=None):
    now = time.time() if now is None else now
    path = paths.state_root() / 'scout' / (provider + '.json')
    previous = None
    try:
        previous = json.loads(path.read_text())
        if (previous.get('version') != 2 or previous.get('provider') != provider
                or not isinstance(previous.get('models'), list)
                or not isinstance(previous.get('checked_at'), (int, float))):
            previous = None
    except (OSError, ValueError, AttributeError):
        pass
    if previous and not refresh and 0 <= now - previous['checked_at'] < TTL:
        return {**previous, 'cached': True, 'stale': False}
    try:
        rows = openrouter_models(fetch_json(OPENROUTER)) if provider == 'openrouter' else zen_models(fetch_json(ZEN), fetch_json(MODELS))
        result = {'version': 2, 'provider': provider, 'checked_at': now, 'models': rows,
                  'sources': [OPENROUTER] if provider == 'openrouter' else [ZEN, MODELS]}
        worker_registry.atomic_json(path, result)
        return {**result, 'cached': False, 'stale': False}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {**(previous or {'provider': provider, 'models': [], 'checked_at': None}),
                'cached': bool(previous), 'stale': True,
                'error': 'Catalogue refresh failed; retained metadata is not current availability.'}


def shortlist(rows, runs, limit=5, task=None):
    counts = {}
    for run in runs:
        model = (run.get('model_selection') or {}).get('requested_model')
        counts.setdefault(model, Counter())[run.get('status', 'unknown')] += 1
    selected = []
    for row in rows:
        if task and task not in row['task_candidates']:
            continue
        selected.append({**row, 'observed_runs': dict(counts.get(row['model'], {}))})
    # Deterministic shortlist, not a benchmark leaderboard. Failures lower priority;
    # a completed launcher status is never promoted to independently tested quality.
    def priority(row):
        outcomes = row['observed_runs']
        failures = sum(n for k, n in outcomes.items() if k not in ('completed', 'running', 'starting'))
        return (not row['tools'], failures > 0, -outcomes.get('completed', 0), row['model'])
    return sorted(selected, key=priority)[:limit]


def auth_configured(provider):
    key = 'openrouter' if provider == 'openrouter' else 'opencode'
    env_key = 'OPENROUTER_API_KEY' if provider == 'openrouter' else 'OPENCODE_API_KEY'
    if os.environ.get(env_key):
        return True
    try:
        data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
        entry = json.loads((data / 'opencode/auth.json').read_text()).get(key, {})
        return bool(entry.get('type') == 'api' and entry.get('key'))
    except FileNotFoundError:
        return False
    except (OSError, ValueError, AttributeError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=('openrouter', 'zen', 'all'), default='all')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--limit', type=int, choices=range(1, 21), default=5, metavar='1..20')
    parser.add_argument('--task', choices=TASKS)
    args = parser.parse_args()
    reports = []
    runs = worker_registry.list_runs()
    for provider in ('openrouter', 'zen') if args.provider == 'all' else (args.provider,):
        result = catalogue(provider, args.refresh)
        rows = result.pop('models')
        result.update(listed_free_models=len(rows), auth_configured=auth_configured(provider),
                      shortlist=shortlist(rows, runs, args.limit, args.task))
        reports.append(result)
    print(json.dumps({'providers': reports, 'inference_requests': 0,
        'note': 'Candidate mappings only; no settings changed. Listed/authenticated does not prove a request will succeed. '
                'Local run statuses are not acceptance evidence. OpenRouter and Zen workers '
                'require a fresh launch preflight. Free offers and account limits may change.'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
