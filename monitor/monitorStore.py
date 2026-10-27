# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     monitorStore.py
   Description :   监控指标 SQLite 存储
   Author :        JHao
   date：          2026/10/26
-------------------------------------------------
   Change Activity:
                   2026/10/26: 代理趋势、网关统计、WAF 事件和运行时策略
-------------------------------------------------
"""
__author__ = 'JHao'

import atexit
import contextlib
import json
import os
import queue
import sqlite3
import threading
import time

from handler.configHandler import ConfigHandler
from handler.logHandler import LogHandler
from util.singleton import Singleton
from util.six import withMetaclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS proxy_snapshots (
    minute INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL,
    total INTEGER NOT NULL DEFAULT 0,
    http INTEGER NOT NULL DEFAULT 0,
    https INTEGER NOT NULL DEFAULT 0,
    sources TEXT NOT NULL DEFAULT '{}',
    regions TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS gateway_stats (
    minute INTEGER PRIMARY KEY,
    requests INTEGER NOT NULL DEFAULT 0,
    success INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    waf_detected INTEGER NOT NULL DEFAULT 0,
    waf_blocked INTEGER NOT NULL DEFAULT 0,
    retries INTEGER NOT NULL DEFAULT 0,
    latency_sum INTEGER NOT NULL DEFAULT 0,
    latency_max INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS waf_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    rule TEXT NOT NULL DEFAULT '',
    score INTEGER NOT NULL DEFAULT 0,
    target TEXT NOT NULL DEFAULT '',
    proxy TEXT NOT NULL DEFAULT '',
    retried INTEGER NOT NULL DEFAULT 0,
    blocked INTEGER NOT NULL DEFAULT 0,
    final_status INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_waf_events_ts ON waf_events(ts);
CREATE INDEX IF NOT EXISTS idx_waf_events_rule ON waf_events(rule);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at INTEGER
);
"""

UPSERT_GATEWAY_STATS = """
INSERT INTO gateway_stats (
    minute, requests, success, errors, waf_detected,
    waf_blocked, retries, latency_sum, latency_max
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(minute) DO UPDATE SET
    requests = requests + excluded.requests,
    success = success + excluded.success,
    errors = errors + excluded.errors,
    waf_detected = waf_detected + excluded.waf_detected,
    waf_blocked = waf_blocked + excluded.waf_blocked,
    retries = retries + excluded.retries,
    latency_sum = latency_sum + excluded.latency_sum,
    latency_max = MAX(latency_max, excluded.latency_max)
"""

UPSERT_SNAPSHOT = """
INSERT INTO proxy_snapshots (minute, ts, total, http, https, sources, regions)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(minute) DO UPDATE SET
    ts = excluded.ts,
    total = excluded.total,
    http = excluded.http,
    https = excluded.https,
    sources = excluded.sources,
    regions = excluded.regions
"""

