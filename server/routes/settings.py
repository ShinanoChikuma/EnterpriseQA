from flask import Blueprint, request

from services.api_settings_service import (
    fetch_model_options,
    get_api_settings_payload,
    save_api_settings,
)
from services.maintenance_service import MaintenanceService
from utils.response import error, success


settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/api', methods=['GET'])
def get_api_settings():
    return success(get_api_settings_payload())


@settings_bp.route('/api/models', methods=['GET'])
def get_api_models():
    provider = request.args.get('provider')
    api_key = (request.args.get('api_key') or '').strip()

    if not provider:
        return error('请选择 API 来源')

    try:
        options = fetch_model_options(provider, api_key=api_key)
    except ValueError as exc:
        return error(str(exc))

    return success({
        'provider': provider,
        'options': options,
    })


@settings_bp.route('/api', methods=['PUT'])
def update_api_settings():
    data = request.get_json() or {}

    api_source = data.get('api_source')
    api_key = (data.get('api_key') or '').strip()
    model = data.get('model')

    if not api_source:
        return error('请选择 API 来源')
    if not api_key:
        return error('请输入 API 密钥')
    if not model:
        return error('请选择模型')

    existing_settings = get_api_settings_payload()['settings']
    api_keys = dict(existing_settings.get('api_keys') or {})
    submitted_api_keys = data.get('api_keys') or {}
    if isinstance(submitted_api_keys, dict):
        for key, value in submitted_api_keys.items():
            api_keys[key] = str(value or '').strip()

    api_keys[api_source] = api_key

    settings = save_api_settings({
        'api_source': api_source,
        'api_key': api_key,
        'api_keys': api_keys,
        'model': model,
    })
    return success(settings, '保存成功')


@settings_bp.route('/maintenance/format-database', methods=['POST'])
def format_database():
    try:
        result = MaintenanceService().format_database()
    except Exception as exc:
        return error(f'格式化数据库失败: {exc}')

    return success(result, '格式化数据库成功')
