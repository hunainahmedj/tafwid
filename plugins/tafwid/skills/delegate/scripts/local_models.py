#!/usr/bin/env python3
"""Configure private LM Studio/vLLM connections for OpenCode workers."""
import argparse
import ipaddress
import json
import os
import re
import socket
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

import paths
from worker_registry import atomic_json

NETWORKS = tuple(ipaddress.ip_network(n) for n in (
    '127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
    '100.64.0.0/10', '::1/128', 'fc00::/7'))


def filename():
    return paths.state_root() / 'local-models.json'


def read():
    try:
        data = json.loads(filename().read_text())
    except FileNotFoundError:
        return {'version': 1, 'connections': {}}
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('connections'), dict):
        raise ValueError('Invalid local-models.json')
    return data


def validate(profile):
    if not isinstance(profile, dict) or set(profile) - {'api_key_file'} != {
            'kind', 'base_url', 'model', 'context_length', 'output_limit', 'tool_call', 'api_key_env'}:
        raise ValueError('Invalid local connection fields')
    if profile['kind'] not in ('lmstudio', 'vllm'):
        raise ValueError('Local connection kind must be lmstudio or vllm')
    if not isinstance(profile['model'], str) or not re.fullmatch(r'[A-Za-z0-9_./:@+-]+', profile['model']):
        raise ValueError('Invalid served model ID')
    for key in ('context_length', 'output_limit'):
        if type(profile[key]) is not int or profile[key] <= 0:
            raise ValueError('Context and output limits must be positive integers')
    if profile['output_limit'] >= profile['context_length']:
        raise ValueError('Output limit must be smaller than context length')
    if type(profile['tool_call']) is not bool:
        raise ValueError('Explicit tool_call capability required')
    key = profile['api_key_env']
    if key is not None and (not isinstance(key, str) or not re.fullmatch(r'[A-Z_][A-Z0-9_]*', key)):
        raise ValueError('Use an environment variable name, never an API key')
    key_file = profile.get('api_key_file')
    if key_file is not None and (not isinstance(key_file, str) or not Path(key_file).is_absolute()
                                 or any(c in key_file for c in '{}\n\r')):
        raise ValueError('API key file must be an absolute path')
    if key_file and key:
        raise ValueError('Choose either an API key file or environment variable')
    endpoint(profile['base_url'])
    return profile


def endpoint(value):
    """Private/loopback destinations only; never forward credentials on redirects."""
    if not isinstance(value, str):
        raise ValueError('Invalid local base URL')
    url = urlsplit(value)
    if (url.scheme not in ('http', 'https') or not url.hostname or url.username is not None
            or url.password is not None or url.query or url.fragment or url.path.rstrip('/') != '/v1'):
        raise ValueError('Use an http(s) private-server /v1 URL without credentials or query parameters')
    try:
        addresses = {ipaddress.ip_address(row[4][0]) for row in socket.getaddrinfo(
            url.hostname, url.port or (443 if url.scheme == 'https' else 80), type=socket.SOCK_STREAM)}
    except (OSError, ValueError):
        raise ValueError('Cannot resolve local inference host') from None
    if not addresses or any(not any(ip in net for net in NETWORKS) for ip in addresses):
        raise ValueError('Local inference requires loopback, LAN, or private overlay addresses')
    return value.rstrip('/')


def connection(provider):
    if not re.fullmatch(r'local-[a-z][a-z0-9-]{0,47}', provider):
        raise ValueError('Invalid local connection name')
    profile = read()['connections'].get(provider[6:])
    if profile is None:
        raise ValueError('Unknown local connection; configure it with local_models.py add')
    return validate(profile)


def auth(profile):
    name = profile['api_key_env']
    if name and not os.environ.get(name):
        raise ValueError(f'Local inference requires the configured {name} environment variable')
    if profile.get('api_key_file'):
        secret(profile)
        return 'file'
    return 'environment' if name else 'none'


def secret(profile):
    try:
        if profile.get('api_key_file'):
            with Path(profile['api_key_file']).open() as stream:
                value = stream.read(8193).strip()
        else:
            value = os.environ.get(profile['api_key_env'], '') if profile['api_key_env'] else ''
    except OSError:
        raise ValueError('Cannot read local inference API key file') from None
    if (profile.get('api_key_file') or profile['api_key_env']) and (
            not value or len(value) > 8192 or any(c.isspace() for c in value)):
        raise ValueError('Invalid or empty local inference credential')
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Local inference endpoint redirected; configure its direct address')


