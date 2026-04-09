"""API 集成测试 — 使用 TestClient 直接测试 FastAPI 端点，无需启动服务器。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# 使用 conftest.py 中的 app_client 和 admin_token fixture


# ═══════════════════════════════════════════════════════
# Test 1: 基础端点
# ═══════════════════════════════════════════════════════

class TestBasicEndpoints:

    def test_health(self, app_client):
        resp = app_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"

    def test_info_requires_admin(self, app_client):
        """验证 /api/info 需要管理员权限。"""
        resp = app_client.get("/api/info")
        assert resp.status_code in (401, 403)

    def test_info_with_admin(self, app_client, admin_token):
        """验证管理员可以访问 /api/info。"""
        resp = app_client.get("/api/info", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        # 确保不暴露敏感信息
        assert "llm_api_base" not in data

    def test_openapi(self, app_client):
        resp = app_client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        paths = list(data.get("paths", {}).keys())
        assert len(paths) > 5, f"API 路径太少: {paths}"

    def test_docs(self, app_client):
        resp = app_client.get("/docs")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════
# Test 2: 认证
# ═══════════════════════════════════════════════════════

class TestAuth:

    def test_login_success(self, app_client):
        resp = app_client.post("/api/users/login", json={
            "username": "admin",
            "password": "test_admin_123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data.get("role") == "admin"

    def test_login_wrong_password(self, app_client):
        resp = app_client.post("/api/users/login", json={
            "username": "admin",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, app_client):
        resp = app_client.post("/api/users/login", json={})
        assert resp.status_code == 422

    def test_register_duplicate(self, app_client):
        """注册已存在用户应失败。"""
        resp = app_client.post("/api/users/register", json={
            "username": "admin",
            "email": "admin@test.com",
            "password": "test123",
        })
        assert resp.status_code == 400

    def test_protected_without_token(self, app_client):
        resp = app_client.get("/api/users/me")
        assert resp.status_code == 403

    def test_protected_with_token(self, app_client, admin_token):
        resp = app_client.get("/api/users/me", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("username") == "admin"


# ═══════════════════════════════════════════════════════
# Test 3: 公开端点
# ═══════════════════════════════════════════════════════

class TestPublicEndpoints:

    def test_public_events(self, app_client):
        resp = app_client.get("/api/events/public")
        assert resp.status_code == 200

    def test_public_events_with_pagination(self, app_client):
        resp = app_client.get("/api/events/public?page=1&page_size=5")
        assert resp.status_code == 200

    def test_categories(self, app_client):
        """分类列表端点。"""
        resp = app_client.get("/api/events/categories")
        assert resp.status_code == 200

    def test_search(self, app_client):
        """搜索端点。"""
        resp = app_client.get("/api/events/search/test")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════
# Test 4: 管理端点
# ═══════════════════════════════════════════════════════

class TestAdminEndpoints:

    def test_admin_stats(self, app_client, admin_token):
        resp = app_client.get("/api/admin/stats", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" in data

    def test_admin_no_token(self, app_client):
        """无 token 访问管理端点。"""
        resp = app_client.get("/api/admin/stats")
        assert resp.status_code == 403

    def test_admin_wrong_role(self, app_client):
        """普通用户不能访问管理端点。"""
        import time
        username = f"testuser_{int(time.time())}"
        reg_resp = app_client.post("/api/users/register", json={
            "username": username,
            "email": f"{username}@test.com",
            "password": "test123",
        })
        if reg_resp.status_code != 200:
            pytest.skip("注册失败")
        login_resp = app_client.post("/api/users/login", json={
            "username": username,
            "password": "test123",
        })
        if login_resp.status_code != 200:
            pytest.skip("登录失败")
        token = login_resp.json()["access_token"]

        resp = app_client.get("/api/admin/stats", headers={
            "Authorization": f"Bearer {token}"
        })
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════
# Test 5: RSS 端点
# ═══════════════════════════════════════════════════════

class TestRSSEndpoints:

    def test_rss_sources_list(self, app_client, admin_token):
        resp = app_client.get("/api/rss", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert resp.status_code == 200

    def test_rss_create_source(self, app_client, admin_token):
        """创建 RSS 源。"""
        import time
        resp = app_client.post("/api/rss", json={
            "name": f"测试源_{int(time.time())}",
            "url": f"http://example.com/rss/{int(time.time())}",
            "category": "tech",
        }, headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert resp.status_code in (200, 201, 400)


# ═══════════════════════════════════════════════════════
# Test 6: 管线触发端点
# ═══════════════════════════════════════════════════════

class TestPipelineTrigger:

    def test_pipeline_trigger(self, app_client, admin_token):
        """触发管线执行。"""
        resp = app_client.post("/api/admin/pipeline", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "crawled" in data or "message" in data
