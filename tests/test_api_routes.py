"""
API route smoke tests.
"""

import pytest
import time
from fastapi.testclient import TestClient

from app.main import app
from app.config.settings import AppConfig
import app.api.system_config as system_config_api
import app.api.quark as quark_api


client = TestClient(app)


class TestQuarkSDKRoutes:
    def test_sdk_status(self):
        response = client.get('/api/quark-sdk/status')
        assert response.status_code == 200
        data = response.json()
        assert 'available' in data

    def test_get_files_without_cookie(self):
        response = client.get('/api/quark-sdk/files/0')
        assert response.status_code in [200, 400, 500]


class TestSearchRoutes:
    def test_search_status(self):
        response = client.get('/api/search/status')
        assert response.status_code == 200
        data = response.json()
        assert 'available' in data

    def test_search_without_keyword(self):
        response = client.get('/api/search')
        assert response.status_code == 422


class TestRenameRoutes:
    def test_rename_status(self):
        response = client.get('/api/rename/status')
        assert response.status_code == 200
        data = response.json()
        assert 'available' in data

    def test_preview_rename_invalid_path(self):
        response = client.post('/api/rename/preview', json={
            'path': '/nonexistent/path',
            'recursive': True,
        })
        assert response.status_code in [200, 400, 500]


class TestExistingRoutes:
    def test_root(self):
        response = client.get('/')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'running'

    def test_health(self):
        response = client.get('/health')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'

    def test_existing_quark_routes(self):
        response = client.get('/api/quark/config')
        assert response.status_code == 200


class TestSystemConfigRoutes:
    def test_get_ai_models_config(self):
        response = client.get('/api/system-config/ai-models')
        assert response.status_code == 200
        body = response.json()
        assert 'kimi' in body
        assert 'deepseek' in body
        assert 'glm' in body
        assert 'configured' in body['glm']
        assert 'api_key_masked' in body['glm']

    def test_update_ai_models_config_keep_old_api_key_when_blank(self, monkeypatch):
        state = AppConfig()
        state.glm.api_key = 'glm-secret-abcdefgh'

        class StubConfigService:
            def get_config(self):
                return state

            def update_config(self, new_config):
                nonlocal state
                state = AppConfig.model_validate(new_config)
                return state

        monkeypatch.setattr(system_config_api, 'get_config_service', lambda *_args, **_kwargs: StubConfigService())

        payload = {
            'kimi': {
                'api_key': '',
                'base_url': 'https://integrate.api.nvidia.com/v1',
                'model': 'moonshotai/kimi-k2.5',
                'timeout': 8,
            },
            'deepseek': {
                'api_key': '',
                'base_url': 'https://api.deepseek.com/v1',
                'model': 'deepseek-chat',
                'timeout': 8,
            },
            'glm': {
                'api_key': '',
                'base_url': 'https://open.bigmodel.cn/api/paas/v4',
                'model': 'glm-4.7-flash',
                'timeout': 9,
            },
        }

        response = client.post('/api/system-config/ai-models', json=payload)
        assert response.status_code == 200
        assert state.glm.api_key == 'glm-secret-abcdefgh'
        assert state.glm.timeout == 9


class TestQuarkWorkflowTaskRoutes:
    def test_cloud_workflow_task_create_and_complete(self, monkeypatch):
        async def fake_preview(request, _cookie=None, _auth=None):
            return {
                'status': 200,
                'data': {
                    'batch_id': 'batch-test',
                    'pdir_fid': request.pdir_fid,
                    'total_items': 1,
                    'matched_items': 1,
                    'parsed_items': 0,
                    'needs_confirmation': 0,
                    'average_confidence': 0.95,
                    'algorithm_used': request.algorithm,
                    'naming_standard': request.naming_standard,
                    'items': [
                        {
                            'fid': 'fid-test',
                            'original_name': 'old.mkv',
                            'new_name': 'new.mkv',
                            'tmdb_id': 1,
                            'tmdb_title': 'Title',
                            'tmdb_year': 2024,
                            'media_type': 'movie',
                            'season': None,
                            'episode': None,
                            'overall_confidence': 0.95,
                            'used_algorithm': request.algorithm,
                            'needs_confirmation': False,
                            'confirmation_reason': None,
                            'status': 'matched',
                        }
                    ],
                },
            }

        async def fake_execute(request, _cookie=None, _auth=None):
            return {
                'status': 200,
                'data': {
                    'batch_id': request.batch_id,
                    'total': len(request.operations),
                    'success': len(request.operations),
                    'failed': 0,
                    'skipped': 0,
                    'results': [
                        {
                            'fid': op.fid,
                            'status': 'success',
                            'old_name': 'old.mkv',
                            'new_name': op.new_name,
                            'verified': True,
                        }
                        for op in request.operations
                    ],
                },
            }

        monkeypatch.setattr(quark_api, 'smart_rename_cloud_files', fake_preview)
        monkeypatch.setattr(quark_api, 'execute_cloud_rename', fake_execute)

        payload = {
            'pdir_fid': '0',
            'algorithm': 'ai_enhanced',
            'naming_standard': 'emby',
            'force_ai_parse': False,
            'auto_execute': True,
            'options': {'recursive': True, 'fast_mode': True},
        }
        create_resp = client.post('/api/quark/smart-rename-cloud/workflow-tasks', json=payload)
        assert create_resp.status_code == 200
        task_id = create_resp.json()['task_id']

        final_data = None
        for _ in range(30):
            status_resp = client.get(f'/api/quark/smart-rename-cloud/workflow-tasks/{task_id}')
            assert status_resp.status_code == 200
            data = status_resp.json()
            if data['status'] in {'completed', 'failed', 'cancelled'}:
                final_data = data
                break
            time.sleep(0.05)

        assert final_data is not None
        assert final_data['status'] == 'completed'
        assert final_data['execute']['total'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
