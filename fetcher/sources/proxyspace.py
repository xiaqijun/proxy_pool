# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     proxyspace.py
   Description :   Proxyspace代理源
   Author :        JHao
   date：          2026/11/06
-------------------------------------------------
   Change Activity:
                   2026/11/06: 新增
-------------------------------------------------
"""
__author__ = 'JHao'

from fetcher.baseFetcher import BaseFetcher
from handler.logHandler import LogHandler
from util.webRequest import WebRequest

logger = LogHandler("fetcher")


class ProxyspaceFetcher(BaseFetcher):
    """Proxyspace https://proxyspace.pro"""

    name = "proxyspace"
    url = "https://proxyspace.pro/"

    enabled = True  # 是否启用

    def fetch(self):
        # 站点按国家提供 txt 列表，这里只取中国大陆的 HTTP/HTTPS 代理，避免全量列表过大
        target_urls = [
            "https://proxyspace.pro/country/cn/http.txt",
            "https://proxyspace.pro/country/cn/https.txt",
        ]
        proxies = []
        try:
            for url in target_urls:
                r = WebRequest().get(url, timeout=10, verify=False)
                proxies.extend(self.parseProxiesFromText(r.text))
        except Exception as e:
            logger.error("ProxyFetch - proxyspace: %s" % e)
        for proxy in self.yieldUniqueProxies(proxies):
            yield proxy


if __name__ == '__main__':
    for proxy in ProxyspaceFetcher().fetch():
        print(proxy)
