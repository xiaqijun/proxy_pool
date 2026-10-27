# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     configHandler
   Description :
   Author :        JHao
   date：          2020/6/22
-------------------------------------------------
   Change Activity:
                   2020/6/22:
-------------------------------------------------
"""
__author__ = 'JHao'

import os
import setting
from util.singleton import Singleton
from util.lazyProperty import LazyProperty
from util.six import reload_six, withMetaclass


def _asBool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _envList(name, default):
    value = os.getenv(name)
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


def _envIntList(name, default):
    value = os.getenv(name)
    if value is None:
        return list(default or [])

    result = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.append(int(item))
        except ValueError:
            continue
    return result


class ConfigHandler(withMetaclass(Singleton)):

    def __init__(self):
        pass

    @LazyProperty
    def serverHost(self):
        return os.environ.get("HOST", setting.HOST)

    @LazyProperty
    def serverPort(self):
        return os.environ.get("PORT", setting.PORT)

    @LazyProperty
    def dbConn(self):
        return os.getenv("DB_CONN", setting.DB_CONN)

    @LazyProperty
    def tableName(self):
        return os.getenv("TABLE_NAME", setting.TABLE_NAME)

    @property
    def fetcherExclude(self):
        reload_six(setting)
        return getattr(setting, 'PROXY_FETCHER_EXCLUDE', [])

    @LazyProperty
    def httpUrl(self):
        return os.getenv("HTTP_URL", setting.HTTP_URL)

    @LazyProperty
    def httpsUrl(self):
        return os.getenv("HTTPS_URL", setting.HTTPS_URL)

    @LazyProperty
    def verifyTimeout(self):
        return int(os.getenv("VERIFY_TIMEOUT", setting.VERIFY_TIMEOUT))

    # @LazyProperty
    # def proxyCheckCount(self):
    #     return int(os.getenv("PROXY_CHECK_COUNT", setting.PROXY_CHECK_COUNT))

    @LazyProperty
    def maxFailCount(self):
        return int(os.getenv("MAX_FAIL_COUNT", setting.MAX_FAIL_COUNT))

    # @LazyProperty
    # def maxFailRate(self):
    #     return int(os.getenv("MAX_FAIL_RATE", setting.MAX_FAIL_RATE))

    @LazyProperty
    def poolSizeMin(self):
        return int(os.getenv("POOL_SIZE_MIN", setting.POOL_SIZE_MIN))

    @LazyProperty
    def proxyRegion(self):
        return bool(os.getenv("PROXY_REGION", setting.PROXY_REGION))

    @LazyProperty
    def timezone(self):
        return os.getenv("TIMEZONE", setting.TIMEZONE)

    # ############# proxy strategy config #################

    @LazyProperty
    def defaultStrategy(self):
        return os.getenv("PROXY_STRATEGY", setting.PROXY_STRATEGY)

    # ############# gateway config #################

    @LazyProperty
    def gatewayEnabled(self):
        return _asBool(os.getenv("GATEWAY_ENABLED", setting.GATEWAY_ENABLED))

    @LazyProperty
    def gatewayHost(self):
        return os.getenv("GATEWAY_HOST", setting.GATEWAY_HOST)

    @LazyProperty
    def gatewayPort(self):
        return int(os.getenv("GATEWAY_PORT", setting.GATEWAY_PORT))

    @LazyProperty
    def gatewayStrategy(self):
        return os.getenv("GATEWAY_STRATEGY", setting.GATEWAY_STRATEGY)

    @LazyProperty
    def gatewayAuth(self):
        return os.getenv("GATEWAY_AUTH", setting.GATEWAY_AUTH)

    @LazyProperty
    def gatewayRetry(self):
        return int(os.getenv("GATEWAY_RETRY", setting.GATEWAY_RETRY))

    @LazyProperty
    def gatewayConnectTimeout(self):
        return float(os.getenv("GATEWAY_CONNECT_TIMEOUT", setting.GATEWAY_CONNECT_TIMEOUT))

    @LazyProperty
    def gatewayHeaderTimeout(self):
        return float(os.getenv("GATEWAY_HEADER_TIMEOUT", setting.GATEWAY_HEADER_TIMEOUT))

    # ############# WAF detect config #################

    @LazyProperty
    def wafDetectEnabled(self):
        return _asBool(os.getenv("WAF_DETECT_ENABLED", setting.WAF_DETECT_ENABLED))

    @LazyProperty
    def wafScoreThreshold(self):
        return int(os.getenv("WAF_SCORE_THRESHOLD", setting.WAF_SCORE_THRESHOLD))

    @LazyProperty
    def wafBodyPrefixSize(self):
        return int(os.getenv("WAF_BODY_PREFIX_SIZE", setting.WAF_BODY_PREFIX_SIZE))

    @LazyProperty
    def wafBodyReadTimeout(self):
        return float(os.getenv("WAF_BODY_READ_TIMEOUT", setting.WAF_BODY_READ_TIMEOUT))

    @LazyProperty
    def wafMaxReplayBody(self):
        return int(os.getenv("WAF_MAX_REPLAY_BODY", setting.WAF_MAX_REPLAY_BODY))

    @LazyProperty
    def wafCustomHeaders(self):
        return _envList("WAF_CUSTOM_HEADERS", setting.WAF_CUSTOM_HEADERS)

    @LazyProperty
    def wafCustomKeywords(self):
        return _envList("WAF_CUSTOM_KEYWORDS", setting.WAF_CUSTOM_KEYWORDS)

    @LazyProperty
    def wafCustomStatus(self):
        return _envIntList("WAF_CUSTOM_STATUS", setting.WAF_CUSTOM_STATUS)

    # ############# monitor config #################

    @LazyProperty
    def monitorEnabled(self):
        return _asBool(os.getenv("MONITOR_ENABLED", setting.MONITOR_ENABLED))

    @LazyProperty
    def monitorDbPath(self):
        path = os.getenv("MONITOR_DB_PATH", setting.MONITOR_DB_PATH)
        if not os.path.isabs(path):
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(root, path)
        return os.path.normpath(path)

    @LazyProperty
    def monitorAuthUser(self):
        return os.getenv("MONITOR_AUTH_USER", setting.MONITOR_AUTH_USER)

    @LazyProperty
    def monitorAuthPassword(self):
        return os.getenv("MONITOR_AUTH_PASSWORD", setting.MONITOR_AUTH_PASSWORD)

    @LazyProperty
    def monitorSessionTtl(self):
        return int(os.getenv("MONITOR_SESSION_TTL", setting.MONITOR_SESSION_TTL))

    @LazyProperty
    def monitorCookieSecure(self):
        return _asBool(os.getenv("MONITOR_COOKIE_SECURE", setting.MONITOR_COOKIE_SECURE))

    @LazyProperty
    def monitorRetentionDays(self):
        return int(os.getenv("MONITOR_RETENTION_DAYS", setting.MONITOR_RETENTION_DAYS))

    @LazyProperty
    def monitorRefreshSeconds(self):
        return int(os.getenv("MONITOR_REFRESH_SECONDS", setting.MONITOR_REFRESH_SECONDS))

