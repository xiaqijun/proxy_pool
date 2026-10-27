# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     monitorApi.py
   Description :   监控工作台 API 与静态资源
   Author :        JHao
   date：          2026/10/26
-------------------------------------------------
   Change Activity:
                   2026/10/26: 登录、概览、代理列表、趋势、WAF、策略配置
-------------------------------------------------
"""
__author__ = 'JHao'

import contextlib
import hashlib
import hmac
import json
import os
import threading
import time
from collections import Counter
from datetime import timedelta
from functools import wraps

from flask import (
    Blueprint,
    Response,
    current_app,
    request,
    send_from_directory,
    session,
    stream_with_context,
)

from handler.configHandler import ConfigHandler
from helper.proxy import Proxy
from helper.strategy import (
    STRATEGY_DESCRIPTIONS,
    STRATEGY_RANDOM,
    SUPPORTED_STRATEGIES,
    UnknownStrategyError,
    normalizeStrategy,
)
from monitor.monitorStore import MonitorStore
from setting import VERSION

monitor_bp = Blueprint("monitor", __name__, url_prefix="/dashboard")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_FAILURES = 5
_login_failures = {}
_login_lock = threading.Lock()


def initMonitorApp(app, proxy_handler):
    """初始化监控工作台：注册蓝图、设置会话密钥和 Cookie 策略"""
    app.extensions["proxy_pool_handler"] = proxy_handler

    conf = ConfigHandler()
    secret_material = "proxy_pool_monitor:%s:%s" % (
        conf.monitorAuthUser,
        conf.monitorAuthPassword,
    )
    app.secret_key = hashlib.sha256(secret_material.encode("utf-8")).digest()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=conf.monitorCookieSecure,
        PERMANENT_SESSION_LIFETIME=timedelta(
            seconds=max(int(conf.monitorSessionTtl), 60)
        ),
    )
    app.register_blueprint(monitor_bp)


def _enabled():
    return ConfigHandler().monitorEnabled


def _handler():
    return current_app.extensions.get("proxy_pool_handler")


def _monitorDisabled():
    return {"code": 503, "src": "monitor is disabled"}, 503


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not _enabled():
            return _monitorDisabled()
        if not session.get("monitor_user"):
            return {"code": 401, "src": "unauthorized"}, 401
        return func(*args, **kwargs)
    return wrapper


def _clientIp():
    # 反向代理场景下使用 X-Forwarded-For 的第一个地址
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "-"
    return request.remote_addr or "-"


def _tooManyLoginFailures(ip):
    now = time.time()
    with _login_lock:
        attempts = [ts for ts in _login_failures.get(ip, [])
                    if now - ts < LOGIN_WINDOW_SECONDS]
        _login_failures[ip] = attempts
        return len(attempts) >= LOGIN_MAX_FAILURES


def _recordLoginFailure(ip):
    with _login_lock:
        _login_failures.setdefault(ip, []).append(time.time())


def _clearLoginFailures(ip):
    with _login_lock:
        _login_failures.pop(ip, None)


def _safeDefaultStrategy(value):
    try:
        return normalizeStrategy(value, default=STRATEGY_RANDOM)
    except UnknownStrategyError:
        return STRATEGY_RANDOM


def _strategyState(store):
    conf = ConfigHandler()
    config_default = _safeDefaultStrategy(conf.defaultStrategy)
    override = store.getSetting("strategy_override")
    effective = config_default
    if override:
        try:
            effective = normalizeStrategy(override)
        except UnknownStrategyError:
            effective = config_default

    return {
        "effective": effective,
        "config_default": config_default,
        "override": override or None,
        "supported": [
            {"name": name, "description": STRATEGY_DESCRIPTIONS[name]}
            for name in SUPPORTED_STRATEGIES
        ],
    }


def _configSummary(store=None):
    store = store or MonitorStore()
    conf = ConfigHandler()
    return {
        "version": VERSION,
        "strategy": _strategyState(store),
        "gateway": {
            "enabled": conf.gatewayEnabled,
            "address": "%s:%s" % (conf.gatewayHost, conf.gatewayPort),
            "strategy": conf.gatewayStrategy,
            "auth": bool(conf.gatewayAuth),
            "retry": conf.gatewayRetry,
            "connect_timeout": conf.gatewayConnectTimeout,
            "header_timeout": conf.gatewayHeaderTimeout,
        },
        "waf": {
            "enabled": conf.wafDetectEnabled,
            "score_threshold": conf.wafScoreThreshold,
            "body_prefix_size": conf.wafBodyPrefixSize,
            "body_read_timeout": conf.wafBodyReadTimeout,
            "max_replay_body": conf.wafMaxReplayBody,
            "custom_headers": len(conf.wafCustomHeaders),
            "custom_keywords": len(conf.wafCustomKeywords),
            "custom_status": conf.wafCustomStatus,
        },
        "monitor": {
            "enabled": conf.monitorEnabled,
            "retention_days": conf.monitorRetentionDays,
            "refresh_seconds": conf.monitorRefreshSeconds,
            "cookie_secure": conf.monitorCookieSecure,
        },
    }


def _poolStats(proxies):
    total = len(proxies)
    https_count = sum(1 for item in proxies if item.https)
    http_count = total - https_count
    sources = Counter()
    regions = Counter()
    fail_sum = 0
    check_sum = 0
    healthy = 0
    failing = 0
    last_updated = ""

    for item in proxies:
        for source in str(item.source or "").split("/"):
            if source:
                sources[source] += 1
        if item.region:
            regions[item.region] += 1
        fail_sum += int(item.fail_count or 0)
        check_sum += int(item.check_count or 0)
        if int(item.fail_count or 0) == 0:
            healthy += 1
        else:
            failing += 1
        if item.last_time and item.last_time > last_updated:
            last_updated = item.last_time

    return {
        "total": total,
        "http": http_count,
        "https": https_count,
        "healthy": healthy,
        "failing": failing,
        "avg_fail_count": round(fail_sum * 1.0 / total, 2) if total else 0,
        "avg_check_count": round(check_sum * 1.0 / total, 2) if total else 0,
        "sources": dict(sources.most_common()),
        "regions": dict(regions.most_common()),
        "last_updated": last_updated,
    }


def _clampHours(value, default=24):
    try:
        hours = int(value)
    except (TypeError, ValueError):
        hours = default
    return min(max(hours, 1), 168)


def _sseEvent(name, data):
    return "event: %s\ndata: %s\n\n" % (
        name,
        json.dumps(data, ensure_ascii=False, default=str),
    )


def _eventStream(handler, store):
    """SSE 实时推送：网关 1s、WAF 2s、代理池 3s、趋势 10s"""
    tick = 0
    last_pool = 0.0
    last_waf = 0.0
    last_trends = 0.0
    last_heartbeat = 0.0
    refresh_seconds = max(int(ConfigHandler().monitorRefreshSeconds), 1)

    yield _sseEvent("hello", {
        "version": VERSION,
        "stream_interval": 1,
        "refresh_seconds": refresh_seconds,
    })

    while True:
        now = time.time()
        try:
            # 代理池与配置变化较慢，3 秒推送一次
            if tick == 0 or now - last_pool >= 3:
                proxies = handler.getAll()
                store.recordProxySnapshot(proxies)
                yield _sseEvent("pool", {
                    "pool": _poolStats(proxies),
                    "strategy": _strategyState(store),
                    "config": _configSummary(store),
                    "generated_at": int(now),
                })
                last_pool = now

            # 网关指标 1 秒推送一次
            yield _sseEvent("gateway", {
                "gateway": store.getGatewaySummary(24),
                "generated_at": int(now),
            })

            # WAF 事件 2 秒推送一次
            if tick == 0 or now - last_waf >= 2:
                yield _sseEvent("waf", {
                    "rules": store.getWafRuleCounts(24),
                    "recent": store.getRecentWafEvents(20),
                })
                last_waf = now

            # 趋势 10 秒推送一次
            if tick == 0 or now - last_trends >= 10:
                yield _sseEvent("trends", {
                    "proxy": store.getProxySnapshots(24),
                    "gateway": store.getGatewaySeries(24),
                })
                last_trends = now

            # 心跳，避免反向代理空闲断开
            if now - last_heartbeat >= 15:
                yield ": ping\n\n"
                last_heartbeat = now

            tick += 1
            time.sleep(1)
        except GeneratorExit:
            return
        except Exception as error:
            # 数据源暂时异常时推送一次错误，继续保留连接
            with contextlib.suppress(Exception):
                yield _sseEvent("server-error", {"src": str(error)})
            time.sleep(2)


@monitor_bp.after_request
def _noCache(response):
    if request.path.startswith("/dashboard/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ######################## static SPA ########################

def _spa():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.isfile(index_path):
        return {
            "code": 503,
            "src": "dashboard frontend not built, run: cd dashboard && npm install && npm run build",
        }, 503
    response = send_from_directory(STATIC_DIR, "index.html")
    response.headers["Cache-Control"] = "no-cache"
    return response


@monitor_bp.route("/")
def index():
    return _spa()


@monitor_bp.route("/<path:path>")
def staticOrSpa(path):
    if path.startswith("api/"):
        return {"code": 404, "src": "not found"}, 404
    full_path = os.path.join(STATIC_DIR, path)
    if os.path.isfile(full_path):
        return send_from_directory(STATIC_DIR, path)
    return _spa()


# ######################## auth ########################

@monitor_bp.route("/api/session")
def sessionInfo():
    if not _enabled():
        return _monitorDisabled()
    user = session.get("monitor_user")
    if not user:
        return {"code": 401, "src": "unauthorized"}, 401
    return {"authenticated": True, "user": user}


@monitor_bp.route("/api/login", methods=["POST"])
def login():
    if not _enabled():
        return _monitorDisabled()

    conf = ConfigHandler()
    expected_user = str(conf.monitorAuthUser)
    expected_password = str(conf.monitorAuthPassword)
    if not expected_password:
        return {"code": 503, "src": "MONITOR_AUTH_PASSWORD is not configured"}, 503

    ip = _clientIp()
    if _tooManyLoginFailures(ip):
        return {"code": 429, "src": "too many login attempts"}, 429

    data = request.get_json(silent=True) or {}
    user = str(data.get("username") or "")
    password = str(data.get("password") or "")

    valid = hmac.compare_digest(user.encode("utf-8"), expected_user.encode("utf-8")) \
        and hmac.compare_digest(password.encode("utf-8"), expected_password.encode("utf-8"))
    if not valid:
        _recordLoginFailure(ip)
        time.sleep(0.15)
        return {"code": 401, "src": "invalid username or password"}, 401

    _clearLoginFailures(ip)
    session.clear()
    session.permanent = True
    session["monitor_user"] = expected_user
    return {"code": 0, "user": expected_user}


@monitor_bp.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return {"code": 0}


# ######################## data ########################

@monitor_bp.route("/api/overview")
@login_required
def overview():
    handler = _handler()
    store = MonitorStore()
    if not store.enabled:
        return _monitorDisabled()

    proxies = handler.getAll()
    store.recordProxySnapshot(proxies)

    return {
        "code": 0,
        "pool": _poolStats(proxies),
        "gateway": store.getGatewaySummary(24),
        "waf": {
            "rules_24h": store.getWafRuleCounts(24),
            "recent": store.getRecentWafEvents(10),
        },
        "strategy": _strategyState(store),
        "config": _configSummary(store),
        "generated_at": int(time.time()),
    }


@monitor_bp.route("/api/stream")
@login_required
def stream():
    store = MonitorStore()
    if not store.enabled:
        return _monitorDisabled()

    handler = _handler()
    response = Response(
        stream_with_context(_eventStream(handler, store)),
        mimetype="text/event-stream",
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    return response


@monitor_bp.route("/api/proxies")
@login_required
def proxies():
    handler = _handler()
    store = MonitorStore()
    if not store.enabled:
        return _monitorDisabled()

    try:
        page = max(int(request.args.get("page", 1)), 1)
        page_size = min(max(int(request.args.get("page_size", 20)), 1), 200)
    except (TypeError, ValueError):
        page, page_size = 1, 20

    query = str(request.args.get("q") or "").strip().lower()
    protocol = str(request.args.get("https") or "all").lower()
    source = str(request.args.get("source") or "").strip()
    status = str(request.args.get("status") or "all").lower()
    sort = str(request.args.get("sort") or "proxy")
    order = str(request.args.get("order") or "asc").lower()

    all_proxies = handler.getAll()
    sources = sorted({
        item for proxy in all_proxies
        for item in str(proxy.source or "").split("/") if item
    })
    regions = sorted({
        proxy.region for proxy in all_proxies if proxy.region
    })

    items = list(all_proxies)
    if query:
        items = [
            item for item in items
            if query in item.proxy.lower()
            or query in str(item.source or "").lower()
            or query in str(item.region or "").lower()
        ]
    if protocol == "https":
        items = [item for item in items if item.https]
    elif protocol == "http":
        items = [item for item in items if not item.https]
    if source:
        items = [
            item for item in items
            if source in str(item.source or "").split("/")
        ]
    if status == "healthy":
        items = [item for item in items if int(item.fail_count or 0) == 0]
    elif status == "failing":
        items = [item for item in items if int(item.fail_count or 0) > 0]

    sort_keys = {
        "proxy": lambda item: item.proxy,
        "fail_count": lambda item: int(item.fail_count or 0),
        "check_count": lambda item: int(item.check_count or 0),
        "last_time": lambda item: item.last_time or "",
    }
    items.sort(key=sort_keys.get(sort, sort_keys["proxy"]), reverse=(order == "desc"))

    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start:start + page_size]

    result = []
    for item in page_items:
        data = item.to_dict
        data["healthy"] = int(item.fail_count or 0) == 0
        result.append(data)

    return {
        "code": 0,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": result,
        "sources": sources,
        "regions": regions,
    }


@monitor_bp.route("/api/proxies/delete", methods=["POST"])
@login_required
def deleteProxy():
    data = request.get_json(silent=True) or {}
    proxy = str(data.get("proxy") or "").strip()
    if not proxy:
        return {"code": 400, "src": "proxy is required"}, 400

    handler = _handler()
    status = handler.delete(Proxy(proxy))
    return {"code": 0, "src": bool(status)}


@monitor_bp.route("/api/trends")
@login_required
def trends():
    store = MonitorStore()
    if not store.enabled:
        return _monitorDisabled()
    hours = _clampHours(request.args.get("hours", 24))
    return {
        "code": 0,
        "hours": hours,
        "proxy": store.getProxySnapshots(hours),
        "gateway": store.getGatewaySeries(hours),
    }


@monitor_bp.route("/api/waf")
@login_required
def waf():
    store = MonitorStore()
    if not store.enabled:
        return _monitorDisabled()
    hours = _clampHours(request.args.get("hours", 24))
    return {
        "code": 0,
        "hours": hours,
        "rules": store.getWafRuleCounts(hours),
        "recent": store.getRecentWafEvents(20),
    }


@monitor_bp.route("/api/config")
@login_required
def config():
    store = MonitorStore()
    if not store.enabled:
        return _monitorDisabled()
    return {"code": 0, "config": _configSummary(store)}


@monitor_bp.route("/api/strategy", methods=["POST"])
@login_required
def setStrategy():
    store = MonitorStore()
    if not store.enabled:
        return _monitorDisabled()

    data = request.get_json(silent=True) or {}
    raw = data.get("strategy")
    if raw in (None, "", "config", "default"):
        if not store.setRuntimeStrategy(None):
            return {"code": 503, "src": "monitor store unavailable"}, 503
        return {"code": 0, "strategy": _strategyState(store)}

    try:
        strategy = normalizeStrategy(raw)
    except UnknownStrategyError:
        return {
            "code": 400,
            "src": "unknown strategy",
            "supported": list(SUPPORTED_STRATEGIES),
        }, 400

    if not store.setRuntimeStrategy(strategy):
        return {"code": 503, "src": "monitor store unavailable"}, 503
    return {"code": 0, "strategy": _strategyState(store)}


@monitor_bp.route("/api/health")
@login_required
def health():
    store = MonitorStore()
    return {
        "code": 0,
        "version": VERSION,
        "store": store.health(),
    }
