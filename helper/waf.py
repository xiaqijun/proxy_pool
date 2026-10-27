# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     waf.py
   Description :   WAF 响应指纹检测
   Author :        JHao
   date：          2026/10/26
-------------------------------------------------
   Change Activity:
                   2026/10/26: 支持常见 WAF 指纹、评分机制及自定义规则
-------------------------------------------------
"""
__author__ = 'JHao'

import gzip
import re
import zlib
from collections import namedtuple

WafResult = namedtuple("WafResult", ["matched", "rule", "score", "reason"])

NO_WAF = WafResult(False, "", 0, "")

CHARSET_REGEX = re.compile(r"charset\s*=\s*[\"']?([\w\-]+)", re.IGNORECASE)


def normalizeHeaders(headers):
    """将 (name, value) 列表转为小写 name -> value 列表的字典"""
    result = {}
    for name, value in headers or []:
        key = str(name).strip().lower()
        if not key:
            continue
        result.setdefault(key, []).append(str(value))
    return result


def matchHeader(header_map, name, value_substr=None):
    """
    匹配响应头

    Args:
        header_map: normalizeHeaders 返回的字典
        name: 头部名称，支持以 * 结尾的前缀匹配，例如 x-waf-*
        value_substr: 可选，头部值需要包含的子串（不区分大小写）
    Returns:
        (matched, description)
    """
    name = str(name).strip().lower()
    if not name:
        return False, ""

    if name.endswith("*"):
        prefix = name[:-1]
        for key, values in header_map.items():
            if not key.startswith(prefix):
                continue
            joined = "; ".join(values)
            if value_substr is None or str(value_substr).lower() in joined.lower():
                return True, "header:%s" % key
        return False, ""

    values = header_map.get(name)
    if not values:
        return False, ""

    joined = "; ".join(values)
    if value_substr is None or str(value_substr).lower() in joined.lower():
        return True, "header:%s" % name
    return False, ""


def decodeChunkedPrefix(data):
    """解析 chunked 编码前缀，尽量取出已完整的 chunk 内容"""
    if not data:
        return b""

    result = bytearray()
    index = 0
    while index < len(data):
        line_end = data.find(b"\r\n", index)
        if line_end == -1:
            break

        size_text = data[index:line_end].split(b";", 1)[0].strip()
        try:
            size = int(size_text, 16)
        except ValueError:
            break

        index = line_end + 2
        if size == 0:
            break
        if index + size > len(data):
            break

        result.extend(data[index:index + size])
        index += size
        if data[index:index + 2] == b"\r\n":
            index += 2

    return bytes(result)


def decompressPrefix(data, content_encoding):
    """解压 gzip/deflate 前缀；失败时返回原始数据"""
    if not data or not content_encoding:
        return data

    encoding = str(content_encoding).lower()
    try:
        if "gzip" in encoding:
            # 允许不完整 gzip 流，返回已解压部分
            return zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(data)
        if "deflate" in encoding:
            return zlib.decompressobj().decompress(data)
    except (zlib.error, OSError):
        try:
            return gzip.decompress(data)
        except Exception:
            return data
    return data


def decodeBody(body, headers):
    """将响应体前缀解码为小写文本，供关键词匹配"""
    if not body:
        return ""

    header_map = normalizeHeaders(headers)
    transfer_encoding = "; ".join(header_map.get("transfer-encoding", []))
    content_encoding = "; ".join(header_map.get("content-encoding", []))

    if "chunked" in transfer_encoding.lower():
        body = decodeChunkedPrefix(body)

    body = decompressPrefix(body, content_encoding)

    content_type = "; ".join(header_map.get("content-type", []))
    charset_match = CHARSET_REGEX.search(content_type)
    charsets = []
    if charset_match:
        charsets.append(charset_match.group(1))
    charsets.extend(["utf-8", "gb18030", "latin-1"])

    for charset in charsets:
        try:
            return body.decode(charset).lower()
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("latin-1", errors="ignore").lower()


class WafRule(object):
    """单个 WAF 指纹规则"""

    def __init__(self, name, headers=None, keywords=None, status_codes=None):
        self.name = name
        # [(header_name, value_substr, score), ...]
        self.headers = headers or []
        # [(keyword, score), ...]
        self.keywords = keywords or []
        self.status_codes = set(status_codes or [])

    def score(self, status, header_map, body_text):
        """
        计算规则得分

        - 响应头/响应体命中累加对应分数；
        - 状态码只在已有其他指纹时额外加 1，避免仅凭 403/503 误判。
        """
        total = 0
        signals = []

        for name, value_substr, points in self.headers:
            matched, description = matchHeader(header_map, name, value_substr)
            if matched:
                total += points
                signals.append(description)

        for keyword, points in self.keywords:
            if keyword.lower() in body_text:
                total += points
                signals.append("body:%s" % keyword)

        if status in self.status_codes and total > 0:
            total += 1
            signals.append("status:%s" % status)

        return total, signals


# 常见 WAF 指纹。分数说明：
#   1 = 弱指纹，需要状态码或其他指纹配合
#   2 = 较强指纹
#   3 = 强指纹，单独出现即可判定
BUILTIN_RULES = [
    WafRule(
        "cloudflare",
        headers=[
            ("cf-mitigated", "challenge", 3),
            ("server", "cloudflare", 1),
        ],
        keywords=[
            ("just a moment", 3),
            ("attention required", 2),
            ("checking your browser", 2),
            ("cf-chl", 2),
            ("__cf_chl", 2),
            ("cloudflare ray id", 2),
        ],
        status_codes=(403, 429, 503),
    ),
    WafRule(
        "akamai",
        headers=[
            ("server", "akamaighost", 1),
        ],
        keywords=[
            ("reference #", 2),
            ("akamai", 1),
        ],
        status_codes=(403, 429, 503),
    ),
    WafRule(
        "aws_waf",
        headers=[
            ("x-amzn-waf-action", None, 3),
            ("server", "awselb", 1),
        ],
        keywords=[
            ("aws waf", 3),
            ("request blocked", 2),
        ],
        status_codes=(403,),
    ),
    WafRule(
        "imperva",
        headers=[
            ("x-iinfo", None, 1),
            ("x-cdn", "incapsula", 1),
            ("set-cookie", "visid_incap", 1),
        ],
        keywords=[
            ("incapsula incident id", 3),
            ("request unsuccessful", 2),
            ("incapsula", 1),
        ],
        status_codes=(403, 429, 503),
    ),
    WafRule(
        "sucuri",
        headers=[
            ("x-sucuri-id", None, 1),
            ("server", "sucuri", 1),
        ],
        keywords=[
            ("sucuri website firewall", 3),
        ],
        status_codes=(403, 429, 503),
    ),
    WafRule(
        "f5_bigip",
        headers=[
            ("x-wa-info", None, 3),
            ("server", "bigip", 1),
        ],
        keywords=[
            ("the requested url was rejected", 3),
            ("your support id is", 2),
        ],
        status_codes=(403,),
    ),
    WafRule(
        "modsecurity",
        keywords=[
            ("modsecurity", 3),
            ("not acceptable", 2),
            ("request rejected", 2),
        ],
        status_codes=(403, 406),
    ),
    WafRule(
        "barracuda",
        headers=[
            ("set-cookie", "barra_counter_session", 3),
        ],
        keywords=[
            ("barracuda", 2),
        ],
        status_codes=(403,),
    ),
    WafRule(
        "fortiweb",
        headers=[
            ("set-cookie", "fortiwafsid", 3),
        ],
        keywords=[
            ("fortiweb", 3),
        ],
        status_codes=(403,),
    ),
    WafRule(
        "aliyun_waf",
        headers=[
            ("server", "yunjiasu", 1),
            ("set-cookie", "acw_tc", 1),
            ("set-cookie", "aliyungf", 2),
        ],
        keywords=[
            ("errors.aliyun.com", 3),
            ("aliyun waf", 3),
            ("your request has been blocked", 2),
            ("访问被拦截", 3),
            ("请求被拦截", 2),
            ("访问被拒绝", 2),
        ],
        status_codes=(403, 405, 429, 503),
    ),
    WafRule(
        "tencent_waf",
        headers=[
            ("x-waf-*", None, 1),
        ],
        keywords=[
            ("waf.tencent.com", 3),
            ("tencent waf", 3),
            ("请求被拦截", 2),
            ("访问被拦截", 2),
        ],
        status_codes=(403, 429, 503),
    ),
    WafRule(
        "baidu_yunjiasu",
        headers=[
            ("server", "yunjiasu", 1),
        ],
        keywords=[
            ("百度云加速", 3),
            ("yunjiasu", 1),
        ],
        status_codes=(403, 503),
    ),
    WafRule(
        "safedog",
        headers=[
            ("server", "safedog", 3),
            ("set-cookie", "safedog", 2),
        ],
        keywords=[
            ("safedog", 3),
            ("安全狗", 3),
        ],
        status_codes=(403,),
    ),
    WafRule(
        "knownsec",
        keywords=[
            ("创宇盾", 3),
            ("知道创宇", 3),
            ("yunaq", 2),
        ],
        status_codes=(403,),
    ),
    WafRule(
        "generic",
        keywords=[
            ("web application firewall", 3),
            ("request blocked", 2),
            ("request has been blocked", 2),
            ("your request has been blocked", 2),
            ("access denied", 1),
            ("security policy", 1),
            ("not acceptable", 1),
            ("请求被拦截", 2),
            ("访问被拒绝", 1),
            ("访问被拦截", 2),
            ("非法请求", 2),
        ],
        status_codes=(403, 429, 503),
    ),
]


class WafDetector(object):
    """WAF 检测器"""

    def __init__(self, threshold=2, custom_headers=None, custom_keywords=None,
                 custom_status=None, rules=None):
        self.threshold = max(int(threshold), 1)
        self.rules = list(rules if rules is not None else BUILTIN_RULES)

        self.custom_headers = []
        for item in custom_headers or []:
            name, sep, value = str(item).partition(":")
            name = name.strip().lower()
            if not name:
                continue
            self.custom_headers.append((name, value.strip() if sep else None))

        self.custom_keywords = [
            str(item).strip().lower()
            for item in (custom_keywords or [])
            if str(item).strip()
        ]

        self.custom_status = set()
        for item in custom_status or []:
            try:
                self.custom_status.add(int(item))
            except (TypeError, ValueError):
                continue

    def detect(self, status, headers, body=b""):
        """
        检测 WAF

        Args:
            status: HTTP 状态码
            headers: [(name, value), ...]
            body: 响应体前缀（bytes）
        Returns:
            WafResult
        """
        if status in self.custom_status:
            return WafResult(True, "custom_status", 99, "status:%s" % status)

        header_map = normalizeHeaders(headers)
        body_text = decodeBody(body, headers)

        best = NO_WAF
        for rule in self.rules:
            score, signals = rule.score(status, header_map, body_text)
            if score >= self.threshold and score > best.score:
                best = WafResult(True, rule.name, score, ", ".join(signals))

        custom_score = 0
        custom_signals = []
        for name, value_substr in self.custom_headers:
            matched, description = matchHeader(header_map, name, value_substr)
            if matched:
                custom_score += 10
                custom_signals.append(description)

        for keyword in self.custom_keywords:
            if keyword in body_text:
                custom_score += 10
                custom_signals.append("body:%s" % keyword)

        if custom_score and custom_score > best.score:
            best = WafResult(True, "custom", custom_score, ", ".join(custom_signals))

        return best
