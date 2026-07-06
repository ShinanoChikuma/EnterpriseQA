import json
import os
import urllib.error
import urllib.parse
import urllib.request

from flask import current_app


PROVIDER_OPTIONS = [
    {'label': 'DeepSeek', 'value': 'deepseek'},
]

PROVIDER_LABELS = {
    'deepseek': 'DeepSeek',
}

MODEL_API_CONFIG = {
    'deepseek': {
        'url': 'https://api.deepseek.com/models',
    },
}


def _default_settings():
    deepseek_api_key = current_app.config.get('DEEPSEEK_API_KEY', '').strip()
    return {
        'api_source': 'deepseek',
        'api_key': deepseek_api_key,
        'api_keys': {
            'deepseek': deepseek_api_key,
        },
        'model': current_app.config.get('DEEPSEEK_CHAT_MODEL', 'deepseek-chat').strip(),
        'embed_model': current_app.config.get('DEEPSEEK_EMBED_MODEL', 'deepseek-embedding').strip(),
    }


def _settings_file():
    return current_app.config['API_SETTINGS_FILE']


def _normalize_provider(provider):
    provider = str(provider or '').strip().lower()
    if provider not in MODEL_API_CONFIG:
        return _default_settings()['api_source']
    return provider


def _normalize_model(model, provider):
    model = str(model or '').strip()
    if model:
        return model

    if provider == 'deepseek':
        return current_app.config.get('DEEPSEEK_CHAT_MODEL', 'deepseek-chat').strip()

    return ''


def _normalize_settings(data):
    defaults = _default_settings()
    raw_data = data or {}

    api_source = _normalize_provider(raw_data.get('api_source', defaults['api_source']))

    api_keys = dict(defaults['api_keys'])
    saved_api_keys = raw_data.get('api_keys') or {}
    if isinstance(saved_api_keys, dict):
        for provider in MODEL_API_CONFIG:
            api_keys[provider] = str(saved_api_keys.get(provider, api_keys.get(provider, '')) or '').strip()

    legacy_api_key = str(raw_data.get('api_key', '') or '').strip()
    if legacy_api_key and not api_keys.get(api_source):
        api_keys[api_source] = legacy_api_key

    if not api_keys.get('deepseek'):
        api_keys['deepseek'] = defaults['api_keys']['deepseek']

    model = _normalize_model(raw_data.get('model', defaults['model']), api_source)
    embed_model = str(raw_data.get('embed_model', defaults.get('embed_model', 'deepseek-embedding'))).strip()
    api_key = api_keys.get(api_source, '')

    return {
        'api_source': api_source,
        'api_key': api_key,
        'api_keys': api_keys,
        'model': model,
        'embed_model': embed_model,
    }


def load_api_settings():
    path = _settings_file()
    if not os.path.exists(path):
        return _default_settings()

    try:
        with open(path, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return _default_settings()

    return _normalize_settings(data)


def save_api_settings(data):
    settings = _normalize_settings(data)
    path = _settings_file()

    with open(path, 'w', encoding='utf-8') as file:
        json.dump(settings, file, ensure_ascii=False, indent=2)

    return settings


def _get_provider_api_key(provider, api_key=''):
    provider = _normalize_provider(provider)
    direct_api_key = str(api_key or '').strip()
    if direct_api_key:
        return direct_api_key

    settings = load_api_settings()
    saved_api_keys = settings.get('api_keys') or {}
    provider_api_key = str(saved_api_keys.get(provider, '') or '').strip()
    if provider_api_key:
        return provider_api_key

    if provider == 'deepseek':
        return current_app.config.get('DEEPSEEK_API_KEY', '').strip()

    return ''


def _request_model_list(provider, api_key):
    provider = _normalize_provider(provider)
    provider_label = PROVIDER_LABELS[provider]

    if not api_key:
        raise ValueError(f'请先输入 {provider_label} API 密钥')

    config = MODEL_API_CONFIG[provider]
    request = urllib.request.Request(
        url=config['url'],
        headers={
            'Accept': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='GET',
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        raise ValueError(f'{provider_label} 模型列表获取失败: {detail or exc.reason}') from exc
    except urllib.error.URLError as exc:
        raise ValueError(f'{provider_label} 连接失败: {exc.reason}') from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f'{provider_label} 模型列表返回了无效 JSON') from exc


def fetch_model_options(provider, api_key=''):
    provider = _normalize_provider(provider)
    provider_api_key = _get_provider_api_key(provider, api_key)
    payload = _request_model_list(provider, provider_api_key)

    models = payload.get('data')
    if not isinstance(models, list):
        raise ValueError(f'{PROVIDER_LABELS[provider]} 模型列表格式异常')

    options = []
    seen = set()
    for item in models:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get('id') or '').strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        options.append({
            'label': model_id,
            'value': model_id,
        })

    if not options:
        raise ValueError(f'{PROVIDER_LABELS[provider]} 未返回可用模型')

    return options


def get_api_settings_payload():
    settings = load_api_settings()
    return {
        'settings': settings,
        'api_source_options': PROVIDER_OPTIONS,
    }
