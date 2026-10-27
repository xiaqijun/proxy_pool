# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     test_gateway.py
   Description :   代理网关单元测试
   Author :        JHao
   date：          2026/10/26
-------------------------------------------------
   Change Activity:
                   2026/10/26:
-------------------------------------------------
"""
__author__ = 'JHao'

import base64
from unittest.mock import MagicMock, patch

import pytest

from helper.proxy import Proxy
from gateway.proxyGateway import (
    ProxyGateway,
    RequestHead,
    buildConnectHead,
    buildHttpRequestHead,
    encodeBasicAuth,
    getHeader,
    maskProxy,
    parseBasicAuth,
    parseProxyAddress,
    removeHeader,
    resolveStrategyFromHeaders,
    setHeader,
    splitHeader,
)


def _basic(username, password):
    token = base64.b64encode(("%s:%s" % (username, password)).encode("utf-8")).decode("ascii")
    return "Basic " + token


def _request_head(auth=None, method="GET", target="http://example.com/"):
    lines = ["%s %s HTTP/1.1" % (method, target), "Host: example.com"]
    if auth:
        lines.append("Proxy-Authorization: " + auth)
    lines.append("")
    lines.append("")
    return RequestHead("\r\n".join(lines).encode("iso-8859-1"))


class TestParseProxyAddress:

    def test_plain(self):
        assert parseProxyAddress("1.2.3.4:8080") == ("1.2.3.4", 8080, None)

    def test_with_auth(self):
        assert parseProxyAddress("user:pass@1.2.3.4:8080") == ("1.2.3.4", 8080, "user:pass")

    def test_ipv6(self):
        assert parseProxyAddress("[::1]:8080") == ("::1", 8080, None)

    @pytest.mark.parametrize("value", ["", "1.2.3.4", "1.2.3.4:abc",
                                       "1.2.3.4:70000", ":8080"])
    def test_invalid(self, value):
        with pytest.raises(ValueError):
            parseProxyAddress(value)


class TestMaskProxy:

    def test_mask_auth(self):
        assert maskProxy("user:pass@1.2.3.4:8080") == "***@1.2.3.4:8080"

    def test_plain(self):
        assert maskProxy("1.2.3.4:8080") == "1.2.3.4:8080"


class TestHeaderHelpers:

    def test_split_header(self):
        start_line, headers = splitHeader(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n"
        )
        assert start_line == "HTTP/1.1 200 OK"
        assert headers == [("Content-Type", "text/plain")]

    def test_get_header_case_insensitive(self):
        headers = [("Content-Type", "text/plain")]
        assert getHeader(headers, "content-type") == "text/plain"
        assert getHeader(headers, "X-Not-Exist") is None

    def test_remove_header(self):
        headers = [("A", "1"), ("b", "2")]
        assert removeHeader(headers, "a") == [("b", "2")]

    def test_set_header(self):
        headers = [("A", "1"), ("a", "2")]
        assert setHeader(headers, "A", "3") == [("A", "3")]


class TestBasicAuth:

    def test_roundtrip(self):
        value = encodeBasicAuth("user:pass")
        assert parseBasicAuth(value) == ("user", "pass")

    def test_invalid(self):
        assert parseBasicAuth(None) is None
        assert parseBasicAuth("Bearer token") is None
        assert parseBasicAuth("Basic !!!") is None


class TestRequestHead:

    def test_parse(self):
        head = _request_head()
        assert head.method == "GET"
        assert head.target == "http://example.com/"
        assert head.version == "HTTP/1.1"
        assert head.getHeader("host") == "example.com"

    def test_invalid_request_line(self):
        with pytest.raises(ValueError):
            RequestHead(b"INVALID\r\n\r\n")


class TestBuildHeads:

    def test_build_http_request_head(self):
        head = buildHttpRequestHead(
            "GET", "http://example.com/", "HTTP/1.1",
            [("Host", "example.com"),
             ("Proxy-Authorization", "Basic client"),
             ("Proxy-Connection", "keep-alive")],
            auth="upstream:pass",
        )
        text = head.decode("iso-8859-1")
        assert "GET http://example.com/ HTTP/1.1" in text
        assert "Connection: close" in text
        assert "Basic client" not in text
        assert "Proxy-Connection" not in text
        assert encodeBasicAuth("upstream:pass") in text

    def test_build_connect_head(self):
        text = buildConnectHead("example.com:443", auth="upstream:pass").decode("iso-8859-1")
        assert text.startswith("CONNECT example.com:443 HTTP/1.1")
        assert "Host: example.com:443" in text
        assert encodeBasicAuth("upstream:pass") in text


class TestStrategyFromHeaders:

    def test_default(self):
        headers = [("Host", "example.com")]
        assert resolveStrategyFromHeaders(headers, "random") == "random"

    def test_strategy_username(self):
        headers = [("Proxy-Authorization", _basic("round_robin", "pass"))]
        assert resolveStrategyFromHeaders(headers, "random") == "round_robin"

    def test_non_strategy_username(self):
        headers = [("Proxy-Authorization", _basic("user", "pass"))]
        assert resolveStrategyFromHeaders(headers, "weighted") == "weighted"


class TestProxyGatewayAuth:

    @staticmethod
    def _gateway(auth="user:pass"):
        with patch("gateway.proxyGateway.ProxyHandler"):
            return ProxyGateway(
                host="127.0.0.1",
                port=0,
                strategy="random",
                auth=auth,
                retry=2,
                monitor=False,
            )

    def test_no_auth_configured(self):
        gateway = self._gateway(auth="")
        assert gateway.checkAuth(_request_head()) is True

    def test_exact_auth(self):
        gateway = self._gateway()
        assert gateway.checkAuth(_request_head(_basic("user", "pass"))) is True
        assert gateway.checkAuth(_request_head(_basic("user", "bad"))) is False
        assert gateway.checkAuth(_request_head()) is False

    def test_strategy_username_with_valid_password(self):
        gateway = self._gateway()
        assert gateway.checkAuth(_request_head(_basic("weighted", "pass"))) is True
        assert gateway.checkAuth(_request_head(_basic("weighted", "bad"))) is False

    def test_resolve_strategy(self):
        gateway = self._gateway()
        assert gateway.resolveStrategy(_request_head(_basic("round_robin", "pass"))) == "round_robin"
        assert gateway.resolveStrategy(_request_head(_basic("user", "pass"))) == "random"


class TestSelectProxy:

    @staticmethod
    def _gateway():
        with patch("gateway.proxyGateway.ProxyHandler"):
            return ProxyGateway(
                host="127.0.0.1", port=0, strategy="random", auth="", monitor=False
            )

    def test_fallback_to_all_proxies(self):
        gateway = self._gateway()
        gateway.proxy_handler = MagicMock()
        proxy = Proxy("1.2.3.4:8080")
        gateway.proxy_handler.get.side_effect = [None, proxy]

        result = gateway.selectProxy(https=True, strategy="random", exclude=set())

        assert result is proxy
        assert gateway.proxy_handler.get.call_count == 2
        first_call = gateway.proxy_handler.get.call_args_list[0]
        second_call = gateway.proxy_handler.get.call_args_list[1]
        assert first_call.kwargs["https"] is True
        assert second_call.kwargs["https"] is False

    def test_returns_none_when_pool_empty(self):
        gateway = self._gateway()
        gateway.proxy_handler = MagicMock()
        gateway.proxy_handler.get.return_value = None

        assert gateway.selectProxy(https=True, strategy="random") is None
