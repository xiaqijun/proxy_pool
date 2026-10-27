# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     testProxyApi.py
   Description :   Flask API全路由测试
   Author :        JHao
   date：          2026/5/28
-------------------------------------------------
   Change Activity:
                   2026/05/28:
-------------------------------------------------
"""
__author__ = 'JHao'

import pytest
from unittest.mock import patch, MagicMock
from helper.proxy import Proxy
from api.proxyApi import JsonResponse


@pytest.fixture
def mocks(app):
    """快捷访问 app._test_mocks"""
    return app._test_mocks


class TestIndex:

    def test_index_returns_api_list(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "url" in data
        assert len(data["url"]) > 0
        assert data["dashboard"] == "/dashboard/"


class TestGet:

    def test_get_returns_proxy(self, client, mocks):
        proxy = Proxy("1.2.3.4:8080", source="test", https=False)
        mocks["get"].return_value = proxy

        resp = client.get("/get/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["proxy"] == "1.2.3.4:8080"
        assert data["https"] is False

    def test_get_no_proxy(self, client, mocks):
        mocks["get"].return_value = None

        resp = client.get("/get/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == 0
        assert data["src"] == "no proxy"

    def test_get_https_filter(self, client, mocks):
        proxy = Proxy("5.6.7.8:443", source="test", https=True)
        mocks["get"].return_value = proxy

        resp = client.get("/get/?type=https")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["https"] is True
        mocks["get"].assert_called_with(True)

    def test_get_http_filter(self, client, mocks):
        mocks["get"].return_value = None

        client.get("/get/")
        mocks["get"].assert_called_with(False)


class TestGetStrategy:

    def test_get_with_strategy(self, client, mocks):
        proxy = Proxy("1.2.3.4:8080", source="test")
        mocks["get"].return_value = proxy

        resp = client.get("/get/?strategy=round_robin")
        assert resp.status_code == 200
        assert resp.get_json()["proxy"] == "1.2.3.4:8080"
        mocks["get"].assert_called_once_with(
            False, strategy="round_robin", key="api:get:http"
        )

    def test_get_with_random_uses_default_path(self, client, mocks):
        proxy = Proxy("1.2.3.4:8080", source="test")
        mocks["get"].return_value = proxy

        resp = client.get("/get/?strategy=random")
        assert resp.status_code == 200
        mocks["get"].assert_called_once_with(False)

    def test_get_with_mode_alias(self, client, mocks):
        proxy = Proxy("1.2.3.4:8080", source="test")
        mocks["get"].return_value = proxy

        resp = client.get("/get/?mode=weighted&type=https")
        assert resp.status_code == 200
        mocks["get"].assert_called_once_with(
            True, strategy="weighted", key="api:get:https"
        )

    def test_get_unknown_strategy(self, client, mocks):
        resp = client.get("/get/?strategy=not-exist")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["src"] == "unknown strategy"
        assert mocks["get"].not_called

    def test_get_format_text(self, client, mocks):
        proxy = Proxy("1.2.3.4:8080", source="test")
        mocks["get"].return_value = proxy

        resp = client.get("/get/?format=text")
        assert resp.status_code == 200
        assert resp.mimetype == "text/plain"
        assert resp.get_data(as_text=True) == "1.2.3.4:8080"

    def test_get_format_text_no_proxy(self, client, mocks):
        mocks["get"].return_value = None

        resp = client.get("/get/?format=text")
        assert resp.status_code == 503
        assert resp.get_data(as_text=True) == "no proxy"


class TestStrategies:

    def test_strategies_endpoint(self, client):
        resp = client.get("/strategies/")
        assert resp.status_code == 200
        data = resp.get_json()
        names = [item["name"] for item in data["supported"]]
        assert names == ["random", "round_robin", "weighted"]
        assert data["default"] in names
        assert all(item["description"] for item in data["supported"])


class TestGatewayInfo:

    def test_gateway_endpoint(self, client):
        resp = client.get("/gateway/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["address"].endswith(":5011")
        assert data["strategy"] in ("random", "round_robin", "weighted")
        assert isinstance(data["auth"], bool)
        assert data["waf"]["enabled"] is True
        assert data["waf"]["score_threshold"] >= 1


class TestPop:

    def test_pop_returns_proxy(self, client, mocks):
        proxy = Proxy("1.2.3.4:8080", source="test")
        mocks["pop"].return_value = proxy

        resp = client.get("/pop/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["proxy"] == "1.2.3.4:8080"

    def test_pop_no_proxy(self, client, mocks):
        mocks["pop"].return_value = None

        resp = client.get("/pop/")
        data = resp.get_json()
        assert data["code"] == 0


class TestAll:

    def test_all_returns_list(self, client, mocks):
        proxies = [
            Proxy("1.2.3.4:8080", source="test"),
            Proxy("5.6.7.8:443", source="test", https=True),
        ]
        mocks["getAll"].return_value = proxies

        resp = client.get("/all/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2
        assert data[0]["proxy"] == "1.2.3.4:8080"
        assert data[1]["proxy"] == "5.6.7.8:443"

    def test_all_empty(self, client, mocks):
        mocks["getAll"].return_value = []

        resp = client.get("/all/")
        data = resp.get_json()
        assert data == []


class TestDelete:

    def test_delete_calls_handler(self, client, mocks):
        mocks["delete"].return_value = True

        resp = client.get("/delete/?proxy=1.2.3.4:8080")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == 0
        assert data["src"] is True
        mocks["delete"].assert_called_once()


class TestCount:

    def test_count_returns_stats(self, client, mocks):
        proxies = [
            Proxy("1.2.3.4:8080", source="freeProxy01", https=False),
            Proxy("5.6.7.8:443", source="freeProxy02", https=True),
        ]
        mocks["getAll"].return_value = proxies

        resp = client.get("/count/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 2
        assert data["http_type"]["http"] == 1
        assert data["http_type"]["https"] == 1
        assert data["source"]["freeProxy01"] == 1
        assert data["source"]["freeProxy02"] == 1

    def test_count_empty(self, client, mocks):
        mocks["getAll"].return_value = []

        resp = client.get("/count/")
        data = resp.get_json()
        assert data["count"] == 0
        assert data["http_type"] == {}
        assert data["source"] == {}


class TestRefresh:

    def test_refresh_returns_success(self, client):
        resp = client.get("/refresh/")
        assert resp.status_code == 200
        assert b"success" in resp.data


class TestJsonResponse:

    def test_force_type_with_dict(self, app):
        """dict -> JSON Response"""
        with app.app_context():
            resp = JsonResponse.force_type({"key": "val"})
            assert resp.content_type == "application/json"

    def test_force_type_with_list(self, app):
        """list -> JSON Response"""
        with app.app_context():
            resp = JsonResponse.force_type([1, 2, 3])
            assert resp.content_type == "application/json"


class TestRunFlask:

    @patch("api.proxyApi.platform")
    @patch("api.proxyApi.app")
    def test_runflask_windows_path(self, mock_app, mock_platform):
        """Windows 下调用 app.run()"""
        mock_platform.system.return_value = "Windows"
        from api.proxyApi import runFlask
        runFlask()
        mock_app.run.assert_called_once()