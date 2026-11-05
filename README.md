
ProxyPool 爬虫代理IP池
=======
[![Tests](https://github.com/jhao104/proxy_pool/actions/workflows/test.yml/badge.svg)](https://github.com/jhao104/proxy_pool/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/jhao104/proxy_pool/graph/badge.svg?token=8WHGkrQA6E)](https://codecov.io/gh/jhao104/proxy_pool)
[![](https://img.shields.io/badge/Powered%20by-@j_hao104-green.svg)](http://www.spiderpy.cn/blog/)
[![Packagist](https://img.shields.io/packagist/l/doctrine/orm.svg)](https://github.com/jhao104/proxy_pool/blob/master/LICENSE)
[![GitHub contributors](https://img.shields.io/github/contributors/jhao104/proxy_pool.svg)](https://github.com/jhao104/proxy_pool/graphs/contributors)
[![](https://img.shields.io/badge/language-Python-green.svg)](https://github.com/jhao104/proxy_pool)

    ______                        ______             _
    | ___ \_                      | ___ \           | |
    | |_/ / \__ __   __  _ __   _ | |_/ /___   ___  | |
    |  __/|  _// _ \ \ \/ /| | | ||  __// _ \ / _ \ | |
    | |   | | | (_) | >  < \ |_| || |  | (_) | (_) || |___
    \_|   |_|  \___/ /_/\_\ \__  |\_|   \___/ \___/ \_____\
                           __ / /
                          /___ /

### ProxyPool

爬虫代理IP池项目，主要功能为定时采集网上发布的免费代理验证入库，定时验证入库的代理保证代理的可用性。提供策略化 API、稳定代理网关和 CLI 三种使用方式，支持随机、轮询、加权三种代理更换方式；网关内置 WAF 检测，命中后自动切换代理。同时你也可以扩展代理源以增加代理池 IP 的质量和数量。

* 文档: [document](https://jhao104.github.io/proxy_pool/)

* 支持版本: 
[![](https://img.shields.io/badge/Python-3.8-blue.svg)](https://docs.python.org/3.8/)
[![](https://img.shields.io/badge/Python-3.9-blue.svg)](https://docs.python.org/3.9/)
[![](https://img.shields.io/badge/Python-3.10-blue.svg)](https://docs.python.org/3.10/)
[![](https://img.shields.io/badge/Python-3.11-blue.svg)](https://docs.python.org/3.11/)

* 测试地址: http://demo.spiderpy.cn (勿压谢谢)

* 付费代理推荐: [亮数据 Bright Data](https://get.brightdata.com/github_jh)（前身 Luminati）.全球代理与网络抓取行业头部领导者。覆盖 195+ 国家的 1.5亿+ 真人住宅IP，亲测成功率极高，轻松突破反爬封锁。需要高质量代理IP的可以注册后联系中文客服。[申请免费试用](https://get.brightdata.com/github_jh) (PS:用不明白的同学可以参考这个[使用教程](https://www.cnblogs.com/jhao/p/15611785.html))。

&emsp;&emsp; 想自建爬虫？接入 [Bright Data MCP Server](https://get.brightdata.com/cd3yy5)，让 Claude、Cursor、Windsurf 等 AI 助手直接实时抓取网页——自动破解验证码、绕过地区限制。[Scraper Studio](https://get.brightdata.com/cd3yy5) 支持 AI 一键生成或 JS 代码定制，全托管基础设施运行，无需自购代理、无需搭服务器，分钟级上线。所有产品底层均由同一套顶级代理网络驱动。

&emsp;&emsp; API 产品现享7折 + 免费试用额度，注册后可联系中文客服快速上手。(用不明白的同学可参考使用教程，或注册后直接使用互动 AI 智能助手)
👉 [https://get.brightdata.com/cd3yy5](https://get.brightdata.com/cd3yy5)


### 运行项目

##### 下载代码:

* git clone

```bash
git clone https://github.com/jhao104/proxy_pool.git
```

* releases

```bash
https://github.com/jhao104/proxy_pool/releases 下载对应zip文件
```

##### 安装依赖:

```bash
pip install -r requirements.txt
```

##### 更新配置:


```python
# setting.py 为项目配置文件

# 配置API服务

HOST = "0.0.0.0"               # IP
PORT = 5010                    # 监听端口


# 配置数据库

DB_CONN = 'redis://:pwd@127.0.0.1:8888/0'


# 配置代理源（可选）
# 默认自动扫描 fetcher/sources/ 目录下所有 enabled=True 的代理源
# 如需禁用某些代理源，在黑名单中添加其 name 即可
# PROXY_FETCHER_EXCLUDE = ["freevpnnode"]

# 配置代理更换方式（可选）
# random: 随机 / round_robin: 轮询 / weighted: 按成功率加权
PROXY_STRATEGY = "random"

# 配置稳定代理网关（可选）
GATEWAY_HOST = "0.0.0.0"
GATEWAY_PORT = 5011
GATEWAY_STRATEGY = "random"
GATEWAY_AUTH = ""          # 如 "user:password"，留空表示不认证

# WAF 检测（网关转发 HTTP 响应时生效）
WAF_DETECT_ENABLED = True
WAF_SCORE_THRESHOLD = 2
WAF_CUSTOM_HEADERS = []    # 如 ["x-my-waf: blocked"]
WAF_CUSTOM_KEYWORDS = []   # 如 ["custom block page"]
WAF_CUSTOM_STATUS = []     # 如 [418]

# 监控工作台
MONITOR_ENABLED = True
MONITOR_DB_PATH = "data/monitor.db"
MONITOR_AUTH_USER = "admin"
MONITOR_AUTH_PASSWORD = "change-me"   # 请务必修改
MONITOR_RETENTION_DAYS = 7
MONITOR_REFRESH_SECONDS = 5   # SSE 断线时的回退轮询间隔
```

#### 启动项目:

```bash
# 如果已经具备运行条件, 可用通过proxyPool.py启动。
# 程序分为: schedule 调度程序、server Api服务 和 gateway 稳定代理网关

# 启动调度程序
python proxyPool.py schedule

# 启动webApi服务
python proxyPool.py server

# 启动稳定代理网关（可选，客户端直接把网关当代理用）
python proxyPool.py gateway

# 或者在一个进程内同时启动 API 和网关
python proxyPool.py all

```

### Docker Image

```bash
docker pull jhao104/proxy_pool

docker run \
  --env DB_CONN=redis://:password@ip:port/0 \
  --env MONITOR_AUTH_PASSWORD=your-strong-password \
  -v $(pwd)/data:/app/data \
  -p 5010:5010 -p 5011:5011 \
  jhao104/proxy_pool:latest
```
### docker-compose

项目目录下运行: 
``` bash
docker-compose up -d
```

生产环境推荐使用独立服务编排（API、调度器、网关、Redis 分离）：

```bash
cp .env.example .env
# 修改 Redis、工作台、网关密码
docker compose -f docker-compose.prod.yml up -d --build
```

详见 [托管部署](docs/deployment.md)。

> Vercel / Netlify / Cloudflare Pages 等纯静态或 Serverless 平台无法运行调度器、网关、Redis 和长期 SSE，不能部署完整项目。共享虚拟主机同样不支持。

### 使用

* Api

启动web服务后, 默认配置下会开启 http://127.0.0.1:5010 的api接口服务:

| api | method | Description | params|
| ----| ---- | ---- | ----|
| / | GET | api介绍 | None |
| /get | GET | 按策略获取一个代理 | 可选：`?type=https`、`?strategy=random / round_robin / weighted`、`?format=text` |
| /pop | GET | 获取并删除一个代理| 可选参数: `?type=https` 过滤支持https的代理|
| /all | GET | 获取所有代理 |可选参数: `?type=https` 过滤支持https的代理|
| /count | GET | 查看代理数量 |None|
| /delete | GET | 删除代理  |`?proxy=host:ip`|
| /strategies | GET | 查看支持的更换方式 |None|
| /gateway | GET | 查看网关配置 |None|


* 更换方式

| 策略 | 说明 |
| ---- | ---- |
| `random` | 每次请求随机选择一个代理，默认方式 |
| `round_robin` | 按代理地址稳定排序后顺序轮询 |
| `weighted` | 按历史校验成功率加权随机，质量越高的代理越容易被选中 |

```bash
# 随机
curl "http://127.0.0.1:5010/get/"
# 轮询
curl "http://127.0.0.1:5010/get/?strategy=round_robin"
# 加权随机，只要地址文本
curl "http://127.0.0.1:5010/get/?strategy=weighted&format=text"
```

* 稳定代理网关

网关提供一个固定的代理地址，客户端只要配置一次，后续由网关自动更换上游代理；支持普通 HTTP 请求和 HTTPS CONNECT 隧道。

```bash
# 启动网关，默认监听 0.0.0.0:5011
python proxyPool.py gateway

# HTTP 请求
curl -x http://127.0.0.1:5011 http://httpbin.org/ip

# HTTPS 请求（CONNECT 隧道）
curl -x http://127.0.0.1:5011 https://httpbin.org/ip
```

网关默认使用 `GATEWAY_STRATEGY` 指定的策略。还可以用“策略名:密码”作为代理认证信息，在同一个网关地址上临时切换更换方式；未开启认证时密码可任意填写：

```bash
# GATEWAY_AUTH = "user:password"
curl -x http://round_robin:password@127.0.0.1:5011 http://httpbin.org/ip
curl -x http://weighted:password@127.0.0.1:5011 http://httpbin.org/ip
```

* WAF 自动检测

网关会对普通 HTTP 响应做 WAF 指纹检测。命中 Cloudflare、Akamai、AWS WAF、Imperva、Sucuri、F5、ModSecurity、阿里云、腾讯云、百度云加速、安全狗等常见 WAF 后，会自动换下一个代理重试：

```bash
# 无需额外参数，命中 WAF 后自动切换上游代理
curl -x http://127.0.0.1:5011 http://example.com/
```

如果所有代理都被 WAF 拦截，网关会把最后一次 WAF 响应返回给客户端，并附加：

- `X-ProxyPool-WAF`：命中的 WAF 类型，例如 `cloudflare`
- `X-ProxyPool-WAF-Score`：命中分数

可通过 `WAF_CUSTOM_HEADERS`、`WAF_CUSTOM_KEYWORDS`、`WAF_CUSTOM_STATUS` 增加自定义规则，或通过 `WAF_DETECT_ENABLED = False` 关闭检测。

> HTTPS 使用 CONNECT 隧道，内容已加密，网关无法检测目标站 WAF；WAF 检测仅对普通 HTTP 转发生效。chunked、超大请求体或带 `Expect: 100-continue` 的请求只流式转发，不做 WAF 重试。

> 网关只支持 HTTP/HTTPS 代理协议，不支持 SOCKS5；每个请求使用独立的上游连接，不支持 WebSocket 等长连接协议。

* 监控工作台

启动 `server` 后访问：

```text
http://127.0.0.1:5010/dashboard/
```

工作台包含：

- 代理池概览与趋势：总数、HTTP/HTTPS、健康度、来源/地区分布
- 代理列表：搜索、协议/来源/状态筛选、排序、分页、删除
- 网关与 WAF 统计：请求量、成功率、延迟、WAF 类型分布、最近事件
- 策略与配置：查看配置，在线切换 `random` / `round_robin` / `weighted`
- SSE 实时推送：网关指标 1 秒、WAF 2 秒、代理池 3 秒、趋势 10 秒；断线自动重连，失败回退轮询

默认登录账号为 `admin`，密码为 `change-me`，请通过 `MONITOR_AUTH_PASSWORD` 修改。指标存储在 `data/monitor.db`（SQLite），多进程共享，默认保留 7 天。

> 工作台前端位于 `dashboard/`，构建产物在 `monitor/static/`。修改前端后执行 `cd dashboard && npm install && npm run build`。


* 爬虫使用

　　如果要在爬虫代码中使用的话， 可以将此api封装成函数直接使用，例如：

```python
import requests

def get_proxy():
    return requests.get("http://127.0.0.1:5010/get/").json()

def delete_proxy(proxy):
    requests.get("http://127.0.0.1:5010/delete/?proxy={}".format(proxy))

# your spider code

def getHtml():
    # ....
    retry_count = 5
    proxy = get_proxy().get("proxy")
    while retry_count > 0:
        try:
            html = requests.get('http://www.example.com', proxies={"http": "http://{}".format(proxy)})
            # 使用代理访问
            return html
        except Exception:
            retry_count -= 1
    # 删除代理池中代理
    delete_proxy(proxy)
    return None
```

### 扩展代理

　　项目默认包含几个免费的代理获取源，但是免费的毕竟质量有限，所以如果直接运行可能拿到的代理质量不理想。所以，提供了代理获取的扩展方法。

　　添加一个新的代理源方法如下:

* 1、在 `fetcher/sources/` 目录下新建 `.py` 文件，继承 `BaseFetcher` 基类，声明 `name`/`url`/`enabled` 属性，实现 `fetch()` 方法以生成器(yield)形式返回`host:port`格式的代理，例如:

```python
from fetcher.baseFetcher import BaseFetcher
from util.webRequest import WebRequest

class MyProxyFetcher(BaseFetcher):
    """我的代理源"""

    name = "myproxy"
    url = "https://www.example.com/"
    enabled = True

    def fetch(self):
        r = WebRequest().get("https://www.example.com/api/proxies")
        for item in r.json:
            yield item["ip"] + ":" + item["port"]
```

* 2、添加好后，`schedule` 进程下次抓取时会自动扫描 `fetcher/sources/` 目录并启用新代理源，无需修改配置。

　　可用 `python proxyPool.py fetcher` 命令查看当前启用的代理源列表。

　　如需临时禁用某个代理源，在 [setting.py](setting.py) 的 `PROXY_FETCHER_EXCLUDE` 黑名单中添加其 `name` 即可。

### 免费代理源

   目前实现的采集免费代理网站有(排名不分先后, 下面仅是对其发布的免费代理情况, 付费代理测评可以参考[这里](https://zhuanlan.zhihu.com/p/33576641)):
   
  | 代理名称         |  状态  | 更新速度 | 可用率 | 地址                                                | 代码                                                      |
  |--------------|  ---- |------|-----|---------------------------------------------------|---------------------------------------------------------|
  | 快代理          |  ✔    | ★    | *   | [地址](https://www.kuaidaili.com/)                  | [`kuaidaili.py`](/fetcher/sources/kuaidaili.py)         |
  | 云代理          |  ✔    | ★    | *   | [地址](http://www.ip3366.net/)                      | [`ip3366.py`](/fetcher/sources/ip3366.py)               |
  | 小幻代理         |  ✔    | ★    | *   | [地址](https://ip.ihuan.me/)                        | [`ihuan.py`](/fetcher/sources/ihuan.py)                 |
  | 89代理         |  ✔    | ★★   | **  | [地址](https://www.89ip.cn)                         | [`ip89.py`](/fetcher/sources/ip89.py)                   |
  | 谷德代理         |  ✔    | ★★   | *** | [地址](https://www.goodips.com)                     | [`goodips.py`](/fetcher/sources/goodips.py)             |
  | Proxifly     |  ✔    | ★★   | **  | [地址](https://proxifly.dev)                        | [`proxifly.py`](/fetcher/sources/proxifly.py)           |
  | FreeVPNNode  |  ✔    | ★★   | *   | [地址](https://cn.freevpnnode.com)                  | [`freevpnnode.py`](/fetcher/sources/freevpnnode.py)     |
  | Geonode      |  ✔    | ★★   | **  | [地址](https://geonode.com)                         | [`geonode.py`](/fetcher/sources/geonode.py)             |
  | RoundProxies |  ✔    | ★    | *   | [地址](https://roundproxies.com/free-proxy-list)    | [`roundproxies.py`](/fetcher/sources/roundproxies.py)   |
  | Proxyspace   |  ✔    | ★★   | ★★  | [地址](https://proxyspace.pro)                      | [`proxyspace.py`](/fetcher/sources/proxyspace.py)       |
  | Proxyhub     |  ✔    | ★★   | ★★  | [地址](https://proxyhub.me)                         | [`proxyhub.py`](/fetcher/sources/proxyhub.py)           |
  | FreeProxyWorld |  ✔  | ★★   | ★★  | [地址](https://www.freeproxy.world)                 | [`freeproxyworld.py`](/fetcher/sources/freeproxyworld.py) |
  | 蜜蜂代理           |  ✔    | ★    | ★   | [地址](https://www.beesproxy.com/free)              | [`beesproxy.py`](/fetcher/sources/beesproxy.py)         |

  
  如果还有其他好的免费代理网站, 可以在提交在[issues](https://github.com/jhao104/proxy_pool/issues/71), 下次更新时会考虑在项目中支持。

### 问题反馈

　　任何问题欢迎在[Issues](https://github.com/jhao104/proxy_pool/issues) 中反馈，同时也可以到我的[博客](http://www.spiderpy.cn/blog/message)中留言。

　　你的反馈会让此项目变得更加完美。

### 贡献代码

　　本项目仅作为基本的通用的代理池架构，不接收特有功能(当然,不限于特别好的idea)。

　　本项目依然不够完善，如果发现bug或有新的功能添加，请在[Issues](https://github.com/jhao104/proxy_pool/issues)中提交bug(或新功能)描述，我会尽力改进，使她更加完美。

　　这里感谢以下contributor的无私奉献：

　　[@kangnwh](https://github.com/kangnwh) | [@bobobo80](https://github.com/bobobo80) | [@halleywj](https://github.com/halleywj) | [@newlyedward](https://github.com/newlyedward) | [@wang-ye](https://github.com/wang-ye) | [@gladmo](https://github.com/gladmo) | [@bernieyangmh](https://github.com/bernieyangmh) | [@PythonYXY](https://github.com/PythonYXY) | [@zuijiawoniu](https://github.com/zuijiawoniu) | [@netAir](https://github.com/netAir) | [@scil](https://github.com/scil) | [@tangrela](https://github.com/tangrela) | [@highroom](https://github.com/highroom) | [@luocaodan](https://github.com/luocaodan) | [@vc5](https://github.com/vc5) | [@1again](https://github.com/1again) | [@obaiyan](https://github.com/obaiyan) | [@zsbh](https://github.com/zsbh) | [@jiannanya](https://github.com/jiannanya) | [@Jerry12228](https://github.com/Jerry12228) | [@zeyudada](https://github.com/zeyudada)


### Release Notes

   [changelog](https://jhao104.github.io/proxy_pool/changelog/)

<a href="https://hellogithub.com/repository/92a066e658d147cc8bd8397a1cb88183" target="_blank"><img src="https://api.hellogithub.com/v1/widgets/recommend.svg?rid=92a066e658d147cc8bd8397a1cb88183&claim_uid=DR60NequsjP54Lc" alt="Featured｜HelloGitHub" style="width: 250px; height: 54px;" width="250" height="54" /></a>
