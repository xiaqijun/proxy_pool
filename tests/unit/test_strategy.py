# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     test_strategy.py
   Description :   代理选择策略单元测试
   Author :        JHao
   date：          2026/10/26
-------------------------------------------------
   Change Activity:
                   2026/10/26:
-------------------------------------------------
"""
__author__ = 'JHao'

import pytest

from helper.proxy import Proxy
from helper.strategy import (
    STRATEGY_RANDOM,
    STRATEGY_ROUND_ROBIN,
    STRATEGY_WEIGHTED,
    StrategyManager,
    UnknownStrategyError,
    normalizeStrategy,
    proxyWeight,
)


def _proxies():
    return [
        Proxy("1.1.1.1:80", check_count=10, fail_count=0, last_status=True),
        Proxy("2.2.2.2:80", check_count=10, fail_count=5, last_status=True),
        Proxy("3.3.3.3:80", check_count=0, fail_count=0),
    ]


class TestNormalizeStrategy:

    def test_default_random(self):
        assert normalizeStrategy(None) == STRATEGY_RANDOM
        assert normalizeStrategy("") == STRATEGY_RANDOM

    def test_aliases(self):
        assert normalizeStrategy("RR") == STRATEGY_ROUND_ROBIN
        assert normalizeStrategy("round-robin") == STRATEGY_ROUND_ROBIN
        assert normalizeStrategy("weight") == STRATEGY_WEIGHTED
        assert normalizeStrategy("RAND") == STRATEGY_RANDOM

    def test_none_default(self):
        assert normalizeStrategy(None, default=None) is None
        assert normalizeStrategy("  ", default=None) is None

    def test_unknown(self):
        with pytest.raises(UnknownStrategyError):
            normalizeStrategy("not-exist")


class TestProxyWeight:

    def test_healthy_proxy_has_higher_weight(self):
        healthy = Proxy("1.1.1.1:80", check_count=10, fail_count=0, last_status=True)
        unhealthy = Proxy("2.2.2.2:80", check_count=10, fail_count=5, last_status=True)
        assert proxyWeight(healthy) > proxyWeight(unhealthy)

    def test_unchecked_proxy_base_weight(self):
        proxy = Proxy("1.1.1.1:80")
        assert proxyWeight(proxy) == 1.0

    def test_last_failed_is_penalized(self):
        ok = Proxy("1.1.1.1:80", check_count=10, fail_count=0, last_status=True)
        failed = Proxy("1.1.1.1:80", check_count=10, fail_count=0, last_status=False)
        assert proxyWeight(failed) < proxyWeight(ok)

    def test_weight_is_positive(self):
        proxy = Proxy("1.1.1.1:80", check_count=100, fail_count=100, last_status=False)
        assert proxyWeight(proxy) >= 0.01


class TestStrategyManager:

    def test_empty_returns_none(self):
        manager = StrategyManager()
        assert manager.select([], strategy=STRATEGY_RANDOM) is None
        assert manager.select(None, strategy=STRATEGY_WEIGHTED) is None

    def test_random_returns_member(self):
        manager = StrategyManager()
        proxies = _proxies()
        for _ in range(20):
            selected = manager.select(proxies, strategy=STRATEGY_RANDOM)
            assert selected in proxies

    def test_round_robin_cycles_in_stable_order(self):
        manager = StrategyManager()
        manager.reset()
        proxies = _proxies()
        selected = [manager.select(proxies, strategy=STRATEGY_ROUND_ROBIN, key="test").proxy
                    for _ in range(6)]
        assert selected == [
            "1.1.1.1:80",
            "2.2.2.2:80",
            "3.3.3.3:80",
            "1.1.1.1:80",
            "2.2.2.2:80",
            "3.3.3.3:80",
        ]

    def test_round_robin_order_independent_of_input_order(self):
        manager = StrategyManager()
        manager.reset()
        proxies = _proxies()
        first = manager.select(proxies, strategy=STRATEGY_ROUND_ROBIN, key="order")
        second = manager.select(list(reversed(proxies)), strategy=STRATEGY_ROUND_ROBIN, key="order")
        assert first.proxy != second.proxy

    def test_round_robin_keys_are_isolated(self):
        manager = StrategyManager()
        manager.reset()
        proxies = _proxies()
        assert manager.select(proxies, strategy=STRATEGY_ROUND_ROBIN, key="a").proxy == "1.1.1.1:80"
        assert manager.select(proxies, strategy=STRATEGY_ROUND_ROBIN, key="b").proxy == "1.1.1.1:80"
        assert manager.select(proxies, strategy=STRATEGY_ROUND_ROBIN, key="a").proxy == "2.2.2.2:80"

    def test_weighted_returns_member(self):
        manager = StrategyManager()
        proxies = _proxies()
        for _ in range(20):
            selected = manager.select(proxies, strategy=STRATEGY_WEIGHTED)
            assert selected in proxies

    def test_explicit_default(self):
        manager = StrategyManager()
        selected = manager.select(_proxies(), strategy=None, default=STRATEGY_WEIGHTED)
        assert selected is not None
