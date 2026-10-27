# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     testConfig.py
   Description :   ConfigHandler环境变量测试
   Author :        JHao
   date：          2026/5/28
-------------------------------------------------
   Change Activity:
                   2026/05/28:
-------------------------------------------------
"""
__author__ = 'JHao'

import os
import pytest
import setting
from handler.configHandler import ConfigHandler


@pytest.fixture(autouse=True)
def clean_env():
    """测试前后清理可能设置的环境变量"""
    env_keys = ["DB_CONN", "PORT", "HOST", "TABLE_NAME", "HTTP_URL",
                "HTTPS_URL", "VERIFY_TIMEOUT", "MAX_FAIL_COUNT",
                "POOL_SIZE_MIN", "PROXY_REGION", "TIMEZONE",
                "PROXY_STRATEGY", "GATEWAY_ENABLED", "GATEWAY_HOST",
                "GATEWAY_PORT", "GATEWAY_STRATEGY", "GATEWAY_AUTH",
                "GATEWAY_RETRY", "GATEWAY_CONNECT_TIMEOUT",
                "GATEWAY_HEADER_TIMEOUT", "WAF_DETECT_ENABLED",
                "WAF_SCORE_THRESHOLD", "WAF_BODY_PREFIX_SIZE",
                "WAF_BODY_READ_TIMEOUT", "WAF_MAX_REPLAY_BODY",
                "WAF_CUSTOM_HEADERS", "WAF_CUSTOM_KEYWORDS",
                "WAF_CUSTOM_STATUS", "MONITOR_ENABLED",
                "MONITOR_DB_PATH", "MONITOR_AUTH_USER",
                "MONITOR_AUTH_PASSWORD", "MONITOR_SESSION_TTL",
                "MONITOR_COOKIE_SECURE", "MONITOR_RETENTION_DAYS",
                "MONITOR_REFRESH_SECONDS"]
    saved = {k: os.environ.get(k) for k in env_keys}
    for k in env_keys:
        os.environ.pop(k, None)
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


@pytest.fixture
def conf():
    return ConfigHandler()


class TestConfigHandlerDefaults:

    def test_db_conn_default(self, conf):
        assert conf.dbConn == setting.DB_CONN

    def test_server_host_default(self, conf):
        assert conf.serverHost == setting.HOST

    def test_server_port_default(self, conf):
        assert str(conf.serverPort) == str(setting.PORT)

    def test_table_name_default(self, conf):
        assert conf.tableName == setting.TABLE_NAME

    def test_http_url_default(self, conf):
        assert conf.httpUrl == setting.HTTP_URL

    def test_https_url_default(self, conf):
        assert conf.httpsUrl == setting.HTTPS_URL

    def test_verify_timeout_default(self, conf):
        assert conf.verifyTimeout == setting.VERIFY_TIMEOUT

    def test_max_fail_count_default(self, conf):
        assert conf.maxFailCount == setting.MAX_FAIL_COUNT

    def test_pool_size_min_default(self, conf):
        assert conf.poolSizeMin == setting.POOL_SIZE_MIN

    def test_timezone_default(self, conf):
        assert conf.timezone == setting.TIMEZONE

    def test_fetcher_exclude_is_list(self, conf):
        assert isinstance(conf.fetcherExclude, list)

    def test_proxy_strategy_default(self, conf):
        assert conf.defaultStrategy == setting.PROXY_STRATEGY

    def test_gateway_enabled_default(self, conf):
        assert conf.gatewayEnabled is True

    def test_gateway_host_default(self, conf):
        assert conf.gatewayHost == setting.GATEWAY_HOST

    def test_gateway_port_default(self, conf):
        assert conf.gatewayPort == setting.GATEWAY_PORT

    def test_gateway_strategy_default(self, conf):
        assert conf.gatewayStrategy == setting.GATEWAY_STRATEGY

    def test_gateway_auth_default(self, conf):
        assert conf.gatewayAuth == setting.GATEWAY_AUTH

    def test_gateway_retry_default(self, conf):
        assert conf.gatewayRetry == setting.GATEWAY_RETRY

    def test_gateway_connect_timeout_default(self, conf):
        assert conf.gatewayConnectTimeout == setting.GATEWAY_CONNECT_TIMEOUT

    def test_waf_detect_enabled_default(self, conf):
        assert conf.wafDetectEnabled is True

    def test_waf_score_threshold_default(self, conf):
        assert conf.wafScoreThreshold == setting.WAF_SCORE_THRESHOLD

    def test_waf_body_prefix_size_default(self, conf):
        assert conf.wafBodyPrefixSize == setting.WAF_BODY_PREFIX_SIZE

    def test_waf_body_read_timeout_default(self, conf):
        assert conf.wafBodyReadTimeout == setting.WAF_BODY_READ_TIMEOUT

    def test_waf_max_replay_body_default(self, conf):
        assert conf.wafMaxReplayBody == setting.WAF_MAX_REPLAY_BODY

    def test_waf_custom_rules_default(self, conf):
        assert conf.wafCustomHeaders == []
        assert conf.wafCustomKeywords == []
        assert conf.wafCustomStatus == []

    def test_monitor_defaults(self, conf):
        assert conf.monitorEnabled is True
        assert conf.monitorAuthUser == "admin"
        assert conf.monitorAuthPassword == "change-me"
        assert conf.monitorSessionTtl == 86400
        assert conf.monitorCookieSecure is False
        assert conf.monitorRetentionDays == 7
        assert conf.monitorRefreshSeconds == 5

    def test_monitor_db_path_is_absolute(self, conf):
        assert os.path.isabs(conf.monitorDbPath)
        assert conf.monitorDbPath.endswith("monitor.db")


class TestConfigHandlerEnvOverride:

    def test_db_conn_override(self):
        os.environ["DB_CONN"] = "redis://:newpwd@10.0.0.1:6380/3"
        conf = ConfigHandler()
        assert conf.dbConn == "redis://:newpwd@10.0.0.1:6380/3"

    def test_port_override(self):
        os.environ["PORT"] = "8080"
        conf = ConfigHandler()
        assert str(conf.serverPort) == "8080"

    def test_verify_timeout_override(self):
        os.environ["VERIFY_TIMEOUT"] = "30"
        conf = ConfigHandler()
        assert conf.verifyTimeout == 30

    def test_max_fail_count_override(self):
        os.environ["MAX_FAIL_COUNT"] = "5"
        conf = ConfigHandler()
        assert conf.maxFailCount == 5

    def test_proxy_strategy_override(self):
        os.environ["PROXY_STRATEGY"] = "weighted"
        conf = ConfigHandler()
        assert conf.defaultStrategy == "weighted"

    def test_gateway_enabled_override(self):
        os.environ["GATEWAY_ENABLED"] = "false"
        conf = ConfigHandler()
        assert conf.gatewayEnabled is False

    def test_gateway_port_override(self):
        os.environ["GATEWAY_PORT"] = "6011"
        conf = ConfigHandler()
        assert conf.gatewayPort == 6011

    def test_gateway_auth_override(self):
        os.environ["GATEWAY_AUTH"] = "user:pass"
        conf = ConfigHandler()
        assert conf.gatewayAuth == "user:pass"

    def test_waf_detect_enabled_override(self):
        os.environ["WAF_DETECT_ENABLED"] = "false"
        conf = ConfigHandler()
        assert conf.wafDetectEnabled is False

    def test_waf_score_threshold_override(self):
        os.environ["WAF_SCORE_THRESHOLD"] = "3"
        conf = ConfigHandler()
        assert conf.wafScoreThreshold == 3

    def test_waf_custom_headers_override(self):
        os.environ["WAF_CUSTOM_HEADERS"] = "x-my-waf: blocked, x-another-waf"
        conf = ConfigHandler()
        assert conf.wafCustomHeaders == ["x-my-waf: blocked", "x-another-waf"]

    def test_waf_custom_keywords_override(self):
        os.environ["WAF_CUSTOM_KEYWORDS"] = "custom block, 自定义拦截"
        conf = ConfigHandler()
        assert conf.wafCustomKeywords == ["custom block", "自定义拦截"]

    def test_waf_custom_status_override(self):
        os.environ["WAF_CUSTOM_STATUS"] = "418, 403, bad"
        conf = ConfigHandler()
        assert conf.wafCustomStatus == [418, 403]

    def test_monitor_overrides(self):
        os.environ["MONITOR_ENABLED"] = "false"
        os.environ["MONITOR_AUTH_PASSWORD"] = "secret"
        os.environ["MONITOR_SESSION_TTL"] = "120"
        os.environ["MONITOR_COOKIE_SECURE"] = "true"
        os.environ["MONITOR_RETENTION_DAYS"] = "3"
        os.environ["MONITOR_REFRESH_SECONDS"] = "10"
        conf = ConfigHandler()
        assert conf.monitorEnabled is False
        assert conf.monitorAuthPassword == "secret"
        assert conf.monitorSessionTtl == 120
        assert conf.monitorCookieSecure is True
        assert conf.monitorRetentionDays == 3
        assert conf.monitorRefreshSeconds == 10

    def test_monitor_relative_db_path(self):
        os.environ["MONITOR_DB_PATH"] = "tmp/monitor-test.db"
        conf = ConfigHandler()
        assert os.path.isabs(conf.monitorDbPath)
        assert conf.monitorDbPath.endswith(os.path.join("tmp", "monitor-test.db"))