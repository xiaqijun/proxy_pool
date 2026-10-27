# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     test_monitor_store.py
   Description :   监控指标 SQLite 存储测试
   Author :        JHao
   date：          2026/10/26
-------------------------------------------------
   Change Activity:
                   2026/10/26:
-------------------------------------------------
"""
__author__ = 'JHao'

from helper.proxy import Proxy
from monitor.monitorStore import MonitorStore
from util.singleton import Singleton


def _proxies():
    return [
        Proxy("1.1.1.1:80", source="srcA", region="CN", https=False, fail_count=0),
        Proxy("2.2.2.2:443", source="srcB/srcA", region="US", https=True, fail_count=2),
    ]


class TestProxySnapshot:

    def test_record_and_read_snapshot(self):
        store = MonitorStore()
        store.recordProxySnapshot(_proxies())

        points = store.getProxySnapshots(24)
        assert len(points) == 1
        point = points[0]
        assert point["total"] == 2
        assert point["http"] == 1
        assert point["https"] == 1
        assert point["sources"] == {"srcA": 2, "srcB": 1}
        assert point["regions"] == {"CN": 1, "US": 1}

    def test_same_minute_is_throttled(self):
        store = MonitorStore()
        store.recordProxySnapshot(_proxies())
        store.recordProxySnapshot([])

        points = store.getProxySnapshots(24)
        assert len(points) == 1
        assert points[0]["total"] == 2


class TestGatewayMetrics:

    def test_summary_and_series(self):
        store = MonitorStore()
        store.recordGatewayRequest(
            target="http://example.com/",
            proxy="1.1.1.1:80",
            status=200,
            success=True,
            retries=0,
            waf_hits=[],
            latency_ms=10,
        )
        store.recordGatewayRequest(
            target="http://example.com/",
            proxy="2.2.2.2:80",
            status=403,
            success=False,
            retries=1,
            waf_hits=[{
                "rule": "cloudflare",
                "score": 5,
                "target": "http://example.com/",
                "proxy": "2.2.2.2:80",
                "retried": False,
                "blocked": True,
            }],
            latency_ms=30,
            blocked=True,
        )
        store.flush()

        summary = store.getGatewaySummary(24)
        assert summary["requests"] == 2
        assert summary["success"] == 1
        assert summary["errors"] == 0
        assert summary["waf_detected"] == 1
        assert summary["waf_blocked"] == 1
        assert summary["retries"] == 1
        assert summary["success_rate"] == 50.0
        assert summary["avg_latency_ms"] == 20.0

        series = store.getGatewaySeries(24)
        assert len(series) == 1
        assert series[0]["requests"] == 2
        assert series[0]["ts"] % 60 == 0

        rules = store.getWafRuleCounts(24)
        assert rules == [{"rule": "cloudflare", "count": 1, "blocked": 1}]

        recent = store.getRecentWafEvents(10)
        assert len(recent) == 1
        assert recent[0]["rule"] == "cloudflare"
        assert recent[0]["blocked"] == 1
        store.stop()

    def test_retried_waf_counts(self):
        store = MonitorStore()
        store.recordGatewayRequest(
            target="http://example.com/",
            proxy="1.1.1.1:80",
            status=200,
            success=True,
            retries=1,
            waf_hits=[{
                "rule": "akamai",
                "score": 4,
                "target": "http://example.com/",
                "proxy": "1.1.1.1:80",
                "retried": True,
                "blocked": False,
            }],
            latency_ms=50,
        )
        store.flush()

        summary = store.getGatewaySummary(24)
        assert summary["requests"] == 1
        assert summary["success"] == 1
        assert summary["waf_detected"] == 1
        assert summary["waf_blocked"] == 0
        assert summary["retries"] == 1

        rules = store.getWafRuleCounts(24)
        assert rules == [{"rule": "akamai", "count": 1, "blocked": 0}]
        store.stop()


class TestRuntimeStrategy:

    def test_set_get_reset(self):
        store = MonitorStore()
        assert store.getRuntimeStrategy("random") == "random"

        assert store.setRuntimeStrategy("weighted") is True
        assert store.getRuntimeStrategy("random") == "weighted"

        assert store.setRuntimeStrategy(None) is True
        assert store.getRuntimeStrategy("random") == "random"

    def test_disabled_store(self, monkeypatch):
        Singleton._inst.clear()
        monkeypatch.setenv("MONITOR_ENABLED", "false")
        store = MonitorStore()

        assert store.enabled is False
        assert store.getProxySnapshots(24) == []
        assert store.getGatewaySummary(24)["requests"] == 0
        assert store.getRuntimeStrategy("random") == "random"
        assert store.health()["ok"] is False


class TestMonitorHealth:

    def test_health_ok(self):
        store = MonitorStore()
        health = store.health()
        assert health["ok"] is True
        assert health["enabled"] is True
        assert health["size"] >= 0
