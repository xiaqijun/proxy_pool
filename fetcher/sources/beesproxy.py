# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     beesproxy.py
   Description :   蜜蜂代理代理源
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


class BeesproxyFetcher(BaseFetcher):
    """蜜蜂代理 https://www.beesproxy.com/free"""

    name = "beesproxy"
    url = "https://www.beesproxy.com/free"

    enabled = True  # 是否启用

    def fetch(self):
        try:
            r = WebRequest().get(self.url, timeout=10, verify=False)
            proxies = []
            if r.tree is not None:
                for tr in r.tree.xpath("//tr"):
                    cells = [" ".join(td.xpath(".//text()")).strip() for td in tr.xpath("./td")]
                    if len(cells) >= 2:
                        if re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', cells[0]) and cells[1].isdigit():
                            proxies.append("%s:%s" % (cells[0], cells[1]))
            if not proxies:
                proxies = self.parseProxiesFromText(r.text)
            for proxy in self.yieldUniqueProxies(proxies):
                yield proxy
        except Exception as e:
            logger.error("ProxyFetch - beesproxy: %s" % e)


if __name__ == '__main__':
    for proxy in BeesproxyFetcher().fetch():
        print(proxy)
