# -*- coding: utf-8 -*-
# !/usr/bin/env python
"""
-------------------------------------------------
   File Name：     ProxyApi.py
   Description :   WebApi
   Author :       JHao
   date：          2016/12/4
-------------------------------------------------
   Change Activity:
                   2016/12/04: WebApi
                   2019/08/14: 集成Gunicorn启动方式
                   2020/06/23: 新增pop接口
                   2022/07/21: 更新count接口
-------------------------------------------------
"""
__author__ = 'JHao'

import platform
from werkzeug.wrappers import Response
from flask import Flask, jsonify, request

from util.six import iteritems
from helper.proxy import Proxy
from helper.strategy import (
    STRATEGY_DESCRIPTIONS,
    STRATEGY_RANDOM,
    SUPPORTED_STRATEGIES,
    UnknownStrategyError,
    normalizeStrategy,
)
from handler.proxyHandler import ProxyHandler
from handler.configHandler import ConfigHandler
from monitor.monitorApi import initMonitorApp

app = Flask(__name__)
conf = ConfigHandler()
proxy_handler = ProxyHandler()
initMonitorApp(app, proxy_handler)


class JsonResponse(Response):
    @classmethod
    def force_type(cls, response, environ=None):
        if isinstance(response, (dict, list)):
            response = jsonify(response)

        return super(JsonResponse, cls).force_type(response, environ)


app.response_class = JsonResponse

api_list = [
    {"url": "/get", "params": "type: ''https'|''; strategy: 'random'|'round_robin'|'weighted'; format: 'json'|'text'",
     "desc": "get a proxy with the specified strategy"},
    {"url": "/pop", "params": "type: ''https'|''", "desc": "get and delete a proxy"},
    {"url": "/delete", "params": "proxy: 'e.g. 127.0.0.1:8080'", "desc": "delete an unable proxy"},
    {"url": "/all", "params": "type: ''https'|''", "desc": "get all proxy from proxy pool"},
    {"url": "/count", "params": "", "desc": "return proxy count"},
    {"url": "/strategies", "params": "", "desc": "list supported proxy selection strategies"},
    {"url": "/gateway", "params": "", "desc": "show gateway and WAF config"},
    {"url": "/dashboard/", "params": "requires login", "desc": "monitoring dashboard"},
    # 'refresh': 'refresh proxy pool',
]


def _requestedStrategy():
    """兼容 strategy 和 mode 两个参数名"""
    return request.args.get("strategy") or request.args.get("mode")


def _defaultStrategy():
    try:
        default = normalizeStrategy(conf.defaultStrategy, default=STRATEGY_RANDOM)
    except UnknownStrategyError:
        default = STRATEGY_RANDOM

    # 监控工作台可以在线覆盖默认策略
    try:
        from monitor.monitorStore import MonitorStore
        effective = MonitorStore().getRuntimeStrategy(default)
        return normalizeStrategy(effective, default=default)
    except Exception:
        return default


@app.route('/')
def index():
    return {'url': api_list, 'dashboard': '/dashboard/'}


@app.route('/get/')
def get():
    https = request.args.get("type", "").lower() == 'https'
    output_format = request.args.get("format", "").lower()

    try:
        strategy = normalizeStrategy(_requestedStrategy(), default=None)
    except UnknownStrategyError:
        return {
            "code": 0,
            "src": "unknown strategy",
            "supported": list(SUPPORTED_STRATEGIES),
        }, 400

    # 默认配置为 random 时保持原有 /get 行为；配置为其他策略时按配置执行
    if strategy is None:
        default_strategy = _defaultStrategy()
        if default_strategy != STRATEGY_RANDOM:
            strategy = default_strategy

    if strategy and strategy != STRATEGY_RANDOM:
        key = "api:get:%s" % ("https" if https else "http")
        proxy = proxy_handler.get(https, strategy=strategy, key=key)
    else:
        # random 直接复用原有 DbClient.get 随机逻辑，避免全量读取代理
        proxy = proxy_handler.get(https)

    if not proxy:
        if output_format == "text":
            return Response("no proxy", status=503, mimetype="text/plain")
        return {"code": 0, "src": "no proxy"}

    if output_format == "text":
        return Response(proxy.proxy, mimetype="text/plain")
    return proxy.to_dict


@app.route('/pop/')
def pop():
    https = request.args.get("type", "").lower() == 'https'
    proxy = proxy_handler.pop(https)
    return proxy.to_dict if proxy else {"code": 0, "src": "no proxy"}


@app.route('/refresh/')
def refresh():
    # TODO refresh会有守护程序定时执行，由api直接调用性能较差，暂不使用
    return 'success'


@app.route('/all/')
def getAll():
    https = request.args.get("type", "").lower() == 'https'
    proxies = proxy_handler.getAll(https)
    return jsonify([_.to_dict for _ in proxies])


@app.route('/delete/', methods=['GET'])
def delete():
    proxy = request.args.get('proxy')
    status = proxy_handler.delete(Proxy(proxy))
    return {"code": 0, "src": status}


@app.route('/count/')
def getCount():
    proxies = proxy_handler.getAll()
    http_type_dict = {}
    source_dict = {}
    for proxy in proxies:
        http_type = 'https' if proxy.https else 'http'
        http_type_dict[http_type] = http_type_dict.get(http_type, 0) + 1
        for source in proxy.source.split('/'):
            source_dict[source] = source_dict.get(source, 0) + 1
    return {"http_type": http_type_dict, "source": source_dict, "count": len(proxies)}


@app.route('/strategies/')
def getStrategies():
    return {
        "default": _defaultStrategy(),
        "supported": [
            {"name": name, "description": STRATEGY_DESCRIPTIONS[name]}
            for name in SUPPORTED_STRATEGIES
        ],
    }


@app.route('/gateway/')
def getGateway():
    return {
        "enabled": conf.gatewayEnabled,
        "address": "%s:%s" % (conf.gatewayHost, conf.gatewayPort),
        "strategy": conf.gatewayStrategy,
        "auth": bool(conf.gatewayAuth),
        "retry": conf.gatewayRetry,
        "connect_timeout": conf.gatewayConnectTimeout,
        "header_timeout": conf.gatewayHeaderTimeout,
        "waf": {
            "enabled": conf.wafDetectEnabled,
            "score_threshold": conf.wafScoreThreshold,
            "body_prefix_size": conf.wafBodyPrefixSize,
            "max_replay_body": conf.wafMaxReplayBody,
            "custom_headers": len(conf.wafCustomHeaders),
            "custom_keywords": len(conf.wafCustomKeywords),
            "custom_status": conf.wafCustomStatus,
        },
    }


def runFlask():
    if platform.system() == "Windows":
        app.run(host=conf.serverHost, port=conf.serverPort)
    else:
        import gunicorn.app.base

        class StandaloneApplication(gunicorn.app.base.BaseApplication):

            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super(StandaloneApplication, self).__init__()

            def load_config(self):
                _config = dict([(key, value) for key, value in iteritems(self.options)
                                if key in self.cfg.settings and value is not None])
                for key, value in iteritems(_config):
                    self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        _options = {
            'bind': '%s:%s' % (conf.serverHost, conf.serverPort),
            'workers': 4,
            'accesslog': '-',  # log to stdout
            'access_log_format': '%(h)s %(l)s %(t)s "%(r)s" %(s)s "%(a)s"'
        }
        StandaloneApplication(app, _options).run()


if __name__ == '__main__':
    runFlask()
