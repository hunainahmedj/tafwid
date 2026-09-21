"""Provider-specific free-model preflight and configuration for OpenCode."""
import json
import os
from pathlib import Path
import re

from scout import fetch_json, OPENROUTER, ZEN, MODELS, zero_prices
import local_models

ZEN_PACKAGES = {'@ai-sdk/openai-compatible', '@ai-sdk/openai', '@ai-sdk/anthropic', '@ai-sdk/google'}


def provider_id(model):
    if re.fullmatch(r'local-[a-z][a-z0-9-]{0,47}/[A-Za-z0-9_./:@+-]+', model or ''):
        return model.split('/', 1)[0]
    if re.fullmatch(r'openrouter/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+:free', model or ''):
        return 'openrouter'
    if re.fullmatch(r'opencode/[A-Za-z0-9_.-]+', model or ''):
        return 'opencode'
    raise ValueError('Specify openrouter/provider/model:free, opencode/model, or local-NAME/model; no automatic fallback')


def model_info(model):
    provider = provider_id(model)
    if provider.startswith('local-'):
        return local_models.model_info(model)
    model_id = model.split('/', 1)[1]
    try:
        if provider == 'openrouter':
            return next((row for row in fetch_json(OPENROUTER)['data'] if row.get('id') == model_id), {})
        # Never use the scout cache to authorize a dispatch, including resumes.
        live = {row['id'] for row in fetch_json(ZEN)['data']}
        metadata = fetch_json(MODELS)['opencode']['models']
        if model_id not in live or model_id not in metadata:
            return {}
        row = metadata[model_id]
        cost = row.get('cost') or {}
        return {'id': model_id, 'pricing': {'prompt': cost.get('input'), 'completion': cost.get('output')},
                'supported_parameters': ['tools'] if row.get('tool_call') is True else [],
                'context_length': (row.get('limit') or {}).get('context'),
                'output_limit': (row.get('limit') or {}).get('output'),
                'npm': (row.get('provider') or {}).get('npm') or '@ai-sdk/openai-compatible',
                'reasoning': row.get('reasoning') is True,
                'catalogue_source': ZEN, 'price_capability_source': MODELS}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Cannot verify current model capabilities/pricing; no worker started') from exc


def validate_model(model, info):
    provider = provider_id(model)
    if info.get('id') != model.split('/', 1)[1]:
        raise ValueError('Selected model is absent from the current provider catalogue')
    if provider.startswith('local-'):
        profile = local_models.validate(info.get('local_connection'))
        if info.get('self_hosted') is not True or profile['model'] != info.get('id') or not profile['tool_call']:
            raise ValueError('Invalid local model capabilities')
    elif not zero_prices(info.get('pricing', {}), ('prompt', 'completion')):
        raise ValueError('Selected model does not have verified zero input/output pricing')
    if 'tools' not in (info.get('supported_parameters') or []):
        raise ValueError(f'{model} does not advertise tool calling; cannot run an OpenCode coding worker')
    if provider == 'opencode' and info.get('npm') not in ZEN_PACKAGES:
        raise ValueError('Unsupported Zen model transport; no worker started')


def check_auth(provider='openrouter'):
    if provider.startswith('local-'):
        return local_models.auth(local_models.connection(provider))
    env_name = 'OPENROUTER_API_KEY' if provider == 'openrouter' else 'OPENCODE_API_KEY'
    label = 'OpenRouter' if provider == 'openrouter' else 'OpenCode Zen'
    if os.environ.get(env_name):
        return 'environment'
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    try:
        auth = json.loads((data / 'opencode/auth.json').read_text()).get(provider, {})
        if auth.get('type') == 'api' and auth.get('key'):
            return 'opencode'
    except FileNotFoundError:
        pass
    except (OSError, ValueError, AttributeError):
        raise ValueError(f'Cannot read OpenCode authentication; run `opencode auth login` and select {label}') from None
    if provider == 'opencode':
        # OpenCode's native Zen loader uses this public access path for free models.
        # Availability/rate limits are still decided by Zen; never retry with a paid model.
        return 'public'
    raise ValueError(f'{label} is not configured. Run `opencode auth login` and select {label}, or set {env_name}; never paste a key into a task brief')


def provider_config(model, info):
    provider = provider_id(model)
    if provider.startswith('local-'):
        return local_models.provider_config(info)
    model_id = model.split('/', 1)[1]
    entry = {'id': model_id, 'name': model_id, 'tool_call': True,
             'limit': {'context': int(info.get('context_length') or 32768),
                       'output': min(4096, int(info.get('output_limit') or 4096))}}
    if provider == 'opencode':
        # Only known bundled SDKs are accepted. Never load a package or URL from
        # catalogue metadata without validation. Model-specific protocols vary.
        if info.get('npm') not in ZEN_PACKAGES:
            raise ValueError('Unsupported Zen model transport')
        entry['provider'] = {'npm': info['npm'], 'api': 'https://opencode.ai/zen/v1'}
        entry['reasoning'] = info.get('reasoning', False)
        return {'whitelist': [model_id], 'options': {'baseURL': 'https://opencode.ai/zen/v1'},
                'models': {model_id: entry}}
    entry['options'] = {'provider': {'allow_fallbacks': False, 'max_price': {'prompt': 0, 'completion': 0}}}
    return {'npm': '@openrouter/ai-sdk-provider', 'whitelist': [model_id],
            'options': {'baseURL': 'https://openrouter.ai/api/v1'}, 'models': {model_id: entry}}
