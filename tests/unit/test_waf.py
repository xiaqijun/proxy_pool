# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     test_waf.py
   Description :   WAF 指纹检测单元测试
   Author :        JHao
   date：          2026/10/26
-------------------------------------------------
   Change Activity:
                   2026/10/26:
-------------------------------------------------
"""
__author__ = 'JHao'

import gzip

from helper.waf import WafDetector, decodeChunkedPrefix


class TestBuiltinWaf:

    def test_cloudflare_challenge_body(self):
        result = WafDetector().detect(
            403,
            [("Server", "cloudflare"), ("CF-Mitigated", "challenge")],
            b"<html>Just a moment...</html>",
        )
        assert result.matched is True
        assert result.rule == "cloudflare"
        assert result.score >= 2

    def test_cloudflare_normal_200(self):
        result = WafDetector().detect(
            200,
            [("Server", "cloudflare"), ("CF-RAY", "abc")],
            b"<html>normal page</html>",
        )
        assert result.matched is False

    def test_cloudflare_weak_header_with_403(self):
        result = WafDetector().detect(403, [("Server", "cloudflare")], b"")
        assert result.matched is True
        assert result.rule == "cloudflare"

    def test_akamai(self):
        result = WafDetector().detect(
            403,
            [("Server", "AkamaiGHost")],
            b"Access Denied. Reference #18.abc",
        )
        assert result.matched is True
        assert result.rule == "akamai"

    def test_aws_waf(self):
        result = WafDetector().detect(
            200,
            [("x-amzn-waf-action", "BLOCK")],
            b"",
        )
        assert result.matched is True
        assert result.rule == "aws_waf"

    def test_imperva(self):
        result = WafDetector().detect(
            403,
            [("X-Iinfo", "1-2-3")],
            b"Request unsuccessful. Incapsula incident ID: 123",
        )
        assert result.matched is True
        assert result.rule == "imperva"

    def test_aliyun_chinese_keyword(self):
        result = WafDetector().detect(
            403,
            [("Set-Cookie", "acw_tc=abc; path=/")],
            "您的请求被拦截，访问被拦截".encode("utf-8"),
        )
        assert result.matched is True
        assert result.rule == "aliyun_waf"

    def test_tencent_header_prefix(self):
        result = WafDetector().detect(
            403,
            [("X-WAF-Request-ID", "abc")],
            b"",
        )
        assert result.matched is True
        assert result.rule == "tencent_waf"

    def test_generic_access_denied_with_403(self):
        result = WafDetector().detect(403, [], b"Access Denied")
        assert result.matched is True
        assert result.rule == "generic"

    def test_generic_access_denied_with_200(self):
        result = WafDetector().detect(200, [], b"Access Denied")
        assert result.matched is False

    def test_normal_page(self):
        result = WafDetector().detect(
            200,
            [("Content-Type", "text/html; charset=utf-8")],
            b"<html><body>hello world</body></html>",
        )
        assert result.matched is False


class TestWafBodyDecoding:

    def test_gzip_body(self):
        body = gzip.compress(b"Just a moment...")
        result = WafDetector().detect(
            200,
            [("Content-Encoding", "gzip"), ("Content-Type", "text/html")],
            body,
        )
        assert result.matched is True
        assert result.rule == "cloudflare"

    def test_chunked_body(self):
        body = b"d\r\nJust a moment\r\n0\r\n\r\n"
        result = WafDetector().detect(
            200,
            [("Transfer-Encoding", "chunked"), ("Content-Type", "text/html")],
            body,
        )
        assert result.matched is True

    def test_charset_gbk(self):
        body = "访问被拦截".encode("gbk")
        result = WafDetector().detect(
            200,
            [("Content-Type", "text/html; charset=gbk")],
            body,
        )
        assert result.matched is True

    def test_decode_chunked_prefix(self):
        assert decodeChunkedPrefix(b"5\r\nhello\r\n0\r\n\r\n") == b"hello"
        assert decodeChunkedPrefix(b"a\r\nhello") == b""


class TestCustomWafRules:

    def test_custom_header(self):
        detector = WafDetector(custom_headers=["x-my-waf: blocked"])
        result = detector.detect(200, [("X-My-WAF", "blocked")], b"")
        assert result.matched is True
        assert result.rule == "custom"

    def test_custom_header_presence(self):
        detector = WafDetector(custom_headers=["x-my-waf"])
        result = detector.detect(200, [("X-My-WAF", "anything")], b"")
        assert result.matched is True

    def test_custom_keyword(self):
        detector = WafDetector(custom_keywords=["custom block page"])
        result = detector.detect(200, [], b"<html>custom block page</html>")
        assert result.matched is True
        assert result.rule == "custom"

    def test_custom_status(self):
        detector = WafDetector(custom_status=[418])
        result = detector.detect(418, [], b"")
        assert result.matched is True
        assert result.rule == "custom_status"

    def test_threshold(self):
        detector = WafDetector(threshold=3)
        # Server: cloudflare(1) + status(1) = 2 < 3
        result = detector.detect(403, [("Server", "cloudflare")], b"")
        assert result.matched is False


class TestWafDetectorEmpty:

    def test_empty_response(self):
        result = WafDetector().detect(200, [], b"")
        assert result.matched is False
        assert result.rule == ""
        assert result.score == 0
