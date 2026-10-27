# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     ProxyHandler.py
   Description :
   Author :       JHao
   date：          2016/12/3
-------------------------------------------------
   Change Activity:
                   2016/12/03:
                   2020/05/26: 区分http和https
-------------------------------------------------
"""
__author__ = 'JHao'

from helper.proxy import Proxy
from helper.strategy import STRATEGY_RANDOM, StrategyManager, normalizeStrategy
from db.dbClient import DbClient
from handler.configHandler import ConfigHandler


class ProxyHandler(object):
    """ Proxy CRUD operator"""

    def __init__(self):
        self.conf = ConfigHandler()
        self.db = DbClient(self.conf.dbConn)
        self.db.changeTable(self.conf.tableName)

    def get(self, https=False, strategy=None, key=None, exclude=None):
        """
        return a proxy

        默认行为保持不变：不指定策略且不排除代理时，直接调用 DbClient.get 随机取一个。
        指定策略后从代理列表中按 random/round_robin/weighted 选择。

        Args:
            https: True/False
            strategy: 代理选择策略，None 表示使用默认行为
            key: 轮询状态 key
            exclude: 需要排除的代理地址集合
        Returns:
            Proxy 或 None
        """
        normalized_strategy = normalizeStrategy(strategy, default=None)

        # 随机策略且无需排除代理时，复用 DbClient.get，避免读取整个代理池
        if not exclude and (normalized_strategy == STRATEGY_RANDOM
                            or (normalized_strategy is None and not strategy)):
            proxy = self.db.get(https)
            return Proxy.createFromJson(proxy) if proxy else None

        proxies = self.getAll(https)
        if exclude:
            excluded = set(exclude)
            proxies = [item for item in proxies if item.proxy not in excluded]
        if not proxies:
            return None

        if normalized_strategy is None:
            normalized_strategy = normalizeStrategy(self.conf.defaultStrategy)
        return StrategyManager().select(proxies, strategy=normalized_strategy, key=key)

    def pop(self, https):
        """
        return and delete a useful proxy
        :return:
        """
        proxy = self.db.pop(https)
        if proxy:
            return Proxy.createFromJson(proxy)
        return None

    def put(self, proxy):
        """
        put proxy into use proxy
        :return:
        """
        self.db.put(proxy)

    def delete(self, proxy):
        """
        delete useful proxy
        :param proxy:
        :return:
        """
        return self.db.delete(proxy.proxy)

    def getAll(self, https=False):
        """
        get all proxy from pool as Proxy list
        :return:
        """
        proxies = self.db.getAll(https)
        return [Proxy.createFromJson(_) for _ in proxies]

    def exists(self, proxy):
        """
        check proxy exists
        :param proxy:
        :return:
        """
        return self.db.exists(proxy.proxy)

    def getCount(self):
        """
        return raw_proxy and use_proxy count
        :return:
        """
        total_use_proxy = self.db.getCount()
        return {'count': total_use_proxy}