INSERT_WAF_EVENT = """
INSERT INTO waf_events (ts, rule, score, target, proxy, retried, blocked, final_status)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

STRATEGY_SETTING = "strategy_override"


class MonitorStore(withMetaclass(Singleton)):
    """监控指标存储，多进程通过同一个 SQLite 文件共享"""

    def __init__(self):
        self.conf = ConfigHandler()
        self.enabled = self.conf.monitorEnabled
        self.path = self.conf.monitorDbPath
        self.retention_days = max(int(self.conf.monitorRetentionDays), 1)
        self.log = LogHandler("monitor")

        self._ready = False
        self._failed = False
        self._init_lock = threading.RLock()
        self._strategy_lock = threading.RLock()
        self._strategy_cache_time = 0
        self._strategy_cache_value = None

        self._last_snapshot_minute = None
        self._last_prune = 0
        self._writer = None
        self._writer_stop = threading.Event()
        self._queue = queue.Queue(maxsize=10000)

    # ######################## init / connection ########################

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _ensureReady(self):
        if not self.enabled:
            return False
        if self._ready:
            return True
        if self._failed:
            return False

        with self._init_lock:
            if self._ready:
                return True
            if self._failed:
                return False

            try:
                parent = os.path.dirname(self.path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                conn = self._connect()
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.executescript(SCHEMA)
                    conn.commit()
                finally:
                    conn.close()
                self._ready = True
                return True
            except Exception as error:
                self._failed = True
                self.log.error("Monitor store init failed: %s" % error, exc_info=True)
                return False

    # ######################## gateway metrics ########################

    def recordGatewayRequest(self, target, proxy, status, success, retries,
                             waf_hits=None, latency_ms=0, blocked=False):
        """记录一次网关请求；非阻塞，由后台线程批量写入"""
        if not self._ensureReady():
            return

        event = {
            "ts": int(time.time()),
            "target": str(target or "")[:2048],
            "proxy": str(proxy or "")[:256],
            "status": int(status or 0),
            "success": bool(success),
            "retries": max(int(retries or 0), 0),
            "waf_hits": waf_hits or [],
            "latency_ms": max(int(latency_ms or 0), 0),
            "blocked": bool(blocked),
        }

        self._ensureWriter()
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            # 监控不能阻塞代理流量，队列满时丢弃指标
            self.log.warning("Monitor queue is full, drop gateway metric")

    def _ensureWriter(self):
        if self._writer is not None:
            return
        with self._init_lock:
            if self._writer is not None:
                return
            self._writer_stop.clear()
            self._writer = threading.Thread(
                target=self._writerLoop,
                name="monitor-writer",
                daemon=True,
            )
            self._writer.start()
            atexit.register(self.stop)

    def _writerLoop(self):
        batch = []
        while True:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                item = None

            if item is None:
                if batch:
                    self._flushBatch(batch)
                    batch = []
                if self._writer_stop.is_set():
                    break
                continue

            if item.get("type") == "stop":
                break
            if item.get("type") == "flush":
                if batch:
                    self._flushBatch(batch)
                    batch = []
                item.get("done").set()
                continue

            batch.append(item)
            if len(batch) >= 100:
                self._flushBatch(batch)
                batch = []

        if batch:
            self._flushBatch(batch)

    def _flushBatch(self, batch):
        stats = {}
        waf_rows = []

        for event in batch:
            minute = event["ts"] // 60
            row = stats.setdefault(minute, {
                "requests": 0, "success": 0, "errors": 0,
                "waf_detected": 0, "waf_blocked": 0, "retries": 0,
                "latency_sum": 0, "latency_max": 0,
            })

            row["requests"] += 1
            if event["success"]:
                row["success"] += 1
            elif not event["blocked"]:
                row["errors"] += 1
            if event["waf_hits"]:
                row["waf_detected"] += 1
            if event["blocked"]:
                row["waf_blocked"] += 1
            row["retries"] += event["retries"]
            row["latency_sum"] += event["latency_ms"]
            row["latency_max"] = max(row["latency_max"], event["latency_ms"])

            for hit in event["waf_hits"]:
                waf_rows.append((
                    event["ts"],
                    str(hit.get("rule", ""))[:64],
                    int(hit.get("score", 0) or 0),
                    str(hit.get("target", event["target"]))[:2048],
                    str(hit.get("proxy", event["proxy"]))[:256],
                    1 if hit.get("retried") else 0,
                    1 if hit.get("blocked") else 0,
                    event["status"],
                ))

        try:
            conn = self._connect()
            try:
                rows = [
                    (minute, data["requests"], data["success"], data["errors"],
                     data["waf_detected"], data["waf_blocked"], data["retries"],
                     data["latency_sum"], data["latency_max"])
                    for minute, data in stats.items()
                ]
                conn.executemany(UPSERT_GATEWAY_STATS, rows)
                if waf_rows:
                    conn.executemany(INSERT_WAF_EVENT, waf_rows)
                conn.commit()
            finally:
                conn.close()
        except Exception as error:
            self.log.warning("Monitor flush failed: %s" % error, exc_info=True)

    def flush(self):
        """等待后台队列写入完成，主要供测试和退出时使用"""
        if self._writer is None:
            return
        done = threading.Event()
        try:
            self._queue.put({"type": "flush", "done": done}, timeout=1)
        except queue.Full:
            return
        done.wait(timeout=3)

    def stop(self):
        writer = self._writer
        if writer is None:
            return
        self._writer_stop.set()
        with contextlib.suppress(Exception):
            self._queue.put_nowait({"type": "stop"})
        writer.join(timeout=3)
        self._writer = None

    # ######################## proxy snapshots ########################

    def recordProxySnapshot(self, proxies):
        """记录代理池当前快照，同一分钟只记录一次"""
        if not self._ensureReady():
            return

        minute = int(time.time() // 60)
        if self._last_snapshot_minute == minute:
            return
        self._last_snapshot_minute = minute

        proxies = list(proxies or [])
        total = len(proxies)
        https_count = sum(1 for item in proxies if getattr(item, "https", False))
        http_count = total - https_count
        sources = {}
        regions = {}

        for item in proxies:
            for source in str(getattr(item, "source", "") or "").split("/"):
                if source:
                    sources[source] = sources.get(source, 0) + 1
            region = str(getattr(item, "region", "") or "")
            if region:
                regions[region] = regions.get(region, 0) + 1

        try:
            conn = self._connect()
            try:
                conn.execute(UPSERT_SNAPSHOT, (
                    minute,
                    minute * 60,
                    total,
                    http_count,
                    https_count,
                    json.dumps(sources, ensure_ascii=False),
                    json.dumps(regions, ensure_ascii=False),
                ))
                conn.commit()
            finally:
                conn.close()
            self._pruneIfNeeded()
        except Exception as error:
            self.log.warning("Monitor snapshot failed: %s" % error, exc_info=True)

    def getProxySnapshots(self, hours=24):
        if not self._ensureReady():
            return []
        since = int(time.time()) - max(int(hours), 1) * 3600
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT minute, ts, total, http, https, sources, regions "
                    "FROM proxy_snapshots WHERE ts >= ? ORDER BY ts ASC",
                    (since,),
                ).fetchall()
                result = []
                for row in rows:
                    item = dict(row)
                    with contextlib.suppress(Exception):
                        item["sources"] = json.loads(item.get("sources") or "{}")
                    with contextlib.suppress(Exception):
                        item["regions"] = json.loads(item.get("regions") or "{}")
                    result.append(item)
                return result
            finally:
                conn.close()
        except Exception as error:
            self.log.warning("Read proxy snapshots failed: %s" % error, exc_info=True)
            return []

    # ######################## gateway / waf queries ########################

    def getGatewaySummary(self, hours=24):
        empty = {
            "requests": 0, "success": 0, "errors": 0,
            "waf_detected": 0, "waf_blocked": 0, "retries": 0,
            "latency_sum": 0, "latency_max": 0,
            "success_rate": 0.0, "avg_latency_ms": 0.0,
        }
        if not self._ensureReady():
            return empty

        since_minute = int((time.time() - max(int(hours), 1) * 3600) // 60)
        try:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT "
                    "COALESCE(SUM(requests), 0) AS requests, "
                    "COALESCE(SUM(success), 0) AS success, "
                    "COALESCE(SUM(errors), 0) AS errors, "
                    "COALESCE(SUM(waf_detected), 0) AS waf_detected, "
                    "COALESCE(SUM(waf_blocked), 0) AS waf_blocked, "
                    "COALESCE(SUM(retries), 0) AS retries, "
                    "COALESCE(SUM(latency_sum), 0) AS latency_sum, "
                    "COALESCE(MAX(latency_max), 0) AS latency_max "
                    "FROM gateway_stats WHERE minute >= ?",
                    (since_minute,),
                ).fetchone()
                result = dict(row)
                requests = result.get("requests", 0) or 0
                if requests:
                    result["success_rate"] = round(
                        (result.get("success", 0) or 0) * 100.0 / requests, 2
                    )
                    result["avg_latency_ms"] = round(
                        (result.get("latency_sum", 0) or 0) / requests, 2
                    )
                else:
                    result["success_rate"] = 0.0
                    result["avg_latency_ms"] = 0.0
                return result
            finally:
                conn.close()
        except Exception as error:
            self.log.warning("Read gateway summary failed: %s" % error, exc_info=True)
            return empty

    def getGatewaySeries(self, hours=24):
        if not self._ensureReady():
            return []
        since_minute = int((time.time() - max(int(hours), 1) * 3600) // 60)
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT minute, requests, success, errors, waf_detected, "
                    "waf_blocked, retries, latency_sum, latency_max "
                    "FROM gateway_stats WHERE minute >= ? ORDER BY minute ASC",
                    (since_minute,),
                ).fetchall()
                result = []
                for row in rows:
                    item = dict(row)
                    item["ts"] = item["minute"] * 60
                    result.append(item)
                return result
            finally:
                conn.close()
        except Exception as error:
            self.log.warning("Read gateway series failed: %s" % error, exc_info=True)
            return []

    def getWafRuleCounts(self, hours=24):
        if not self._ensureReady():
            return []
        since = int(time.time()) - max(int(hours), 1) * 3600
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT rule, COUNT(*) AS count, COALESCE(SUM(blocked), 0) AS blocked "
                    "FROM waf_events WHERE ts >= ? AND rule != '' "
                    "GROUP BY rule ORDER BY count DESC",
                    (since,),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()
        except Exception as error:
            self.log.warning("Read WAF counts failed: %s" % error, exc_info=True)
            return []

    def getRecentWafEvents(self, limit=20):
        if not self._ensureReady():
            return []
        try:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT ts, rule, score, target, proxy, retried, blocked, final_status "
                    "FROM waf_events ORDER BY ts DESC, id DESC LIMIT ?",
                    (max(int(limit), 1),),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()
        except Exception as error:
            self.log.warning("Read recent WAF events failed: %s" % error, exc_info=True)
            return []

    # ######################## settings / runtime strategy ########################

    def getSetting(self, key, default=None):
        if not self._ensureReady():
            return default
        try:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT value FROM settings WHERE key = ?", (key,)
                ).fetchone()
                return row["value"] if row else default
            finally:
                conn.close()
        except Exception as error:
            self.log.warning("Read monitor setting failed: %s" % error, exc_info=True)
            return default

    def setSetting(self, key, value):
        if not self._ensureReady():
            return False
        try:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                    "updated_at = excluded.updated_at",
                    (key, value, int(time.time())),
                )
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as error:
            self.log.warning("Write monitor setting failed: %s" % error, exc_info=True)
            return False

    def deleteSetting(self, key):
        if not self._ensureReady():
            return False
        try:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM settings WHERE key = ?", (key,))
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as error:
            self.log.warning("Delete monitor setting failed: %s" % error, exc_info=True)
            return False

    def getRuntimeStrategy(self, default):
        """读取运行时策略覆盖，2 秒进程内缓存以降低 SQLite 读取频率"""
        if not self.enabled:
            return default

        now = time.time()
        with self._strategy_lock:
            if now - self._strategy_cache_time < 2:
                value = self._strategy_cache_value
            else:
                value = self.getSetting(STRATEGY_SETTING)
                self._strategy_cache_value = value
                self._strategy_cache_time = now
        return value or default

    def setRuntimeStrategy(self, value):
        if value in (None, "", "config", "default"):
            ok = self.deleteSetting(STRATEGY_SETTING)
            value = None
        else:
            ok = self.setSetting(STRATEGY_SETTING, str(value))
        with self._strategy_lock:
            self._strategy_cache_value = value
            self._strategy_cache_time = time.time()
        return ok

    # ######################## maintenance ########################

    def _pruneIfNeeded(self):
        now = int(time.time())
        if now - self._last_prune < 3600:
            return
        self._last_prune = now
        cutoff = now - self.retention_days * 86400
        minute_cutoff = cutoff // 60

        try:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM proxy_snapshots WHERE minute < ?", (minute_cutoff,))
                conn.execute("DELETE FROM gateway_stats WHERE minute < ?", (minute_cutoff,))
                conn.execute("DELETE FROM waf_events WHERE ts < ?", (cutoff,))
                conn.commit()
            finally:
                conn.close()
        except Exception as error:
            self.log.warning("Monitor prune failed: %s" % error, exc_info=True)

    def health(self):
        if not self._ensureReady():
            return {"ok": False, "enabled": self.enabled, "path": self.path}
        try:
            conn = self._connect()
            try:
                conn.execute("SELECT 1").fetchone()
            finally:
                conn.close()
            return {
                "ok": True,
                "enabled": self.enabled,
                "path": self.path,
                "size": os.path.getsize(self.path) if os.path.exists(self.path) else 0,
            }
        except Exception as error:
            return {"ok": False, "enabled": self.enabled, "error": str(error)}
