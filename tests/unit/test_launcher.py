# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     test_launcher.py
   Description :   helper/launcher.py 单元测试
   Author :        JHao
   date：          2026/6/15
-------------------------------------------------
     Change Activity:
                     2026/06/15:
-------------------------------------------------
"""
__author__ = 'JHao'

import pytest
from unittest.mock import patch, MagicMock

import helper.launcher as launcher_mod


class TestStartServer:

    def test_calls_before_start_then_flask(self):
        """startServer 先调用 __beforeStart 再调用 runFlask"""
        with patch.object(launcher_mod, "__beforeStart") as mock_before, \
             patch("api.proxyApi.runFlask") as mock_flask:
            launcher_mod.startServer()
            mock_before.assert_called_once()


class TestStartScheduler:

    def test_calls_before_start_then_scheduler(self):
        """startScheduler 先调用 __beforeStart 再调用 runScheduler"""
        with patch.object(launcher_mod, "__beforeStart") as mock_before, \
             patch("helper.scheduler.runScheduler") as mock_sched:
            launcher_mod.startScheduler()
            mock_before.assert_called_once()


class TestStartGateway:

    def test_calls_before_start_then_gateway(self):
        """startGateway 先调用 __beforeStart 再调用 runGateway"""
        with patch.object(launcher_mod, "__beforeStart") as mock_before, \
             patch("gateway.proxyGateway.runGateway") as mock_gateway:
            launcher_mod.startGateway()
            mock_before.assert_called_once()
            mock_gateway.assert_called_once()


class TestStartAll:

    def test_starts_api_only_when_gateway_disabled(self):
        with patch.object(launcher_mod, "__beforeStart"), \
             patch.object(launcher_mod, "ConfigHandler") as mock_conf_cls, \
             patch("api.proxyApi.runFlask") as mock_flask:
            mock_conf = MagicMock()
            mock_conf.gatewayEnabled = False
            mock_conf_cls.return_value = mock_conf

            launcher_mod.startAll()

            mock_flask.assert_called_once()

    def test_starts_gateway_thread_and_api(self):
        with patch.object(launcher_mod, "__beforeStart"), \
             patch.object(launcher_mod, "ConfigHandler") as mock_conf_cls, \
             patch("gateway.proxyGateway.ProxyGateway") as mock_gateway_cls, \
             patch("threading.Thread") as mock_thread_cls, \
             patch("api.proxyApi.runFlask") as mock_flask:
            mock_conf = MagicMock()
            mock_conf.gatewayEnabled = True
            mock_conf_cls.return_value = mock_conf

            launcher_mod.startAll()

            mock_gateway_cls.assert_called_once()
            mock_thread_cls.return_value.start.assert_called_once()
            mock_flask.assert_called_once()


class TestBeforeStart:

    def test_exits_when_db_check_fails(self):
        """DB 检查失败 -> sys.exit()"""
        with patch.object(launcher_mod, "__showVersion"), \
             patch.object(launcher_mod, "__showConfigure"), \
             patch.object(launcher_mod, "__checkDBConfig", return_value=True), \
             patch("helper.launcher.sys") as mock_sys:
            getattr(launcher_mod, "__beforeStart")()
            mock_sys.exit.assert_called_once()

    def test_continues_when_db_check_passes(self):
        """DB 检查通过 -> 不调用 sys.exit"""
        with patch.object(launcher_mod, "__showVersion"), \
             patch.object(launcher_mod, "__showConfigure"), \
             patch.object(launcher_mod, "__checkDBConfig", return_value=False), \
             patch("helper.launcher.sys") as mock_sys:
            getattr(launcher_mod, "__beforeStart")()
            mock_sys.exit.assert_not_called()


class TestCheckStrategy:

    def test_invalid_strategy_returns_false(self):
        with patch.object(launcher_mod, "ConfigHandler") as mock_conf_cls:
            mock_conf = MagicMock()
            mock_conf.defaultStrategy = "not-exist"
            mock_conf.gatewayStrategy = "random"
            mock_conf_cls.return_value = mock_conf

            assert getattr(launcher_mod, "__checkStrategy")() is False

    def test_valid_strategy_returns_true(self):
        with patch.object(launcher_mod, "ConfigHandler") as mock_conf_cls:
            mock_conf = MagicMock()
            mock_conf.defaultStrategy = "weighted"
            mock_conf.gatewayStrategy = "round_robin"
            mock_conf_cls.return_value = mock_conf

            assert getattr(launcher_mod, "__checkStrategy")() is True


class TestCheckDBConfig:

    def test_returns_db_test_result(self):
        """返回 db.test() 的结果"""
        with patch.object(launcher_mod, "DbClient") as mock_db_cls, \
             patch.object(launcher_mod, "ConfigHandler") as mock_conf_cls:
            mock_conf = MagicMock()
            mock_conf.dbConn = "redis://:@127.0.0.1:6379/0"
            mock_conf_cls.return_value = mock_conf

            mock_db = MagicMock()
            mock_db.test.return_value = False
            mock_db_cls.return_value = mock_db

            result = getattr(launcher_mod, "__checkDBConfig")()

            assert result is False
            mock_db.test.assert_called_once()