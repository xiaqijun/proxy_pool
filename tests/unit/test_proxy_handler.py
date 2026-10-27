# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     test_proxy_handler.py
   Description :   ProxyHandler 单元测试
   Author :        JHao
   date：          2026/6/15
-------------------------------------------------
     Change Activity:
                     2026/06/15:
-------------------------------------------------
"""
__author__ = 'JHao'

import pytest
from unittest.mock import MagicMock, patch

from handler.proxyHandler import ProxyHandler
from helper.proxy import Proxy


def _make_handler():
    """构造注入 mock DbClient 的 ProxyHandler 实例"""
    with patch("handler.proxyHandler.DbClient") as mock_db_cls, \
         patch("handler.proxyHandler.ConfigHandler") as mock_conf_cls:
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        mock_conf = MagicMock()
        mock_conf.dbConn = "redis://:test@127.0.0.1:6379/0"
        mock_conf.tableName = "use_proxy"
        mock_conf_cls.return_value = mock_conf
        handler = ProxyHandler()
        handler._mock_db = mock_db
        return handler


class TestProxyHandlerGet:
    """get() 测试"""

    def test_get_returns_proxy(self):
        """DbClient 返回 JSON -> Proxy 对象"""
        handler = _make_handler()
        proxy = Proxy("1.2.3.4:8080", source="test", https=False)
        handler._mock_db.get.return_value = proxy.to_json

        result = handler.get(https=False)

        assert result is not None
        assert result.proxy == "1.2.3.4:8080"
        assert result.https is False
        handler._mock_db.get.assert_called_once_with(False)

    def test_get_returns_none_when_empty(self):
        """DbClient 返回 None -> None"""
        handler = _make_handler()
        handler._mock_db.get.return_value = None

        result = handler.get(https=False)

        assert result is None

    def test_get_https_forwarded(self):
        """https=True 转发给 DbClient"""
        handler = _make_handler()
        proxy = Proxy("5.6.7.8:443", source="test", https=True)
        handler._mock_db.get.return_value = proxy.to_json

        result = handler.get(https=True)

        assert result is not None
        assert result.https is True
        handler._mock_db.get.assert_called_once_with(True)


class TestProxyHandlerStrategy:
    """按策略获取代理测试"""

    @staticmethod
    def _proxy_list():
        return [
            Proxy("1.2.3.4:8080", source="test", https=False).to_json,
            Proxy("5.6.7.8:443", source="test", https=True).to_json,
        ]

    def test_get_with_strategy_uses_getAll(self):
        handler = _make_handler()
        handler._mock_db.getAll.return_value = self._proxy_list()

        result = handler.get(https=False, strategy="round_robin", key="unit")

        assert result.proxy in ("1.2.3.4:8080", "5.6.7.8:443")
        handler._mock_db.getAll.assert_called_once_with(False)

    def test_get_with_random_reuses_db_get(self):
        handler = _make_handler()
        proxy = Proxy("1.2.3.4:8080", source="test")
        handler._mock_db.get.return_value = proxy.to_json

        result = handler.get(https=False, strategy="random", exclude=set())

        assert result.proxy == "1.2.3.4:8080"
        handler._mock_db.get.assert_called_once_with(False)
        handler._mock_db.getAll.assert_not_called()

    def test_get_with_strategy_empty_pool(self):
        handler = _make_handler()
        handler._mock_db.getAll.return_value = []

        result = handler.get(https=False, strategy="round_robin", key="unit")

        assert result is None

    def test_get_with_exclude(self):
        handler = _make_handler()
        handler.conf.defaultStrategy = "random"
        handler._mock_db.getAll.return_value = self._proxy_list()

        result = handler.get(https=False, exclude={"1.2.3.4:8080"})

        assert result.proxy == "5.6.7.8:443"

    def test_get_exclude_all_returns_none(self):
        handler = _make_handler()
        handler.conf.defaultStrategy = "random"
        handler._mock_db.getAll.return_value = self._proxy_list()

        result = handler.get(https=False, exclude={"1.2.3.4:8080", "5.6.7.8:443"})

        assert result is None


class TestProxyHandlerPop:
    """pop() 测试"""

    def test_pop_returns_proxy(self):
        """pop 正常返回 Proxy 对象"""
        handler = _make_handler()
        proxy = Proxy("1.2.3.4:8080", source="test")
        handler._mock_db.pop.return_value = proxy.to_json

        result = handler.pop(https=False)

        assert result is not None
        assert result.proxy == "1.2.3.4:8080"
        handler._mock_db.pop.assert_called_once_with(False)

    def test_pop_returns_none_when_empty(self):
        """pop 无数据时返回 None"""
        handler = _make_handler()
        handler._mock_db.pop.return_value = None

        result = handler.pop(https=False)

        assert result is None


class TestProxyHandlerPut:
    """put() 测试"""

    def test_put_delegates_to_db(self):
        """put 调用 DbClient.put"""
        handler = _make_handler()
        proxy = Proxy("1.2.3.4:8080", source="test")

        handler.put(proxy)

        handler._mock_db.put.assert_called_once_with(proxy)


class TestProxyHandlerDelete:
    """delete() 测试"""

    def test_delete_delegates_to_db(self):
        """delete 传入 proxy.proxy 字符串给 DbClient"""
        handler = _make_handler()
        proxy = Proxy("1.2.3.4:8080", source="test")

        handler.delete(proxy)

        handler._mock_db.delete.assert_called_once_with("1.2.3.4:8080")


class TestProxyHandlerGetAll:
    """getAll() 测试"""

    def test_getAll_returns_proxy_list(self):
        """getAll 返回 Proxy 对象列表"""
        handler = _make_handler()
        proxy1 = Proxy("1.2.3.4:8080", source="test").to_json
        proxy2 = Proxy("5.6.7.8:443", source="test", https=True).to_json
        handler._mock_db.getAll.return_value = [proxy1, proxy2]

        result = handler.getAll(https=False)

        assert len(result) == 2
        assert result[0].proxy == "1.2.3.4:8080"
        assert result[1].proxy == "5.6.7.8:443"
        handler._mock_db.getAll.assert_called_once_with(False)

    def test_getAll_empty_returns_empty_list(self):
        """getAll 无数据返回空列表"""
        handler = _make_handler()
        handler._mock_db.getAll.return_value = []

        result = handler.getAll()

        assert result == []


class TestProxyHandlerExists:
    """exists() 测试"""

    def test_exists_delegates_to_db(self):
        """exists 传入 proxy.proxy 字符串给 DbClient"""
        handler = _make_handler()
        proxy = Proxy("1.2.3.4:8080", source="test")
        handler._mock_db.exists.return_value = True

        result = handler.exists(proxy)

        assert result is True
        handler._mock_db.exists.assert_called_once_with("1.2.3.4:8080")


class TestProxyHandlerGetCount:
    """getCount() 测试"""

    def test_getCount_returns_dict(self):
        """getCount 返回 {'count': N}"""
        handler = _make_handler()
        handler._mock_db.getCount.return_value = 42

        result = handler.getCount()

        assert result == {"count": 42}