def model_info(model):
    provider, model_id = model.split('/', 1)
    profile = connection(provider)
    if model_id != profile['model']:
        raise ValueError('Model differs from the saved local connection')
    auth(profile)
    headers = {'Accept': 'application/json'}
    credential = secret(profile)
    if credential:
        headers['Authorization'] = 'Bearer ' + credential
    try:
        # Local requests must not pass through a configured HTTP proxy.
        with build_opener(ProxyHandler({}), NoRedirect()).open(
                Request(endpoint(profile['base_url']) + '/models', headers=headers), timeout=10) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('Local model list is too large')
        rows = json.loads(raw)['data']
        found = next((row for row in rows if row.get('id') == model_id), None)
    except HTTPError as exc:
        raise ValueError(f'Local model discovery returned HTTP {exc.code}; no worker started') from None
    except (URLError, OSError, KeyError, TypeError, AttributeError, json.JSONDecodeError):
        raise ValueError('Cannot read local /v1/models; check server and connection settings') from None
    if found is None:
        raise ValueError('Selected model is absent from the local server')
    maximum = found.get('max_model_len')
    if isinstance(maximum, int) and profile['context_length'] > maximum:
        raise ValueError('Configured context exceeds the server context limit')
    if not profile['tool_call']:
        raise ValueError('Local worker needs explicitly configured tool calling; verify server support first')
    return {'id': model_id, 'context_length': profile['context_length'],
            'output_limit': profile['output_limit'], 'supported_parameters': ['tools'],
            'capability_source': 'user-configured; model listing does not prove tool support',
            'local_connection': profile, 'self_hosted': True}


def provider_config(info):
    profile = validate(info['local_connection'])
    options = {'baseURL': endpoint(profile['base_url'])}
    # The placeholder is resolved by OpenCode; only its name appears in artifacts.
    options['apiKey'] = '{env:' + profile['api_key_env'] + '}' if profile['api_key_env'] else 'local'
    if profile.get('api_key_file'):
        options['apiKey'] = '{file:' + profile['api_key_file'] + '}'
    return {'npm': '@ai-sdk/openai-compatible', 'name': profile['kind'] + ' (self-hosted)',
            'whitelist': [profile['model']], 'options': options,
            'models': {profile['model']: {'id': profile['model'], 'name': profile['model'],
                'tool_call': True, 'limit': {'context': profile['context_length'], 'output': profile['output_limit']}}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('list')
    add = sub.add_parser('add')
    add.add_argument('--name', required=True)
    add.add_argument('--kind', choices=('lmstudio', 'vllm'), required=True)
    add.add_argument('--base-url', required=True)
    add.add_argument('--model', required=True)
    add.add_argument('--context', type=int, required=True, help='Actual configured server context limit')
    add.add_argument('--output', type=int, default=4096)
    add.add_argument('--tools', action='store_true', help='Declare server tool-call support; verify with a trial')
    add.add_argument('--api-key-env', help='Environment variable name; never enter the key here')
    add.add_argument('--api-key-file', help='Path to a private file containing only the API key')
    check = sub.add_parser('check')
    check.add_argument('--name', required=True)
    args = parser.parse_args()
    try:
        data = read()
        if args.action == 'add':
            if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', args.name):
                raise ValueError('Connection name must start with a lowercase letter and use letters, digits, hyphens')
            profile = validate({'kind': args.kind, 'base_url': args.base_url.rstrip('/'), 'model': args.model,
                'context_length': args.context, 'output_limit': args.output, 'tool_call': args.tools,
                'api_key_env': args.api_key_env,
                'api_key_file': str(Path(args.api_key_file).expanduser().resolve()) if args.api_key_file else None})
            data['connections'][args.name] = profile
            atomic_json(filename(), data)
        elif args.action == 'check':
            profile = connection('local-' + args.name)
            data = model_info('local-' + args.name + '/' + profile['model'])
        print(json.dumps(data, indent=2))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
