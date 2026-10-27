# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     proxyGateway.py
   Description :   稳定代理池网关，按策略自动更换上游代理
   Author :        JHao
   date：          2026/10/26
-------------------------------------------------
   Change Activity:
                   2026/10/26: 支持 HTTP 转发、HTTPS CONNECT 隧道及多种代理更换方式
-------------------------------------------------
"""
__author__ = 'JHao'

import asyncio
import base64
import contextlib
import time

from handler.configHandler import ConfigHandler
from handler.logHandler import LogHandler
from handler.proxyHandler import ProxyHandler
from monitor.monitorStore import MonitorStore
from helper.strategy import (
    STRATEGY_ALIASES,
    UnknownStrategyError,
    normalizeStrategy,
)
from helper.waf import NO_WAF, WafDetector

CRLF = "\r\n"
BUFFER_SIZE = 64 * 1024
MAX_HEADER_SIZE = 64 * 1024

HTTP_REASONS = {
    200: "OK",
    400: "Bad Request",
    407: "Proxy Authentication Required",
    408: "Request Timeout",
    502: "Bad Gateway",
    504: "Gateway Timeout",
}


class RequestBodyError(Exception):
    """客户端请求体读取失败，无法安全重试"""
    pass


def parseProxyAddress(proxy):
    """
    将上游代理地址拆分为 (host, port, auth)

    Args:
        proxy: [username:password@]host:port
    Returns:
        (host, port, auth)
    """
    if not proxy or not str(proxy).strip():
        raise ValueError("empty proxy address")

    proxy = str(proxy).strip()
    auth = None
    host_port = proxy

    if "@" in proxy:
        auth, host_port = proxy.rsplit("@", 1)
        auth = auth or None
        if not host_port:
            raise ValueError("invalid proxy address: %s" % proxy)

    if host_port.startswith("["):
        end = host_port.find("]")
        if end == -1:
            raise ValueError("invalid proxy address: %s" % proxy)
        host = host_port[1:end]
        rest = host_port[end + 1:]
        if not rest.startswith(":"):
            raise ValueError("invalid proxy address: %s" % proxy)
        port_text = rest[1:]
    else:
        host, sep, port_text = host_port.rpartition(":")
        if not sep or not host:
            raise ValueError("invalid proxy address: %s" % proxy)

    if not host:
        raise ValueError("invalid proxy address: %s" % proxy)

    try:
        port = int(port_text)
    except (TypeError, ValueError):
        raise ValueError("invalid proxy port: %s" % proxy)

    if not 0 < port < 65536:
        raise ValueError("invalid proxy port: %s" % proxy)

    return host, port, auth


def splitHeader(raw):
    """
    解析 HTTP 请求/响应头

    Args:
        raw: 包含结束空行的原始头部字节
    Returns:
        (start_line, headers)，headers 为 (name, value) 列表
    """
    text = raw.decode("iso-8859-1", errors="replace")
    head, _, _ = text.partition("\r\n\r\n")
    lines = head.split("\r\n")
    if not lines or not lines[0]:
        raise ValueError("empty http header")

    start_line = lines[0]
    headers = []
    for line in lines[1:]:
        if not line:
            continue
        name, sep, value = line.partition(":")
        if not sep:
            continue
        headers.append((name.strip(), value.strip()))
    return start_line, headers


def getHeader(headers, name):
    """读取头部，大小写不敏感"""
    lower_name = name.lower()
    for key, value in headers:
        if key.lower() == lower_name:
            return value
    return None


def removeHeader(headers, name):
    """删除头部，返回新列表"""
    lower_name = name.lower()
    return [(key, value) for key, value in headers if key.lower() != lower_name]


def setHeader(headers, name, value):
    """设置头部，覆盖同名头"""
    headers = removeHeader(headers, name)
    headers.append((name, value))
    return headers


def maskProxy(proxy):
    """隐藏上游代理认证信息，避免日志泄漏账号密码"""
    if proxy and "@" in str(proxy):
        return "***@" + str(proxy).rsplit("@", 1)[1]
    return str(proxy)


def encodeBasicAuth(auth):
    """username:password -> Basic xxx"""
    token = base64.b64encode(str(auth).encode("utf-8")).decode("ascii")
    return "Basic " + token


def parseBasicAuth(value):
    """Basic xxx -> (username, password)"""
    if not value:
        return None
    scheme, sep, token = value.partition(" ")
    if not sep or scheme.lower() != "basic":
        return None
    try:
        decoded = base64.b64decode(token.strip()).decode("utf-8")
    except Exception:
        return None
    username, sep, password = decoded.partition(":")
    if not sep:
        return None
    return username, password


def resolveStrategyFromHeaders(headers, default):
    """
    从 Proxy-Authorization 用户名中解析策略，便于同一个网关地址切换更换方式。

    例如：
        http://round_robin:password@127.0.0.1:5011
        http://weighted:password@127.0.0.1:5011
    """
    auth = parseBasicAuth(getHeader(headers, "Proxy-Authorization"))
    if auth:
        username = auth[0].strip().lower()
        if username in STRATEGY_ALIASES:
            try:
                return normalizeStrategy(username)
            except UnknownStrategyError:
                pass
    return default


def buildHttpRequestHead(method, target, version, headers, auth=None):
    """构造转发给上游代理的 HTTP 请求头"""
    headers = removeHeader(headers, "Proxy-Authorization")
    headers = removeHeader(headers, "Proxy-Connection")
    headers = setHeader(headers, "Connection", "close")
    if auth:
        headers = setHeader(headers, "Proxy-Authorization", encodeBasicAuth(auth))

    lines = ["%s %s %s" % (method, target, version)]
    lines.extend("%s: %s" % (key, value) for key, value in headers)
    lines.append("")
    lines.append("")
    return CRLF.join(lines).encode("iso-8859-1", errors="replace")


def buildConnectHead(target, auth=None):
    """构造 CONNECT 请求头"""
    headers = [("Host", target), ("Proxy-Connection", "keep-alive")]
    if auth:
        headers.append(("Proxy-Authorization", encodeBasicAuth(auth)))

    lines = ["CONNECT %s HTTP/1.1" % target]
    lines.extend("%s: %s" % (key, value) for key, value in headers)
    lines.append("")
    lines.append("")
    return CRLF.join(lines).encode("iso-8859-1", errors="replace")


class RequestHead(object):
    """客户端请求头"""

    def __init__(self, raw):
        start_line, headers = splitHeader(raw)
        parts = start_line.split(" ", 2)
        if len(parts) != 3:
            raise ValueError("invalid request line: %s" % start_line)

        self.method, self.target, self.version = parts
        if not self.method or not self.target or not self.version.upper().startswith("HTTP/"):
            raise ValueError("invalid request line: %s" % start_line)
        self.headers = headers
        self.raw = raw

    def getHeader(self, name):
        return getHeader(self.headers, name)


def parseStatusLine(status_line):
    """解析 HTTP 状态行，返回状态码"""
    parts = status_line.split(" ", 2)
    if len(parts) < 2 or not parts[1].isdigit():
        raise ValueError("invalid status line: %s" % status_line)
    return int(parts[1])


def addWafHeaders(response_head, waf_result):
    """在 WAF 响应头中追加检测结果，便于调用方识别"""
    start_line, headers = splitHeader(response_head)
    headers = removeHeader(headers, "X-ProxyPool-WAF")
    headers = removeHeader(headers, "X-ProxyPool-WAF-Score")
    headers.append(("X-ProxyPool-WAF", waf_result.rule))
    headers.append(("X-ProxyPool-WAF-Score", str(waf_result.score)))

    lines = [start_line]
    lines.extend("%s: %s" % (key, value) for key, value in headers)
    lines.append("")
    lines.append("")
    return CRLF.join(lines).encode("iso-8859-1", errors="replace")


class ProxyGateway(object):
    """
    稳定代理池网关

    客户端将 host:port 配置为 HTTP 代理，网关为每个请求按策略选择上游代理：
        - 普通 HTTP 请求：转发绝对 URI 到上游代理；
        - HTTPS 请求：通过 CONNECT 建立隧道。
    """

    def __init__(self, host=None, port=None, strategy=None, auth=None, retry=None,
                 connect_timeout=None, header_timeout=None, monitor=None):
        self.conf = ConfigHandler()
        self.host = host if host is not None else self.conf.gatewayHost
        self.port = int(port if port is not None else self.conf.gatewayPort)
        self.strategy = normalizeStrategy(strategy or self.conf.gatewayStrategy)
        self.auth = auth if auth is not None else self.conf.gatewayAuth
        self.retry = max(int(retry if retry is not None else self.conf.gatewayRetry), 1)
        self.connect_timeout = float(
            connect_timeout if connect_timeout is not None else self.conf.gatewayConnectTimeout
        )
        self.header_timeout = float(
            header_timeout if header_timeout is not None else self.conf.gatewayHeaderTimeout
        )

        self.waf_enabled = bool(self.conf.wafDetectEnabled)
        self.waf_body_prefix_size = max(int(self.conf.wafBodyPrefixSize), 0)
        self.waf_body_read_timeout = max(float(self.conf.wafBodyReadTimeout), 0.1)
        self.waf_max_replay_body = max(int(self.conf.wafMaxReplayBody), 0)
        self.waf_detector = None
        if self.waf_enabled:
            self.waf_detector = WafDetector(
                threshold=self.conf.wafScoreThreshold,
                custom_headers=self.conf.wafCustomHeaders,
                custom_keywords=self.conf.wafCustomKeywords,
                custom_status=self.conf.wafCustomStatus,
            )

        if monitor is False:
            self.monitor = None
        elif monitor is None:
            try:
                self.monitor = MonitorStore()
            except Exception:
                self.monitor = None
        else:
            self.monitor = monitor

        self.proxy_handler = ProxyHandler()
        self.log = LogHandler("gateway")
        self._server = None

    async def start(self):
        self._server = await asyncio.start_server(
            self.handleClient, self.host, self.port, limit=MAX_HEADER_SIZE
        )
        addresses = ", ".join(str(sock.getsockname()) for sock in (self._server.sockets or []))
        self.log.info("Proxy gateway listening on %s (strategy=%s)" % (addresses, self.strategy))
        if self.waf_enabled:
            self.log.info("WAF detection enabled (threshold=%s)" % self.conf.wafScoreThreshold)
        if not self.auth and self.host in ("0.0.0.0", "::", ""):
            self.log.warning("Proxy gateway is open to the network; set GATEWAY_AUTH to enable authentication")
        async with self._server:
            await self._server.serve_forever()

    def run(self):
        """阻塞运行网关，供 CLI / 后台线程调用"""
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            self.log.info("Proxy gateway stopped")
        except Exception as error:
            self.log.error("Proxy gateway error: %s" % error, exc_info=True)
            raise

    async def handleClient(self, reader, writer):
        peer = writer.get_extra_info("peername")
        try:
            try:
                raw_head = await asyncio.wait_for(
                    reader.readuntil(b"\r\n\r\n"), timeout=self.header_timeout
                )
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError,
                    asyncio.TimeoutError, ConnectionError):
                await self.sendError(writer, 400, "Bad Request")
                return

            if len(raw_head) > MAX_HEADER_SIZE:
                await self.sendError(writer, 400, "Request Header Too Large")
                return

            try:
                request_head = RequestHead(raw_head)
            except ValueError as error:
                self.log.warning("Invalid request from %s: %s" % (peer, error))
                await self.sendError(writer, 400, "Bad Request")
                return

            if not self.checkAuth(request_head):
                await self.sendError(
                    writer,
                    407,
                    "Proxy Authentication Required",
                    extra_headers={"Proxy-Authenticate": 'Basic realm="ProxyPool"'},
                )
                return

            if request_head.method.upper() == "CONNECT":
                await self.handleConnect(request_head, reader, writer, peer)
            else:
                await self.handleHttp(request_head, reader, writer, peer)
        except Exception as error:
            self.log.error("Gateway request error from %s: %s" % (peer, error), exc_info=True)
            with contextlib.suppress(Exception):
                await self.sendError(writer, 502, "Bad Gateway")
        finally:
            self.closeWriter(writer)

    async def handleHttp(self, request_head, client_reader, client_writer, peer):
        """转发普通 HTTP 请求，并在响应命中 WAF 时切换代理重试"""
        started_at = time.monotonic()
        target = request_head.target
        if not target.lower().startswith("http://"):
            if target.lower().startswith("https://"):
                await self.sendError(client_writer, 400, "Use CONNECT for HTTPS")
                return
            host = request_head.getHeader("Host")
            if not host:
                await self.sendError(client_writer, 400, "Missing Host Header")
                return
            if not target.startswith("/"):
                target = "/" + target
            target = "http://%s%s" % (host, target)

        strategy = self.resolveStrategy(request_head)

        try:
            replay_body = await self.readReplayBody(request_head, client_reader)
        except asyncio.TimeoutError:
            await self.sendError(client_writer, 408, "Request Timeout")
            return
        except RequestBodyError as error:
            self.log.warning("Read request body from %s failed: %s" % (peer, error))
            await self.sendError(client_writer, 400, "Invalid Request Body")
            return

        excluded = set()
        last_error = None
        client_responded = False
        pending_proxy = None
        last_proxy = ""
        waf_hits = []
        waf_retry_count = 0

        for attempt in range(self.retry):
            if pending_proxy is not None:
                proxy = pending_proxy
                pending_proxy = None
            else:
                proxy = self.selectProxy(https=False, strategy=strategy, exclude=excluded)
            if proxy is None:
                break
            excluded.add(proxy.proxy)
            last_proxy = proxy.proxy

            try:
                upstream_reader, upstream_writer, auth = await self.openUpstream(proxy)
            except Exception as error:
                last_error = error
                self.log.warning("Connect upstream %s failed: %s" % (maskProxy(proxy.proxy), error))
                continue

            body_task = None
            body_started = False
            response_started = False

            try:
                head = buildHttpRequestHead(
                    request_head.method, target, request_head.version,
                    request_head.headers, auth=auth,
                )
                upstream_writer.write(head)

                if replay_body is not None:
                    if replay_body:
                        upstream_writer.write(replay_body)
                    await upstream_writer.drain()
                else:
                    await upstream_writer.drain()
                    body_task = asyncio.ensure_future(
                        self.pipeRequestBody(client_reader, upstream_writer)
                    )
                    body_started = True

                response_head, response_headers, status = await self.readFinalResponseHead(
                    upstream_reader, client_writer
                )

                waf_result = NO_WAF
                prefix = b""
                if self.waf_enabled:
                    prefix = await self.readWafBodyPrefix(
                        upstream_reader, status, request_head, response_headers
                    )
                    waf_result = self.waf_detector.detect(status, response_headers, prefix)

                if waf_result.matched:
                    if replay_body is not None and attempt + 1 < self.retry:
                        # 先确认还有下一个代理可用；没有则直接返回当前 WAF 响应
                        candidate = self.selectProxy(
                            https=False, strategy=strategy, exclude=excluded
                        )
                        if candidate is not None:
                            pending_proxy = candidate
                            waf_hits.append({
                                "rule": waf_result.rule,
                                "score": waf_result.score,
                                "target": target,
                                "proxy": maskProxy(proxy.proxy),
                                "retried": True,
                                "blocked": False,
                            })
                            waf_retry_count += 1
                            self.log.warning(
                                "WAF %s detected (score=%s) via %s, retry %s/%s: %s" % (
                                    waf_result.rule, waf_result.score, maskProxy(proxy.proxy),
                                    attempt + 1, self.retry, target,
                                )
                            )
                            last_error = "waf:%s" % waf_result.rule
                            continue

                    waf_hits.append({
                        "rule": waf_result.rule,
                        "score": waf_result.score,
                        "target": target,
                        "proxy": maskProxy(proxy.proxy),
                        "retried": False,
                        "blocked": True,
                    })
                    self.log.warning(
                        "WAF %s detected (score=%s) via %s, no retry: %s" % (
                            waf_result.rule, waf_result.score, maskProxy(proxy.proxy), target,
                        )
                    )
                    response_head = addWafHeaders(response_head, waf_result)
                else:
                    self.log.info("%s %s %s -> %s" % (
                        peer, request_head.method, target, maskProxy(proxy.proxy)))

                latency_ms = int((time.monotonic() - started_at) * 1000)
                self.recordGateway(
                    target, proxy.proxy, status, not waf_result.matched,
                    waf_retry_count, waf_hits, latency_ms, waf_result.matched,
                )

                response_started = True
                client_responded = True
                client_writer.write(response_head)
                if prefix:
                    client_writer.write(prefix)
                await client_writer.drain()

                await self.streamResponse(
                    upstream_reader, client_writer, response_headers, status,
                    request_head.method, len(prefix),
                )
                return
            except Exception as error:
                last_error = error
                self.log.warning("Forward %s via %s failed: %s" % (
                    target, maskProxy(proxy.proxy), error))
                if body_started or response_started:
                    # 请求体已被消费或响应已经开始返回，不能安全重试
                    break
            finally:
                if body_task is not None:
                    if not body_task.done():
                        body_task.cancel()
                    await asyncio.gather(body_task, return_exceptions=True)
                self.closeWriter(upstream_writer)

        if not client_responded:
            self.log.warning("%s %s -> no usable proxy: %s" % (
                peer, request_head.method, last_error))
            latency_ms = int((time.monotonic() - started_at) * 1000)
            self.recordGateway(
                target, last_proxy, 502, False, waf_retry_count,
                waf_hits, latency_ms, False,
            )
            await self.sendError(client_writer, 502, "Bad Gateway")

    async def readReplayBody(self, request_head, reader):
        """
        读取并缓存可重放的请求体

        Returns:
            bytes: 已完整缓存，可重放
            None: 使用 chunked/Expect 或体积过大，只能流式转发，不能 WAF 重试
        """
        if request_head.method.upper() == "HEAD":
            return b""
        if not self.waf_enabled:
            expect = getHeader(request_head.headers, "Expect")
            if not getHeader(request_head.headers, "Transfer-Encoding") \
                    and not expect \
                    and getHeader(request_head.headers, "Content-Length") in (None, "0"):
                return b""
            return None

        transfer_encoding = getHeader(request_head.headers, "Transfer-Encoding")
        expect = getHeader(request_head.headers, "Expect")
        if transfer_encoding or (expect and "100-continue" in expect.lower()):
            return None

        content_length = getHeader(request_head.headers, "Content-Length")
        if content_length is None:
            return b""

        try:
            length = int(content_length)
        except (TypeError, ValueError):
            return None

        if length <= 0:
            return b""
        if self.waf_max_replay_body and length > self.waf_max_replay_body:
            return None
        if not self.waf_max_replay_body:
            return None

        try:
            return await asyncio.wait_for(
                reader.readexactly(length), timeout=self.header_timeout
            )
        except (asyncio.IncompleteReadError, ConnectionError) as error:
            raise RequestBodyError(str(error))

    async def pipeRequestBody(self, reader, writer):
        """流式转发请求体（不可重放场景）"""
        try:
            while True:
                data = await reader.read(BUFFER_SIZE)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            with contextlib.suppress(Exception):
                if writer.can_write_eof():
                    writer.write_eof()

    async def readFinalResponseHead(self, reader, client_writer):
        """读取最终响应头，1xx 中间响应直接转发给客户端"""
        while True:
            response_head = await asyncio.wait_for(
                reader.readuntil(b"\r\n\r\n"), timeout=self.header_timeout
            )
            status_line, headers = splitHeader(response_head)
            status = parseStatusLine(status_line)

            if 100 <= status < 200 and status != 101:
                client_writer.write(response_head)
                await client_writer.drain()
                continue

            return response_head, headers, status

    async def readWafBodyPrefix(self, reader, status, request_head, response_headers):
        """读取用于 WAF 关键词检测的响应体前缀"""
        if not self.waf_enabled or self.waf_body_prefix_size <= 0:
            return b""
        if request_head.method.upper() == "HEAD":
            return b""
        if status in (204, 304) or 100 <= status < 200:
            return b""
        if not self.shouldInspectBody(response_headers, status):
            return b""

        content_length = getHeader(response_headers, "Content-Length")
        if content_length == "0":
            return b""

        size = self.waf_body_prefix_size
        timeout = self.waf_body_read_timeout

        if content_length and content_length.isdigit():
            length = int(content_length)
            if length <= 0:
                return b""
            if length <= size:
                return await self.readKnownLength(reader, length, timeout)
            size = min(size, length)

        try:
            return await asyncio.wait_for(reader.read(size), timeout=timeout)
        except asyncio.TimeoutError:
            return b""

    async def readKnownLength(self, reader, length, timeout):
        """读取已知长度响应体的前 length 字节，尽量读满"""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        chunks = []
        remaining = length

        while remaining > 0:
            wait = deadline - loop.time()
            if wait <= 0:
                break
            try:
                chunk = await asyncio.wait_for(reader.read(remaining), timeout=wait)
            except asyncio.TimeoutError:
                break
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)

        return b"".join(chunks)

    @staticmethod
    def shouldInspectBody(response_headers, status):
        """根据 Content-Type/状态码决定是否值得读取响应体做关键词检测"""
        content_type = (getHeader(response_headers, "Content-Type") or "").lower()
        if "text/event-stream" in content_type:
            return False

        if content_type:
            return (
                content_type.startswith("text/")
                or "json" in content_type
                or "xml" in content_type
                or "javascript" in content_type
                or "x-www-form-urlencoded" in content_type
            )

        # 没有 Content-Type 时，只对可疑状态码读取前缀，避免无谓延迟
        return status in (403, 405, 406, 429, 503)

    async def streamResponse(self, reader, writer, response_headers, status,
                             method, prefix_length):
        """将响应体剩余部分转发给客户端"""
        if method.upper() == "HEAD":
            return
        if status in (204, 304) or 100 <= status < 200:
            return

        transfer_encoding = (getHeader(response_headers, "Transfer-Encoding") or "").lower()
        content_length = getHeader(response_headers, "Content-Length")

        if "chunked" not in transfer_encoding and content_length and content_length.isdigit():
            remaining = int(content_length) - prefix_length
            while remaining > 0:
                data = await reader.read(min(BUFFER_SIZE, remaining))
                if not data:
                    break
                writer.write(data)
                await writer.drain()
                remaining -= len(data)
            return

        await self.pipeRemaining(reader, writer)

    async def pipeRemaining(self, reader, writer):
        """按连接关闭为边界转发剩余数据（chunked/未知长度）"""
        while True:
            data = await reader.read(BUFFER_SIZE)
            if not data:
                break
            writer.write(data)
            await writer.drain()

    async def handleConnect(self, request_head, client_reader, client_writer, peer):
        """建立 HTTPS CONNECT 隧道"""
        started_at = time.monotonic()
        target = request_head.target
        if ":" not in target:
            target = target + ":443"

        strategy = self.resolveStrategy(request_head)
        excluded = set()
        last_error = None
        last_proxy = ""

        for _ in range(self.retry):
            proxy = self.selectProxy(https=True, strategy=strategy, exclude=excluded)
            if proxy is None:
                break
            excluded.add(proxy.proxy)
            last_proxy = proxy.proxy

            try:
                upstream_reader, upstream_writer, auth = await self.openUpstream(proxy)
            except Exception as error:
                last_error = error
                self.log.warning("Connect upstream %s failed: %s" % (maskProxy(proxy.proxy), error))
                continue

            try:
                upstream_writer.write(buildConnectHead(target, auth=auth))
                await upstream_writer.drain()
                response_head = await asyncio.wait_for(
                    upstream_reader.readuntil(b"\r\n\r\n"), timeout=self.header_timeout
                )
            except Exception as error:
                last_error = error
                self.log.warning("CONNECT upstream %s failed: %s" % (maskProxy(proxy.proxy), error))
                self.closeWriter(upstream_writer)
                continue

            try:
                status_line, _ = splitHeader(response_head)
            except ValueError as error:
                last_error = error
                self.log.warning("Invalid CONNECT response from %s: %s" % (
                    maskProxy(proxy.proxy), error))
                self.closeWriter(upstream_writer)
                continue

            status_parts = status_line.split(" ", 2)
            status = 0
            if len(status_parts) > 1 and status_parts[1].isdigit():
                status = int(status_parts[1])

            if status != 200:
                last_error = "upstream status %s" % status
                self.log.warning("CONNECT upstream %s returned %s" % (maskProxy(proxy.proxy), status))
                self.closeWriter(upstream_writer)
                continue

            try:
                client_writer.write(response_head)
                await client_writer.drain()
            except Exception as error:
                last_error = error
                self.closeWriter(upstream_writer)
                break

            latency_ms = int((time.monotonic() - started_at) * 1000)
            self.recordGateway(target, proxy.proxy, 200, True, 0, [], latency_ms, False)
            self.log.info("%s CONNECT %s -> %s" % (peer, target, maskProxy(proxy.proxy)))
            try:
                await self.relay(client_reader, client_writer, upstream_reader, upstream_writer)
            except Exception as error:
                # 隧道已经建立，不能再向客户端写 HTTP 错误响应
                self.log.warning("CONNECT relay %s -> %s failed: %s" % (
                    target, maskProxy(proxy.proxy), error))
            finally:
                self.closeWriter(upstream_writer)
            return

        self.log.warning("%s CONNECT %s -> no usable proxy: %s" % (peer, target, last_error))
        latency_ms = int((time.monotonic() - started_at) * 1000)
        self.recordGateway(target, last_proxy, 502, False, 0, [], latency_ms, False)
        await self.sendError(client_writer, 502, "Bad Gateway")

    def selectProxy(self, https, strategy, exclude=None):
        """
        选择上游代理

        CONNECT 请求优先选择支持 HTTPS 的代理；如果池中没有，
        则回退到全部代理，避免 HTTPS 场景完全不可用。
        """
        proxy = self.proxy_handler.get(
            https=https,
            strategy=strategy,
            key="gateway:%s" % ("https" if https else "http"),
            exclude=exclude,
        )
        if proxy is None and https:
            proxy = self.proxy_handler.get(
                https=False,
                strategy=strategy,
                key="gateway:http",
                exclude=exclude,
            )
        return proxy

    async def openUpstream(self, proxy):
        """连接上游代理"""
        host, port, auth = parseProxyAddress(proxy.proxy)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=self.connect_timeout
        )
        return reader, writer, auth

    async def relay(self, client_reader, client_writer, upstream_reader, upstream_writer):
        """双向转发字节流，任意一端关闭即结束"""

        async def pipe(reader, writer):
            try:
                while True:
                    data = await reader.read(BUFFER_SIZE)
                    if not data:
                        break
                    writer.write(data)
                    await writer.drain()
            except (ConnectionError, asyncio.CancelledError):
                pass
            finally:
                with contextlib.suppress(Exception):
                    if writer.can_write_eof():
                        writer.write_eof()

        tasks = [
            asyncio.ensure_future(pipe(client_reader, upstream_writer)),
            asyncio.ensure_future(pipe(upstream_reader, client_writer)),
        ]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def checkAuth(self, request_head):
        """校验网关认证；未配置 GATEWAY_AUTH 时放行"""
        if not self.auth:
            return True

        provided = parseBasicAuth(request_head.getHeader("Proxy-Authorization"))
        if not provided:
            return False

        username, password = provided
        expected_user, _, expected_pwd = str(self.auth).partition(":")

        if username == expected_user and password == expected_pwd:
            return True

        # 允许使用 <策略名>:<password> 在同一个网关地址上临时切换更换方式
        if username.strip().lower() in STRATEGY_ALIASES and password == expected_pwd:
            return True

        return False

    def resolveStrategy(self, request_head):
        default = self.strategy
        if self.monitor is not None:
            with contextlib.suppress(Exception):
                default = normalizeStrategy(
                    self.monitor.getRuntimeStrategy(default), default=default
                )
        return resolveStrategyFromHeaders(request_head.headers, default)

    def recordGateway(self, target, proxy, status, success, retries,
                      waf_hits=None, latency_ms=0, blocked=False):
        """记录网关指标，监控异常不能影响代理转发"""
        if self.monitor is None:
            return
        with contextlib.suppress(Exception):
            self.monitor.recordGatewayRequest(
                target=target,
                proxy=maskProxy(proxy),
                status=status,
                success=success,
                retries=retries,
                waf_hits=waf_hits or [],
                latency_ms=latency_ms,
                blocked=blocked,
            )

    async def sendError(self, writer, status, message, extra_headers=None):
        """返回错误响应"""
        body = str(message or "").encode("utf-8")
        reason = HTTP_REASONS.get(status, "Error")
        headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Connection", "close"),
        ]
        if extra_headers:
            headers.extend(extra_headers.items())

        lines = ["HTTP/1.1 %s %s" % (status, reason)]
        lines.extend("%s: %s" % (key, value) for key, value in headers)
        lines.append("")
        lines.append("")
        data = CRLF.join(lines).encode("iso-8859-1", errors="replace") + body

        with contextlib.suppress(Exception):
            writer.write(data)
            await writer.drain()

    @staticmethod
    def closeWriter(writer):
        with contextlib.suppress(Exception):
            writer.close()


def runGateway():
    """启动网关"""
    ProxyGateway().run()
