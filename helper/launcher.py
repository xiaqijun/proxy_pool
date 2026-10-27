# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     launcher
   Description :   启动器
   Author :        JHao
   date：          2021/3/26
-------------------------------------------------
   Change Activity:
                   2021/3/26: 启动器
-------------------------------------------------
"""
__author__ = 'JHao'

import sys
from db.dbClient import DbClient
from handler.logHandler import LogHandler
from handler.configHandler import ConfigHandler

log = LogHandler('launcher')


def startServer():
    __beforeStart()
    from api.proxyApi import runFlask
    runFlask()


def startScheduler():
    __beforeStart()
    from helper.scheduler import runScheduler
    runScheduler()


def startGateway():
    __beforeStart()
    from gateway.proxyGateway import runGateway
    runGateway()


def startAll():
    """同时启动 API 服务和代理网关"""
    __beforeStart()
    conf = ConfigHandler()

    if conf.gatewayEnabled:
        import threading
        from gateway.proxyGateway import ProxyGateway

        gateway = ProxyGateway()
        gateway_thread = threading.Thread(
            target=gateway.run,
            name="proxy-gateway",
            daemon=True,
        )
        gateway_thread.start()
        log.info("Proxy gateway started in background thread")

    from api.proxyApi import runFlask
    runFlask()


def __beforeStart():
    __showVersion()
    __showConfigure()
    if not __checkStrategy():
        log.info('exit!')
        sys.exit()
    if __checkDBConfig():
        log.info('exit!')
        sys.exit()


def __showVersion():
    from setting import VERSION
    log.info("ProxyPool Version: %s" % VERSION)


def __showConfigure():
    conf = ConfigHandler()
    log.info("ProxyPool configure HOST: %s" % conf.serverHost)
    log.info("ProxyPool configure PORT: %s" % conf.serverPort)
    exclude = conf.fetcherExclude
    if exclude:
        log.info("ProxyPool configure PROXY_FETCHER_EXCLUDE: %s" % exclude)
    log.info("ProxyPool configure PROXY_FETCHER: auto-scan (enabled=True, exclude=%s)" % exclude)
    log.info("ProxyPool configure PROXY_STRATEGY: %s" % conf.defaultStrategy)
    if conf.gatewayEnabled:
        log.info("ProxyPool configure GATEWAY: %s:%s (strategy=%s, auth=%s)" % (
            conf.gatewayHost,
            conf.gatewayPort,
            conf.gatewayStrategy,
            "on" if conf.gatewayAuth else "off",
        ))
        log.info("ProxyPool configure WAF: %s (threshold=%s)" % (
            "on" if conf.wafDetectEnabled else "off",
            conf.wafScoreThreshold,
        ))

    if conf.monitorEnabled:
        log.info("ProxyPool configure MONITOR: /dashboard/ (auth=%s)" % (
            "on" if conf.monitorAuthPassword else "off",
        ))
        if conf.monitorAuthPassword in ("", "change-me"):
            log.warning("Monitor dashboard uses the default password; "
                        "set MONITOR_AUTH_PASSWORD before exposing it")


def __checkStrategy():
    """检查代理选择策略配置是否合法"""
    from helper.strategy import UnknownStrategyError, normalizeStrategy

    conf = ConfigHandler()
    strategies = [("PROXY_STRATEGY", conf.defaultStrategy)]
    if conf.gatewayEnabled:
        strategies.append(("GATEWAY_STRATEGY", conf.gatewayStrategy))

    for name, value in strategies:
        try:
            normalizeStrategy(value)
        except UnknownStrategyError as error:
            log.error("%s invalid: %s" % (name, error))
            return False
    return True


def __checkDBConfig():
    conf = ConfigHandler()
    db = DbClient(conf.dbConn)
    log.info("============ DATABASE CONFIGURE ================")
    log.info("DB_TYPE: %s" % db.db_type)
    log.info("DB_HOST: %s" % db.db_host)
    log.info("DB_PORT: %s" % db.db_port)
    log.info("DB_NAME: %s" % db.db_name)
    log.info("DB_USER: %s" % db.db_user)
    log.info("=================================================")
    return db.test()
