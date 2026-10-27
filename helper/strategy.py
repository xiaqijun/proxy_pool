# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     strategy.py
   Description :   代理选择策略（随机/轮询/加权）
   Author :        JHao
   date：          2026/10/26
-------------------------------------------------
   Change Activity:
                   2026/10/26: 新增随机、轮询、加权三种代理更换方式
-------------------------------------------------
"""
__author__ = 'JHao'

import random
import threading

from util.singleton import Singleton
from util.six import withMetaclass

STRATEGY_RANDOM = "random"
STRATEGY_ROUND_ROBIN = "round_robin"
STRATEGY_WEIGHTED = "weighted"

STRATEGY_ALIASES = {
    "random": STRATEGY_RANDOM,
    "rand": STRATEGY_RANDOM,
    "round_robin": STRATEGY_ROUND_ROBIN,
    "round-robin": STRATEGY_ROUND_ROBIN,
    "rr": STRATEGY_ROUND_ROBIN,
    "weighted": STRATEGY_WEIGHTED,
    "weight": STRATEGY_WEIGHTED,
    "wrr": STRATEGY_WEIGHTED,
}

STRATEGY_DESCRIPTIONS = {
    STRATEGY_RANDOM: "随机选择，每次请求独立随机，默认策略",
    STRATEGY_ROUND_ROBIN: "轮询选择，按代理地址稳定排序后依次返回",
    STRATEGY_WEIGHTED: "加权随机，校验成功率越高、失败次数越少的代理权重越大",
}

SUPPORTED_STRATEGIES = tuple(STRATEGY_DESCRIPTIONS.keys())


class UnknownStrategyError(ValueError):
    """未知的代理选择策略"""

    def __init__(self, name):
        self.name = name
        super(UnknownStrategyError, self).__init__(
            "unknown strategy: %s, supported: %s" % (name, ", ".join(SUPPORTED_STRATEGIES))
        )


def normalizeStrategy(name, default=STRATEGY_RANDOM):
    """
    将策略名称/别名转换为标准名称

    Args:
        name: 策略名称，可以为 None/空字符串
        default: name 为空时返回的默认策略，传 None 表示不设置默认值
    Returns:
        标准策略名称或 default
    Raises:
        UnknownStrategyError: 策略名称不受支持
    """
    if name is None or str(name).strip() == "":
        return default

    key = str(name).strip().lower()
    if key not in STRATEGY_ALIASES:
        raise UnknownStrategyError(name)
    return STRATEGY_ALIASES[key]


def proxyWeight(proxy):
    """
    根据代理历史校验结果计算加权随机权重

    权重规则：
        1. 未校验过的代理给予基础权重 1.0；
        2. 成功率越高权重越大（成功率平方，放大高质量代理）；
        3. 失败次数越多权重越低；
        4. 最近一次校验失败时权重减半；
        5. 最小权重 0.01，避免完全无法被选中。

    Args:
        proxy: Proxy 对象
    Returns:
        float
    """
    check_count = max(int(proxy.check_count or 0), 0)
    fail_count = max(int(proxy.fail_count or 0), 0)

    if check_count <= 0:
        weight = 1.0
    else:
        success_count = max(check_count - fail_count, 0)
        success_rate = float(success_count) / check_count
        weight = success_rate * success_rate
        weight = weight / (1.0 + fail_count)

    if proxy.last_status is False:
        weight *= 0.5

    return max(weight, 0.01)


class RandomStrategy(object):
    """随机选择"""

    name = STRATEGY_RANDOM

    def select(self, proxies, key=None):
        return random.choice(proxies)

    def reset(self, key=None):
        pass


class RoundRobinStrategy(object):
    """轮询选择，进程内保存每个 key 的游标"""

    name = STRATEGY_ROUND_ROBIN

    def __init__(self):
        self._lock = threading.Lock()
        self._cursor = {}

    def select(self, proxies, key=None):
        # 稳定排序，避免 Redis hash 返回顺序变化导致轮询重复
        ordered = sorted(proxies, key=lambda item: item.proxy)
        state_key = key or "default"
        with self._lock:
            index = self._cursor.get(state_key, 0) % len(ordered)
            self._cursor[state_key] = index + 1
        return ordered[index]

    def reset(self, key=None):
        with self._lock:
            if key is None:
                self._cursor.clear()
            else:
                self._cursor.pop(key, None)


class WeightedStrategy(object):
    """加权随机"""

    name = STRATEGY_WEIGHTED

    def select(self, proxies, key=None):
        weights = [proxyWeight(proxy) for proxy in proxies]
        return random.choices(proxies, weights=weights, k=1)[0]

    def reset(self, key=None):
        pass


class StrategyManager(withMetaclass(Singleton)):
    """策略管理器"""

    def __init__(self):
        self._strategies = {
            STRATEGY_RANDOM: RandomStrategy(),
            STRATEGY_ROUND_ROBIN: RoundRobinStrategy(),
            STRATEGY_WEIGHTED: WeightedStrategy(),
        }

    def select(self, proxies, strategy=None, key=None, default=STRATEGY_RANDOM):
        """
        从代理列表中按策略选择一个

        Args:
            proxies: Proxy 列表
            strategy: 策略名称/别名，为空时使用 default
            key: 轮询状态 key，建议按用途/协议区分
            default: strategy 为空时的默认策略
        Returns:
            Proxy 或 None
        """
        proxy_list = list(proxies or [])
        if not proxy_list:
            return None

        name = normalizeStrategy(strategy, default=default)
        if name is None:
            name = STRATEGY_RANDOM
        return self._strategies[name].select(proxy_list, key=key)

    def reset(self, strategy=None, key=None):
        """重置策略内部状态，主要用于测试或运行时切换"""
        if strategy is None:
            for item in self._strategies.values():
                item.reset()
            return
        name = normalizeStrategy(strategy)
        self._strategies[name].reset(key=key)
