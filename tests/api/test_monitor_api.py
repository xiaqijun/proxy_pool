# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     test_monitor_api.py
   Description :   监控工作台 API 测试
   Author :        JHao
   date：          2026/10/26
-------------------------------------------------
   Change Activity:
                   2026/10/26:
-------------------------------------------------
"""
__author__ = 'JHao'

from helper.proxy import Proxy


def _login(client, username="admin", password="test-password"):
    return client.post(
        "/dashboard/api/login",
        json={"username": username, "password": password},
    )


def _proxy_list():
    return [
        Proxy("1.1.1.1:80", source="srcA", region="CN", https=False,
              fail_count=0, check_count=10, last_time="2026-10-26 10:00:00"),
        Proxy("2.2.2.2:443", source="srcB/srcA", region="US", https=True,
              fail_count=2, check_count=20, last_time="2026-10-26 11:00:00"),
        Proxy("3.3.3.3:8080", source="srcB", region="CN", https=False,
              fail_count=1, check_count=5, last_time="2026-10-26 09:00:00"),
    ]


class TestMonitorAuth:

    def test_requires_login(self, client):
        resp = client.get("/dashboard/api/overview")
        assert resp.status_code == 401

    def test_wrong_login(self, client):
        resp = _login(client, password="wrong")
        assert resp.status_code == 401

    def test_non_ascii_password(self, client, monkeypatch):
        monkeypatch.setenv("MONITOR_AUTH_PASSWORD", "中文密码")
        resp = _login(client, password="中文密码")
        assert resp.status_code == 200

    def test_login_session_logout(self, client, mocks):
        mocks["getAll"].return_value = []

        resp = _login(client)
        assert resp.status_code == 200
        assert resp.get_json()["user"] == "admin"

        resp = client.get("/dashboard/api/session")
        assert resp.status_code == 200
        assert resp.get_json()["authenticated"] is True

        resp = client.post("/dashboard/api/logout")
        assert resp.status_code == 200

        resp = client.get("/dashboard/api/overview")
        assert resp.status_code == 401


class TestMonitorOverview:

    def test_overview(self, client, mocks):
        _login(client)
        mocks["getAll"].return_value = _proxy_list()

        resp = client.get("/dashboard/api/overview")
        assert resp.status_code == 200
        data = resp.get_json()

        assert data["pool"]["total"] == 3
        assert data["pool"]["http"] == 2
        assert data["pool"]["https"] == 1
        assert data["pool"]["healthy"] == 1
        assert data["pool"]["failing"] == 2
        assert data["pool"]["sources"]["srcA"] == 2
        assert data["gateway"]["requests"] == 0
        assert data["waf"]["rules_24h"] == []
        assert data["strategy"]["effective"] == "random"
        assert data["config"]["version"]


class TestMonitorProxies:

    def test_pagination_and_filters(self, client, mocks):
        _login(client)
        mocks["getAll"].return_value = _proxy_list()

        resp = client.get("/dashboard/api/proxies?page=1&page_size=2")
        data = resp.get_json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["sources"] == ["srcA", "srcB"]

        resp = client.get("/dashboard/api/proxies?https=https")
        data = resp.get_json()
        assert data["total"] == 1
        assert data["items"][0]["proxy"] == "2.2.2.2:443"

        resp = client.get("/dashboard/api/proxies?q=3.3.3.3")
        data = resp.get_json()
        assert data["total"] == 1
        assert data["items"][0]["proxy"] == "3.3.3.3:8080"

        resp = client.get("/dashboard/api/proxies?source=srcB")
        data = resp.get_json()
        assert data["total"] == 2

        resp = client.get("/dashboard/api/proxies?status=failing")
        data = resp.get_json()
        assert data["total"] == 2

        resp = client.get("/dashboard/api/proxies?sort=fail_count&order=desc")
        data = resp.get_json()
        assert data["items"][0]["fail_count"] == 2

    def test_delete_proxy(self, client, mocks):
        _login(client)
        mocks["delete"].return_value = True

        resp = client.post(
            "/dashboard/api/proxies/delete",
            json={"proxy": "1.1.1.1:80"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["src"] is True
        mocks["delete"].assert_called_once()
        assert mocks["delete"].call_args[0][0].proxy == "1.1.1.1:80"


class TestMonitorStrategy:

    def test_set_and_reset_strategy(self, client, mocks):
        _login(client)
        mocks["getAll"].return_value = _proxy_list()

        resp = client.post(
            "/dashboard/api/strategy",
            json={"strategy": "round_robin"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["strategy"]["effective"] == "round_robin"

        # /get 应使用运行时覆盖策略
        proxy = Proxy("1.1.1.1:80", source="srcA")
        mocks["get"].return_value = proxy
        mocks["get"].reset_mock()
        resp = client.get("/get/")
        assert resp.status_code == 200
        mocks["get"].assert_called_once_with(
            False, strategy="round_robin", key="api:get:http"
        )

        resp = client.post(
            "/dashboard/api/strategy",
            json={"strategy": "not-exist"},
        )
        assert resp.status_code == 400

        resp = client.post(
            "/dashboard/api/strategy",
            json={"strategy": None},
        )
        assert resp.status_code == 200
        assert resp.get_json()["strategy"]["effective"] == "random"


class TestMonitorData:

    def test_trends_waf_config_health(self, client, mocks):
        _login(client)
        mocks["getAll"].return_value = _proxy_list()

        # overview 会写入快照
        assert client.get("/dashboard/api/overview").status_code == 200

        resp = client.get("/dashboard/api/trends?hours=24")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["proxy"]) == 1
        assert data["proxy"][0]["total"] == 3

        resp = client.get("/dashboard/api/waf?hours=24")
        assert resp.status_code == 200
        assert resp.get_json()["rules"] == []

        resp = client.get("/dashboard/api/config")
        assert resp.status_code == 200
        assert resp.get_json()["config"]["monitor"]["enabled"] is True

        resp = client.get("/dashboard/api/health")
        assert resp.status_code == 200
        assert resp.get_json()["store"]["ok"] is True


class TestMonitorStream:

    def test_stream_requires_login(self, client):
        resp = client.get("/dashboard/api/stream")
        assert resp.status_code == 401

    def test_stream_events(self, client, mocks):
        _login(client)
        mocks["getAll"].return_value = _proxy_list()

        resp = client.get("/dashboard/api/stream", buffered=False)
        assert resp.status_code == 200
        assert resp.mimetype == "text/event-stream"

        try:
            first = next(iter(resp.response)).decode("utf-8")
            assert "event: hello" in first or "event: pool" in first
            assert "data:" in first
        finally:
            resp.close()


class TestMonitorStatic:

    def test_index_served(self, client):
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        assert b"<div id=\"root\">" in resp.data

    def test_unknown_api_returns_404(self, client):
        resp = client.get("/dashboard/api/not-exist")
        assert resp.status_code == 404
