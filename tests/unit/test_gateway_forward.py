# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     test_gateway_forward.py
   Description :   代理网关真实转发测试（本地假上游代理）
   Author :        JHao
   date：          2026/10/26
-------------------------------------------------
   Change Activity:
                   2026/10/26:
-------------------------------------------------
"""
__author__ = 'JHao'

import asyncio
from unittest.mock import MagicMock, patch

from helper.proxy import Proxy
from gateway.proxyGateway import ProxyGateway, encodeBasicAuth


class FakeUpstreamProxy(object):
    """本地假上游代理：HTTP 模式直接响应，CONNECT 模式回显数据"""

    def __init__(self, mode):
        self.mode = mode
        self.server = None
        self.port = None
        self.received = []

    async def start(self):
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def handle(self, reader, writer):
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            self.received.append(head)
            if self.mode == "http":
                writer.write(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Length: 2\r\n"
                    b"Connection: close\r\n\r\n"
                    b"ok"
                )
                await writer.drain()
            elif self.mode == "waf":
                body = b"<html><title>Just a moment...</title></html>"
                writer.write(
                    b"HTTP/1.1 403 Forbidden\r\n"
                    b"Server: cloudflare\r\n"
                    b"Content-Type: text/html; charset=utf-8\r\n"
                    b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                    b"Connection: close\r\n\r\n" + body
                )
                await writer.drain()
            elif self.mode == "custom_waf":
                body = b"<html>custom block page</html>"
                writer.write(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: text/html; charset=utf-8\r\n"
                    b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                    b"Connection: close\r\n\r\n" + body
                )
                await writer.drain()
            elif self.mode == "http_body":
                length = 0
                for line in head.split(b"\r\n"):
                    if line.lower().startswith(b"content-length:"):
                        length = int(line.split(b":", 1)[1].strip())
                body = await reader.readexactly(length)
                self.received.append(body)
                writer.write(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                    b"Connection: close\r\n\r\n" + body
                )
                await writer.drain()
            else:
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                while True:
                    data = await reader.read(1024)
                    if not data:
                        break
                    writer.write(data)
                    await writer.drain()
        finally:
            writer.close()

    async def close(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()


async def _start_gateway(upstream_port=None, auth="", retry=1, upstream_auth=None,
                         proxies=None, waf_enabled=True, monitor=False):
    with patch("gateway.proxyGateway.ProxyHandler"):
        gateway = ProxyGateway(
            host="127.0.0.1",
            port=0,
            strategy="random",
            auth=auth,
            retry=retry,
            connect_timeout=2,
            header_timeout=2,
            monitor=monitor,
        )
    gateway.waf_enabled = waf_enabled
    if not waf_enabled:
        gateway.waf_detector = None

    gateway.proxy_handler = MagicMock()
    if proxies is not None:
        gateway.proxy_handler.get.side_effect = proxies
    else:
        proxy_address = "127.0.0.1:%d" % upstream_port
        if upstream_auth:
            proxy_address = "%s@%s" % (upstream_auth, proxy_address)
        gateway.proxy_handler.get.return_value = Proxy(proxy_address)

    server = await asyncio.start_server(gateway.handleClient, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return gateway, server, port


async def _test_http_forward():
    upstream = await FakeUpstreamProxy("http").start()
    gateway, server, gateway_port = await _start_gateway(upstream.port)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", gateway_port)
        writer.write(b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=3)
        assert b"200 OK" in response
        assert response.endswith(b"ok")
        assert upstream.received
        assert b"GET http://example.com/ HTTP/1.1" in upstream.received[0]
        assert b"Connection: close" in upstream.received[0]
        writer.close()
    finally:
        server.close()
        await server.wait_closed()
        await upstream.close()


async def _test_http_body_forward():
    upstream = await FakeUpstreamProxy("http_body").start()
    gateway, server, gateway_port = await _start_gateway(upstream.port)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", gateway_port)
        writer.write(
            b"POST http://example.com/ HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Length: 5\r\n\r\n"
            b"hello"
        )
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=3)
        assert b"200 OK" in response
        assert response.endswith(b"hello")
        assert upstream.received[-1] == b"hello"
        writer.close()
    finally:
        server.close()
        await server.wait_closed()
        await upstream.close()


async def _test_connect_tunnel():
    upstream = await FakeUpstreamProxy("connect").start()
    gateway, server, gateway_port = await _start_gateway(upstream.port)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", gateway_port)
        writer.write(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
        await writer.drain()

        response_head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=3)
        assert b"200 Connection Established" in response_head
        assert upstream.received
        assert b"CONNECT example.com:443 HTTP/1.1" in upstream.received[0]

        writer.write(b"ping")
        await writer.drain()
        echoed = await asyncio.wait_for(reader.readexactly(4), timeout=3)
        assert echoed == b"ping"
        writer.close()
    finally:
        server.close()
        await server.wait_closed()
        await upstream.close()


async def _test_upstream_auth():
    upstream = await FakeUpstreamProxy("http").start()
    gateway, server, gateway_port = await _start_gateway(
        upstream.port, upstream_auth="upuser:uppass"
    )
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", gateway_port)
        writer.write(b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=3)
        assert b"200 OK" in response
        assert upstream.received
        expected = encodeBasicAuth("upuser:uppass").encode("iso-8859-1")
        assert expected in upstream.received[0]
        writer.close()
    finally:
        server.close()
        await server.wait_closed()
        await upstream.close()


async def _test_waf_retry_switches_proxy():
    waf_upstream = await FakeUpstreamProxy("waf").start()
    ok_upstream = await FakeUpstreamProxy("http").start()
    gateway, server, gateway_port = await _start_gateway(
        retry=3,
        proxies=[
            Proxy("127.0.0.1:%d" % waf_upstream.port),
            Proxy("127.0.0.1:%d" % ok_upstream.port),
        ],
    )
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", gateway_port)
        writer.write(b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=3)
        assert response.startswith(b"HTTP/1.1 200")
        assert response.endswith(b"ok")
        assert waf_upstream.received
        assert ok_upstream.received
        assert b"X-ProxyPool-WAF" not in response
        writer.close()
    finally:
        server.close()
        await server.wait_closed()
        await waf_upstream.close()
        await ok_upstream.close()


async def _test_waf_all_blocked_returns_response():
    waf_upstream = await FakeUpstreamProxy("waf").start()
    gateway, server, gateway_port = await _start_gateway(
        retry=3,
        proxies=[
            Proxy("127.0.0.1:%d" % waf_upstream.port),
            None,
        ],
    )
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", gateway_port)
        writer.write(b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=3)
        assert response.startswith(b"HTTP/1.1 403")
        assert b"X-ProxyPool-WAF: cloudflare" in response
        assert b"Just a moment" in response
        writer.close()
    finally:
        server.close()
        await server.wait_closed()
        await waf_upstream.close()


async def _test_waf_post_body_replayed():
    waf_upstream = await FakeUpstreamProxy("waf").start()
    ok_upstream = await FakeUpstreamProxy("http_body").start()
    gateway, server, gateway_port = await _start_gateway(
        retry=3,
        proxies=[
            Proxy("127.0.0.1:%d" % waf_upstream.port),
            Proxy("127.0.0.1:%d" % ok_upstream.port),
        ],
    )
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", gateway_port)
        writer.write(
            b"POST http://example.com/ HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Length: 5\r\n\r\n"
            b"hello"
        )
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=3)
        assert response.startswith(b"HTTP/1.1 200")
        assert response.endswith(b"hello")
        assert ok_upstream.received[-1] == b"hello"
        writer.close()
    finally:
        server.close()
        await server.wait_closed()
        await waf_upstream.close()
        await ok_upstream.close()


async def _test_waf_disabled_no_retry():
    waf_upstream = await FakeUpstreamProxy("waf").start()
    gateway, server, gateway_port = await _start_gateway(
        retry=3,
        proxies=[Proxy("127.0.0.1:%d" % waf_upstream.port)],
        waf_enabled=False,
    )
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", gateway_port)
        writer.write(b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=3)
        assert response.startswith(b"HTTP/1.1 403")
        assert b"X-ProxyPool-WAF" not in response
        writer.close()
    finally:
        server.close()
        await server.wait_closed()
        await waf_upstream.close()


async def _test_waf_custom_keyword():
    from helper.waf import WafDetector

    custom_upstream = await FakeUpstreamProxy("custom_waf").start()
    ok_upstream = await FakeUpstreamProxy("http").start()
    gateway, server, gateway_port = await _start_gateway(
        retry=3,
        proxies=[
            Proxy("127.0.0.1:%d" % custom_upstream.port),
            Proxy("127.0.0.1:%d" % ok_upstream.port),
        ],
    )
    gateway.waf_detector = WafDetector(custom_keywords=["custom block page"])
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", gateway_port)
        writer.write(b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=3)
        assert response.startswith(b"HTTP/1.1 200")
        assert response.endswith(b"ok")
        assert custom_upstream.received
        assert ok_upstream.received
        writer.close()
    finally:
        server.close()
        await server.wait_closed()
        await custom_upstream.close()
        await ok_upstream.close()


async def _test_waf_metrics_recorded():
    waf_upstream = await FakeUpstreamProxy("waf").start()
    ok_upstream = await FakeUpstreamProxy("http").start()
    monitor = MagicMock()
    gateway, server, gateway_port = await _start_gateway(
        retry=3,
        proxies=[
            Proxy("127.0.0.1:%d" % waf_upstream.port),
            Proxy("127.0.0.1:%d" % ok_upstream.port),
        ],
        monitor=monitor,
    )
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", gateway_port)
        writer.write(b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=3)
        assert response.startswith(b"HTTP/1.1 200")
        assert monitor.recordGatewayRequest.called
        kwargs = monitor.recordGatewayRequest.call_args.kwargs
        assert kwargs["success"] is True
        assert kwargs["blocked"] is False
        assert kwargs["retries"] == 1
        assert kwargs["waf_hits"][0]["rule"] == "cloudflare"
        writer.close()
    finally:
        server.close()
        await server.wait_closed()
        await waf_upstream.close()
        await ok_upstream.close()


async def _test_gateway_metrics_store():
    from monitor.monitorStore import MonitorStore

    store = MonitorStore()
    waf_upstream = await FakeUpstreamProxy("waf").start()
    ok_upstream = await FakeUpstreamProxy("http").start()
    gateway, server, gateway_port = await _start_gateway(
        retry=3,
        proxies=[
            Proxy("127.0.0.1:%d" % waf_upstream.port),
            Proxy("127.0.0.1:%d" % ok_upstream.port),
        ],
        monitor=store,
    )
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", gateway_port)
        writer.write(b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=3)
        assert response.startswith(b"HTTP/1.1 200")

        store.flush()
        summary = store.getGatewaySummary(24)
        assert summary["requests"] == 1
        assert summary["success"] == 1
        assert summary["waf_detected"] == 1
        assert summary["retries"] == 1
        rules = store.getWafRuleCounts(24)
        assert rules[0]["rule"] == "cloudflare"
        writer.close()
    finally:
        server.close()
        await server.wait_closed()
        await waf_upstream.close()
        await ok_upstream.close()
        store.stop()


async def _test_auth_required():
    gateway, server, gateway_port = await _start_gateway(1, auth="user:pass")
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", gateway_port)
        writer.write(b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=3)
        assert b"407" in response
        assert b"Proxy-Authenticate" in response
        writer.close()
    finally:
        server.close()
        await server.wait_closed()


def test_http_forward():
    asyncio.run(_test_http_forward())


def test_http_body_forward():
    asyncio.run(_test_http_body_forward())


def test_connect_tunnel():
    asyncio.run(_test_connect_tunnel())


def test_upstream_auth():
    asyncio.run(_test_upstream_auth())


def test_waf_retry_switches_proxy():
    asyncio.run(_test_waf_retry_switches_proxy())


def test_waf_all_blocked_returns_response():
    asyncio.run(_test_waf_all_blocked_returns_response())


def test_waf_post_body_replayed():
    asyncio.run(_test_waf_post_body_replayed())


def test_waf_disabled_no_retry():
    asyncio.run(_test_waf_disabled_no_retry())


def test_waf_custom_keyword():
    asyncio.run(_test_waf_custom_keyword())


def test_waf_metrics_recorded():
    asyncio.run(_test_waf_metrics_recorded())


def test_gateway_metrics_store():
    asyncio.run(_test_gateway_metrics_store())


def test_auth_required():
    asyncio.run(_test_auth_required())
