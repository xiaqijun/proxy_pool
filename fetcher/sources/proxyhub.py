# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     proxyhub.py
   Description :   Proxyhub代理源
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


class ProxyhubFetcher(BaseFetcher):
    """Proxyhub https://proxyhub.me"""

    name = "proxyhub"
    url = "https://proxyhub.me/"

    enabled = True  # 是否启用

    # 站点每页 20 条，抓取前 page_count 页中国代理
    page_count = 5

    def fetch(self):
        detail_url = "https://proxyhub.me/en/cn-free-proxy-list.html"
        proxies = []
        for page in range(1, self.page_count + 1):
            url = detail_url if page == 1 else "%s?page=%d" % (detail_url, page)
            try:
                r = WebRequest().get(url, timeout=10, verify=False)
                page_proxies = []
                if r.tree is not None:
                    for tr in r.tree.xpath("//tr"):
                        ip = "".join(tr.xpath(".//td[contains(@class,'ip-cell')]//@title")).strip()
                        if not re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', ip):
                            ip = "".join(tr.xpath(".//td[contains(@class,'ip-cell')]//text()")).strip()
                        port = "".join(tr.xpath(".//td[contains(@class,'port-cell')]//text()")).strip()
                        if ip and port.isdigit():
                            page_proxies.append("%s:%s" % (ip, port))
                if not page_proxies:
                    page_proxies = self.parseProxiesFromText(r.text)
                proxies.extend(page_proxies)
            except Exception as e:
                logger.error("ProxyFetch - proxyhub: %s" % e)
        for proxy in self.yieldUniqueProxies(proxies):
            yield proxy


if __name__ == '__main__':
    for proxy in ProxyhubFetcher().fetch():
        print(proxy)
