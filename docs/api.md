# API 使用

## 接口列表

启动 ProxyPool 的 `server` 后会提供如下 HTTP 接口：

| 接口 | 方法 | 说明 | 参数 |
|------|------|------|------|
| `/` | GET | 返回 API 列表 | 无 |
| `/get` | GET | 按策略返回一个代理 | 可选：`?type=https`、`?strategy=random / round_robin / weighted`、`?format=text` |
| `/pop` | GET | 返回并删除一个代理 | 可选：`?type=https` 过滤 HTTPS 代理 |
| `/all` | GET | 返回所有代理 | 可选：`?type=https` 过滤 HTTPS 代理 |
| `/count` | GET | 返回代理数量统计 | 无 |
| `/delete` | GET | 删除指定代理 | `?proxy=host:port` |
| `/strategies` | GET | 返回支持的代理更换方式 | 无 |
| `/gateway` | GET | 返回网关配置信息 | 无 |

## 代理更换方式

`/get` 支持通过 `strategy`（别名 `mode`）指定代理更换方式：

| 策略 | 说明 |
|------|------|
| `random` | 随机选择，默认方式 |
| `round_robin` | 按代理地址稳定排序后顺序轮询 |
| `weighted` | 按历史校验成功率加权随机，失败次数越多权重越低 |

```bash
# 随机
curl "http://127.0.0.1:5010/get/"

# 轮询
curl "http://127.0.0.1:5010/get/?strategy=round_robin"

# 加权随机
curl "http://127.0.0.1:5010/get/?strategy=weighted"

# 只返回 host:port 文本，方便直接用于脚本
curl "http://127.0.0.1:5010/get/?strategy=round_robin&format=text"
```

策略别名：`rand`、`rr`、`round-robin`、`weight`、`wrr`。传入不支持的策略会返回 HTTP 400。代理池为空时，JSON 格式仍返回 `{"code": 0, "src": "no proxy"}`，`format=text` 返回 HTTP 503。

也可以通过 `setting.py` 的 `PROXY_STRATEGY` 修改默认策略。轮询游标保存在进程内，多进程部署时每个进程独立计数；稳定代理网关为单进程，不受此限制。

## 稳定代理网关

除了通过 API 主动取代理，还可以启动一个固定地址的代理网关：

```bash
python proxyPool.py gateway
```

默认监听 `0.0.0.0:5011`。客户端把该地址配置为 HTTP 代理即可，网关会按 `GATEWAY_STRATEGY` 自动选择上游代理：

```bash
curl -x http://127.0.0.1:5011 http://httpbin.org/ip
curl -x http://127.0.0.1:5011 https://httpbin.org/ip
```

开启 `GATEWAY_AUTH` 后，可以用“策略名:密码”作为代理认证信息，在同一个网关地址上切换更换方式：

```bash
# GATEWAY_AUTH = "user:password"
curl -x http://round_robin:password@127.0.0.1:5011 http://httpbin.org/ip
curl -x http://weighted:password@127.0.0.1:5011 http://httpbin.org/ip
```

### WAF 自动检测

网关转发普通 HTTP 响应时会检测 WAF 拦截页，命中后自动换下一个代理重试。所有代理都被拦截时，网关返回最后一次 WAF 响应，并附加：

- `X-ProxyPool-WAF`：WAF 类型，例如 `cloudflare`
- `X-ProxyPool-WAF-Score`：命中分数

`/gateway` 接口会返回当前 WAF 配置摘要。HTTPS CONNECT 隧道无法检测目标站 WAF；chunked、超大请求体或带 `Expect: 100-continue` 的请求只流式转发，不做 WAF 重试。完整规则和自定义配置见 [稳定代理网关](gateway.md)。

网关支持 HTTP 转发和 HTTPS CONNECT 隧道，不支持 SOCKS5。完整说明见 [稳定代理网关](gateway.md)。

## 调用示例

### 在爬虫中使用

通过调用 API 接口来使用代理池：

```python
import requests


def get_proxy():
    return requests.get("http://127.0.0.1:5010/get/").json()


def delete_proxy(proxy):
    requests.get("http://127.0.0.1:5010/delete/?proxy={}".format(proxy))


def get_html():
    retry_count = 5
    proxy = get_proxy().get("proxy")
    while retry_count > 0:
        try:
            # 使用代理访问
            html = requests.get(
                "http://www.example.com",
                proxies={
                    "http": "http://{}".format(proxy),
                    "https": "https://{}".format(proxy),
                },
            )
            return html
        except Exception:
            retry_count -= 1
            # 删除代理池中代理
            delete_proxy(proxy)
    return None
```

本例中在本地 `127.0.0.1` 启动端口为 `5010` 的 `server`，使用 `/get` 接口获取代理，`/delete` 删除代理。

### 获取 HTTPS 代理

```python
# 只获取支持 HTTPS 的代理
proxy = requests.get("http://127.0.0.1:5010/get/?type=https").json()
```

### 获取代理统计

```python
# 返回代理数量、类型分布、来源分布
stats = requests.get("http://127.0.0.1:5010/count/").json()
# 示例返回: {"http_type": {"http": 10, "https": 5}, "source": {"freeProxy01": 8, "freeProxy02": 7}, "count": 15}
```

## 监控工作台

API 服务同时提供监控工作台：

```text
http://127.0.0.1:5010/dashboard/
```

工作台需要登录，默认账号 `admin`，密码由 `MONITOR_AUTH_PASSWORD` 配置。它提供代理池概览、代理列表、网关/WAF 统计、趋势图和在线策略切换，数据接口位于 `/dashboard/api/*`，并通过 `/dashboard/api/stream` 使用 SSE 实时推送指标。详见 [监控工作台](dashboard.md)。

## 直接读取数据库

除了通过 API 接口，也可以直接读取数据库获取代理。目前支持两种数据库：Redis 和 SSDB。

- **Redis**：存储结构为 hash，hash name 为配置项中的 `TABLE_NAME`（默认 `use_proxy`）
- **SSDB**：存储结构为 hash，hash name 为配置项中的 `TABLE_NAME`

可以在代码中自行读取数据库获取代理列表。