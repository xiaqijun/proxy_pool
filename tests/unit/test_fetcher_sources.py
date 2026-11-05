# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     test_fetcher_sources.py
   Description :   各代理源 fetcher 测试
   Author :        JHao
   date：          2026/5/31
-------------------------------------------------
   Change Activity:
                   2026/05/31:
-------------------------------------------------
"""
__author__ = 'JHao'

import re
from unittest.mock import patch, MagicMock

from lxml import etree

from fetcher.baseFetcher import BaseFetcher


# --------------- 辅助工具 ---------------

def _make_response(text="", tree=None, json_data=None):
    """构造 mock 的 WebRequest 返回对象"""
    resp = MagicMock()
    resp.text = text
    resp.tree = tree
    resp.json = json_data if json_data is not None else {}
    return resp


def _html_table(rows, has_header=False):
    """快速生成 HTML table 字符串"""
    html = "<table>"
    if has_header:
        html += "<tr><th>IP</th><th>Port</th></tr>"
    for ip, port in rows:
        html += "<tr><td>%s</td><td>%s</td></tr>" % (ip, port)
    html += "</table>"
    return html


def _assert_valid_proxies(proxies):
    """验证所有 proxy 符合 ip:port 格式"""
    pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5}$')
    for p in proxies:
        assert pattern.match(p), f"Invalid proxy format: {p}"


# --------------- 接口约定测试 ---------------

class TestFetcherInterface(object):
    """所有 fetcher 的接口约定"""

    FETCHER_CLASSES = [
        ("fetcher.sources.ip3366", "Ip3366Fetcher"),
        ("fetcher.sources.ip89", "Ip89Fetcher"),
        ("fetcher.sources.goodips", "GoodipsFetcher"),
        ("fetcher.sources.geonode", "GeonodeFetcher"),

        ("fetcher.sources.kuaidaili", "KuaidailiFetcher"),
        ("fetcher.sources.freevpnnode", "FreeVPNNodeFetcher"),
        ("fetcher.sources.scdn", "ScdnFetcher"),
        ("fetcher.sources.ihuan", "IhuanFetcher"),
        ("fetcher.sources.proxifly", "ProxiFlyFetcher"),
        ("fetcher.sources.roundproxies", "RoundProxiesFetcher"),
        ("fetcher.sources.proxyspace", "ProxyspaceFetcher"),
        ("fetcher.sources.proxyhub", "ProxyhubFetcher"),
        ("fetcher.sources.beesproxy", "BeesproxyFetcher"),
        ("fetcher.sources.freeproxyworld", "FreeProxyWorldFetcher"),
    ]

    def test_all_fetchers_have_name_url_enabled(self):
        for module_path, class_name in self.FETCHER_CLASSES:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            assert cls.name, f"{class_name} missing name"
            assert cls.url, f"{class_name} missing url"
            assert hasattr(cls, 'enabled'), f"{class_name} missing enabled"

    def test_all_fetchers_subclass_base(self):
        for module_path, class_name in self.FETCHER_CLASSES:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            assert issubclass(cls, BaseFetcher), f"{class_name} not subclass of BaseFetcher"

    def test_all_fetchers_have_fetch_method(self):
        for module_path, class_name in self.FETCHER_CLASSES:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            assert hasattr(cls, 'fetch'), f"{class_name} missing fetch method"


# --------------- 各 fetcher 逻辑测试 ---------------

class TestIp3366Fetcher(object):

    @patch("fetcher.sources.ip3366.WebRequest")
    def test_fetch(self, mock_wr):
        from fetcher.sources.ip3366 import Ip3366Fetcher
        html = '<td>1.2.3.4</td><td>8080</td><td>5.6.7.8</td><td>3128</td>'
        mock_wr.return_value.get.return_value = _make_response(text=html)
        result = list(Ip3366Fetcher().fetch())
        assert "1.2.3.4:8080" in result
        assert "5.6.7.8:3128" in result


class TestIp89Fetcher(object):

    @patch("fetcher.sources.ip89.WebRequest")
    def test_fetch(self, mock_wr):
        from fetcher.sources.ip89 import Ip89Fetcher
        html = '<td>1.2.3.4</td><td>8080</td>'
        mock_wr.return_value.get.return_value = _make_response(text=html)
        result = list(Ip89Fetcher().fetch())
        assert "1.2.3.4:8080" in result

    @patch("fetcher.sources.ip89.WebRequest")
    def test_fetch_api_first(self, mock_wr):
        """API 返回纯文本时直接使用，不再请求列表页"""
        from fetcher.sources.ip89 import Ip89Fetcher
        mock_wr.return_value.get.return_value = _make_response(
            text="1.2.3.4:8080\n5.6.7.8:3128")
        result = list(Ip89Fetcher().fetch())
        assert "1.2.3.4:8080" in result
        assert "5.6.7.8:3128" in result
        assert mock_wr.return_value.get.call_count == 1


class TestGoodipsFetcher(object):

    @patch("fetcher.sources.goodips.WebRequest")
    def test_fetch(self, mock_wr):
        from fetcher.sources.goodips import GoodipsFetcher
        html = '<div class="table-list"><ul><li>1.2.3.4</li><li>8080</li></ul></div>'
        tree = etree.HTML(html)
        mock_wr.return_value.get.return_value = _make_response(tree=tree)
        result = list(GoodipsFetcher().fetch())
        assert "1.2.3.4:8080" in result


class TestGeonodeFetcher(object):

    @patch("fetcher.sources.geonode.WebRequest")
    def test_fetch_json(self, mock_wr):
        from fetcher.sources.geonode import GeonodeFetcher
        json_data = {"data": [{"ip": "1.2.3.4", "port": "8080"}]}
        mock_wr.return_value.get.return_value = _make_response(json_data=json_data)
        result = list(GeonodeFetcher().fetch())
        assert "1.2.3.4:8080" in result

    @patch("fetcher.sources.geonode.WebRequest")
    def test_fetch_text_fallback(self, mock_wr):
        from fetcher.sources.geonode import GeonodeFetcher
        mock_wr.return_value.get.return_value = _make_response(
            json_data={}, text="1.2.3.4:8080")
        result = list(GeonodeFetcher().fetch())
        assert "1.2.3.4:8080" in result


class TestKuaidailiFetcher(object):

    @patch("fetcher.sources.kuaidaili.WebRequest")
    @patch("fetcher.sources.kuaidaili.sleep", return_value=None)
    def test_fetch(self, mock_sleep, mock_wr):
        from fetcher.sources.kuaidaili import KuaidailiFetcher
        # kuaidaili 使用 proxy_list[1:] 跳过第一行
        html = _html_table([("IP", "Port"), ("1.2.3.4", "8080")])
        tree = etree.HTML(html)
        mock_wr.return_value.get.return_value = _make_response(tree=tree)
        result = list(KuaidailiFetcher().fetch())
        assert "1.2.3.4:8080" in result


class TestFreeVPNNodeFetcher(object):

    @patch("fetcher.sources.freevpnnode.WebRequest")
    def test_fetch(self, mock_wr):
        from fetcher.sources.freevpnnode import FreeVPNNodeFetcher
        html = _html_table([("1.2.3.4", "8080")])
        tree = etree.HTML(html)
        mock_wr.return_value.get.return_value = _make_response(
            tree=tree, text="1.2.3.4:8080 5.6.7.8:3128")
        result = list(FreeVPNNodeFetcher().fetch())
        assert "1.2.3.4:8080" in result
        assert "5.6.7.8:3128" in result


class TestScdnFetcher(object):

    @patch("fetcher.sources.scdn.WebRequest")
    def test_fetch_json(self, mock_wr):
        from fetcher.sources.scdn import ScdnFetcher
        json_data = {"data": [{"ip": "1.2.3.4", "port": "8080"}]}
        mock_wr.return_value.get.return_value = _make_response(json_data=json_data)
        result = list(ScdnFetcher().fetch())
        assert "1.2.3.4:8080" in result

    @patch("fetcher.sources.scdn.WebRequest")
    def test_fetch_table_html(self, mock_wr):
        from fetcher.sources.scdn import ScdnFetcher
        table_html = '<tr><td>1.2.3.4</td><td>8080</td></tr>'
        json_data = {"table_html": table_html}
        mock_wr.return_value.get.return_value = _make_response(json_data=json_data)
        result = list(ScdnFetcher().fetch())
        assert "1.2.3.4:8080" in result


class TestIhuanFetcher(object):

    @patch("fetcher.sources.ihuan.requests")
    def test_fetch(self, mock_requests):
        from fetcher.sources.ihuan import IhuanFetcher
        html = (
            '<table class="table table-hover table-bordered">'
            '<tr><td>1.2.3.4</td><td>8080</td></tr>'
            '<tr><td>5.6.7.8</td><td>3128</td></tr>'
            '</table>'
        )
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = html
        # 第一次 get 获取 cookie，第二次 get 返回数据
        mock_session.get.return_value = mock_resp
        mock_requests.session.return_value = mock_session

        result = list(IhuanFetcher().fetch())
        assert "1.2.3.4:8080" in result
        assert "5.6.7.8:3128" in result
        assert mock_session.get.call_count == 2

    @patch("fetcher.sources.ihuan.requests")
    def test_fetch_empty_table_returns_empty(self, mock_requests):
        from fetcher.sources.ihuan import IhuanFetcher
        html = '<table class="table table-hover table-bordered"></table>'
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_session.get.return_value = mock_resp
        mock_requests.session.return_value = mock_session

        result = list(IhuanFetcher().fetch())
        assert result == []


class TestProxiFlyFetcher(object):

    @patch("fetcher.sources.proxifly.WebRequest")
    def test_fetch(self, mock_wr):
        from fetcher.sources.proxifly import ProxiFlyFetcher
        json_data = [
            {"proxy": "1.2.3.4:8080", "protocol": "http", "geolocation": {"country": "CN"}},
            {"proxy": "5.6.7.8:3128", "protocol": "http", "geolocation": {"country": "CN"}},
        ]
        mock_wr.return_value.get.return_value = _make_response(json_data=json_data)
        result = list(ProxiFlyFetcher().fetch())
        assert "1.2.3.4:8080" in result
        assert "5.6.7.8:3128" in result

    @patch("fetcher.sources.proxifly.WebRequest")
    def test_fetch_filters_non_cn(self, mock_wr):
        from fetcher.sources.proxifly import ProxiFlyFetcher
        json_data = [
            {"proxy": "1.2.3.4:8080", "protocol": "http", "geolocation": {"country": "CN"}},
            {"proxy": "9.9.9.9:8080", "protocol": "http", "geolocation": {"country": "US"}},
        ]
        mock_wr.return_value.get.return_value = _make_response(json_data=json_data)
        result = list(ProxiFlyFetcher().fetch())
        assert "1.2.3.4:8080" in result
        assert "9.9.9.9:8080" not in result

    @patch("fetcher.sources.proxifly.WebRequest")
    def test_fetch_filters_non_http(self, mock_wr):
        from fetcher.sources.proxifly import ProxiFlyFetcher
        json_data = [
            {"proxy": "1.2.3.4:8080", "protocol": "http", "geolocation": {"country": "CN"}},
            {"proxy": "9.9.9.9:8080", "protocol": "https", "geolocation": {"country": "CN"}},
        ]
        mock_wr.return_value.get.return_value = _make_response(json_data=json_data)
        result = list(ProxiFlyFetcher().fetch())
        assert "1.2.3.4:8080" in result
        assert "9.9.9.9:8080" not in result


class TestRoundProxiesFetcher(object):

    @patch("fetcher.sources.roundproxies.WebRequest")
    def test_fetch(self, mock_wr):
        from fetcher.sources.roundproxies import RoundProxiesFetcher
        json_data = {
            "data": [
                {"ip": "1.2.3.4", "port": "8080"},
                {"ip": "5.6.7.8", "port": "3128"},
            ]
        }
        mock_wr.return_value.get.return_value = _make_response(json_data=json_data)
        result = list(RoundProxiesFetcher().fetch())
        assert "1.2.3.4:8080" in result
        assert "5.6.7.8:3128" in result

    @patch("fetcher.sources.roundproxies.WebRequest")
    def test_fetch_empty_data_returns_empty(self, mock_wr):
        from fetcher.sources.roundproxies import RoundProxiesFetcher
        mock_wr.return_value.get.return_value = _make_response(json_data={})
        result = list(RoundProxiesFetcher().fetch())
        assert result == []

    @patch("fetcher.sources.roundproxies.WebRequest")
    def test_fetch_exception_returns_empty(self, mock_wr):
        from fetcher.sources.roundproxies import RoundProxiesFetcher
        mock_wr.return_value.get.return_value = _make_response(json_data=None)
        result = list(RoundProxiesFetcher().fetch())
        assert result == []


class TestProxyspaceFetcher(object):

    @patch("fetcher.sources.proxyspace.WebRequest")
    def test_fetch(self, mock_wr):
        from fetcher.sources.proxyspace import ProxyspaceFetcher
        mock_wr.return_value.get.return_value = _make_response(
            text="1.2.3.4:8080\n5.6.7.8:3128\n")
        result = list(ProxyspaceFetcher().fetch())
        assert "1.2.3.4:8080" in result
        assert "5.6.7.8:3128" in result
        # CN http + CN https 两个地址
        assert mock_wr.return_value.get.call_count == 2

    @patch("fetcher.sources.proxyspace.WebRequest")
    def test_fetch_dedup(self, mock_wr):
        from fetcher.sources.proxyspace import ProxyspaceFetcher
        mock_wr.return_value.get.return_value = _make_response(
            text="1.2.3.4:8080\n1.2.3.4:8080\n")
        result = list(ProxyspaceFetcher().fetch())
        assert result == ["1.2.3.4:8080"]


def _proxyhub_html(rows):
    html = "<table><tbody>"
    for ip, port in rows:
        html += ('<tr><td class="ip-cell" data-label="IP">'
                 '<span class="ip-text" title="%s">%s</span></td>'
                 '<td class="port-cell"><span class="port-text">%s</span></td>'
                 '<td class="protocols-cell">HTTP</td></tr>' % (ip, ip, port))
    return html + "</tbody></table>"


class TestProxyhubFetcher(object):

    @patch("fetcher.sources.proxyhub.WebRequest")
    def test_fetch(self, mock_wr):
        from fetcher.sources.proxyhub import ProxyhubFetcher
        tree = etree.HTML(_proxyhub_html([("1.2.3.4", "8080"), ("5.6.7.8", "3128")]))
        mock_wr.return_value.get.return_value = _make_response(tree=tree)
        result = list(ProxyhubFetcher().fetch())
        assert "1.2.3.4:8080" in result
        assert "5.6.7.8:3128" in result
        assert mock_wr.return_value.get.call_count == ProxyhubFetcher.page_count

    @patch("fetcher.sources.proxyhub.WebRequest")
    def test_fetch_text_fallback(self, mock_wr):
        from fetcher.sources.proxyhub import ProxyhubFetcher
        fetcher = ProxyhubFetcher()
        fetcher.page_count = 1
        mock_wr.return_value.get.return_value = _make_response(
            tree=None, text="1.2.3.4:8080")
        result = list(fetcher.fetch())
        assert "1.2.3.4:8080" in result


class TestBeesproxyFetcher(object):

    @patch("fetcher.sources.beesproxy.WebRequest")
    def test_fetch(self, mock_wr):
        from fetcher.sources.beesproxy import BeesproxyFetcher
        tree = etree.HTML(_html_table([("1.2.3.4", "8080"), ("5.6.7.8", "3128")]))
        mock_wr.return_value.get.return_value = _make_response(tree=tree)
        result = list(BeesproxyFetcher().fetch())
        assert "1.2.3.4:8080" in result
        assert "5.6.7.8:3128" in result

    @patch("fetcher.sources.beesproxy.WebRequest")
    def test_fetch_text_fallback(self, mock_wr):
        from fetcher.sources.beesproxy import BeesproxyFetcher
        mock_wr.return_value.get.return_value = _make_response(
            tree=None, text="1.2.3.4:8080")
        result = list(BeesproxyFetcher().fetch())
        assert "1.2.3.4:8080" in result


def _freeproxyworld_html(rows):
    html = "<table><tbody>"
    for ip, port in rows:
        html += ('<tr><td style="font-weight: 500;">%s</td>'
                 '<td><a href="/?port=%s">%s</a></td>'
                 '<td><a href="/?country=CN">China</a></td></tr>' % (ip, port, port))
    return html + "</tbody></table>"


class TestFreeProxyWorldFetcher(object):

    @patch("fetcher.sources.freeproxyworld.WebRequest")
    def test_fetch(self, mock_wr):
        from fetcher.sources.freeproxyworld import FreeProxyWorldFetcher
        tree = etree.HTML(_freeproxyworld_html([("1.2.3.4", "8080"), ("5.6.7.8", "3128")]))
        mock_wr.return_value.get.return_value = _make_response(tree=tree)
        result = list(FreeProxyWorldFetcher().fetch())
        assert "1.2.3.4:8080" in result
        assert "5.6.7.8:3128" in result
        assert mock_wr.return_value.get.call_count == FreeProxyWorldFetcher.page_count

    @patch("fetcher.sources.freeproxyworld.WebRequest")
    def test_fetch_text_fallback(self, mock_wr):
        from fetcher.sources.freeproxyworld import FreeProxyWorldFetcher
        fetcher = FreeProxyWorldFetcher()
        fetcher.page_count = 1
        mock_wr.return_value.get.return_value = _make_response(
            tree=None, text="1.2.3.4:8080")
        result = list(fetcher.fetch())
        assert "1.2.3.4:8080" in result
