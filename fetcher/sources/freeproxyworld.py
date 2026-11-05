# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     freeproxyworld.py
   Description :   FreeProxyWorld代理源
   Author :        JHao
   date：          2026/11/06
-------------------------------------------------
   Change Activity:
                   2026/11/06: 新增
-------------------------------------------------
"""
__author__ = 'JHao'

import re

from fetcher.baseFetcher import BaseFetcher
from handler.logHandler import LogHandler
from util.webRequest import WebRequest

logger = LogHandler("fetcher")


class FreeProxyWorldFetcher(BaseFetcher):
    """FreeProxyWorld https://www.freeproxy.world"""

    name = "freeproxyworld"
    url = "https://www.freeproxy.world/"

    enabled = True  # 是否启用

    # 站点每页 50 条，抓取前 page_count 页中国代理
    page_count = 3

    def fetch(self):
        base_url = ("https://www.freeproxy.world/"
                    "?type=http&anonymity=&country=CN&speed=&port=&page=%d")
        proxies = []
        for page in range(1, self.page_count + 1):
            try:
                r = WebRequest().get(base_url % page, timeout=10, verify=False)
                page_proxies = []
                if r.tree is not None:
                    for tr in r.tree.xpath("//tr"):
                        ip = "".join(tr.xpath("./td[1]//text()")).strip()
                        port = "".join(tr.xpath("./td[2]//a//text()")).strip() \
                            or "".join(tr.xpath("./td[2]//text()")).strip()
                        if re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', ip) and port.isdigit():
                            page_proxies.append("%s:%s" % (ip, port))
                if not page_proxies:
                    page_proxies = self.parseProxiesFromText(r.text)
                proxies.extend(page_proxies)
            except Exception as e:
                logger.error("ProxyFetch - freeproxyworld: %s" % e)
        for proxy in self.yieldUniqueProxies(proxies):
            yield proxy


if __name__ == '__main__':
    for proxy in FreeProxyWorldFetcher().fetch():
        print(proxy)
