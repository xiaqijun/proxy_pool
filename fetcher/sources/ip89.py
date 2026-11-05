# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     ip89.py
   Description :   89免费代理代理源
   Author :        JHao
   date：          2026/5/31
-------------------------------------------------
   Change Activity:
                   2026/05/31:
-------------------------------------------------
"""
__author__ = 'JHao'

import re

from fetcher.baseFetcher import BaseFetcher
from util.webRequest import WebRequest


class Ip89Fetcher(BaseFetcher):
    """89免费代理 https://www.89ip.cn/"""

    name = "ip89"
    url = "https://www.89ip.cn/"

    def fetch(self):
        # 优先使用官方 API（纯文本、单次 100 条），失败再回退到列表页解析
        r = WebRequest().get(
            "http://api.89ip.cn/tqdl.html?api=1&num=100&port=&address=&isp=",
            timeout=10, retry_time=1)
        proxies = self.parseProxiesFromText(r.text)
        if proxies:
            for proxy in self.yieldUniqueProxies(proxies):
                yield proxy
            return

        r = WebRequest().get("https://www.89ip.cn/index_1.html", timeout=10)
        proxies = re.findall(
            r'<td.*?>[\s\S]*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[\s\S]*?</td>[\s\S]*?<td.*?>[\s\S]*?(\d+)[\s\S]*?</td>',
            r.text)
        for proxy in self.yieldUniqueProxies([':'.join(item) for item in proxies]):
            yield proxy


if __name__ == '__main__':
    for proxy in Ip89Fetcher().fetch():
        print(proxy)