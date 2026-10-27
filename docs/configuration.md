# 配置参考

配置文件 `setting.py` 位于项目的主目录下，配置主要分为九类：**服务配置**、**代理更换策略**、**代理网关**、**WAF 检测**、**监控工作台**、**数据库配置**、**采集配置**、**校验配置**、**调度配置**。

## 服务配置

### `HOST`

API 服务监听的 IP。本机访问设置为 `127.0.0.1`，开启远程访问设置为 `0.0.0.0`。

- 默认值：`"0.0.0.0"`

### `PORT`

API 服务监听的端口。

- 默认值：`5010`

## 代理更换策略

### `PROXY_STRATEGY`

API `/get` 接口的默认代理更换方式，也可通过请求参数 `strategy` 临时覆盖。

- `random`：随机选择
- `round_robin`：轮询选择
- `weighted`：按校验成功率加权随机

- 默认值：`"random"`

## 代理网关

### `GATEWAY_ENABLED`

使用 `python proxyPool.py all` 启动时是否同时启动代理网关。

- 默认值：`True`

### `GATEWAY_HOST` / `GATEWAY_PORT`

代理网关监听的地址和端口。客户端将该地址配置为 HTTP 代理即可。

- 默认值：`"0.0.0.0"` / `5011`

### `GATEWAY_STRATEGY`

网关默认使用的代理更换方式，取值同 `PROXY_STRATEGY`。

- 默认值：`"random"`

### `GATEWAY_AUTH`

网关认证信息，格式 `username:password`。留空表示不认证。

开启认证后，客户端还可以用 `策略名:password` 作为认证信息，在同一个网关地址上临时切换更换方式，例如 `round_robin:password`。

- 默认值：`""`

### `GATEWAY_RETRY`

单个请求在选择上游代理失败时的最大尝试次数。网关只会在“连接上游失败”时重试，不会重复发送已经发送过的请求体。

- 默认值：`3`

### `GATEWAY_CONNECT_TIMEOUT`

连接上游代理的超时时间，单位秒。

- 默认值：`10`

### `GATEWAY_HEADER_TIMEOUT`

读取客户端请求头、上游 CONNECT 响应的超时时间，单位秒。

- 默认值：`30`

## WAF 检测

以下配置只影响网关的普通 HTTP 转发。HTTPS CONNECT 隧道内容已加密，无法检测目标站 WAF。

### `WAF_DETECT_ENABLED`

是否开启 WAF 指纹检测。命中后网关会自动换下一个代理重试。

- 默认值：`True`

### `WAF_SCORE_THRESHOLD`

指纹命中分数阈值。分数越高越不容易误判：

- `1`：弱指纹也会命中，例如仅 `Server: cloudflare`；
- `2`：推荐值，弱指纹需要配合可疑状态码或其他指纹；
- `3`：只命中强指纹。

- 默认值：`2`

### `WAF_BODY_PREFIX_SIZE`

读取响应体前缀用于关键词检测的最大字节数。设为 `0` 可关闭响应体关键词检测，仅使用响应头和状态码。

- 默认值：`32768`

### `WAF_BODY_READ_TIMEOUT`

读取响应体前缀的超时时间，单位秒。超时后继续正常转发响应。

- 默认值：`2`

### `WAF_MAX_REPLAY_BODY`

WAF 命中后允许缓存并重放的请求体上限，单位字节。超过该值、使用 chunked 或带 `Expect: 100-continue` 的请求只流式转发，不做 WAF 重试。

- 默认值：`1048576`（1MB）

### `WAF_CUSTOM_HEADERS`

自定义 WAF 响应头规则。列表元素可以是：

- `"header-name"`：响应头存在即命中；
- `"header-name:value-substring"`：响应头值包含指定子串时命中。

```python
WAF_CUSTOM_HEADERS = ["x-my-waf", "x-company-waf: blocked"]
```

- 默认值：`[]`

### `WAF_CUSTOM_KEYWORDS`

自定义响应体关键词，大小写不敏感。

```python
WAF_CUSTOM_KEYWORDS = ["custom block page", "自定义拦截页面"]
```

- 默认值：`[]`

### `WAF_CUSTOM_STATUS`

直接判定为 WAF 的状态码列表。

```python
WAF_CUSTOM_STATUS = [418]
```

- 默认值：`[]`

## 监控工作台

### `MONITOR_ENABLED`

是否启用监控工作台指标。关闭后工作台数据接口返回 503，代理池和网关仍正常工作。

- 默认值：`True`

### `MONITOR_DB_PATH`

监控指标 SQLite 文件路径。相对路径基于项目根目录。

- 默认值：`"data/monitor.db"`

### `MONITOR_AUTH_USER` / `MONITOR_AUTH_PASSWORD`

工作台登录账号和密码。工作台强制登录，请务必修改默认密码。

```python
MONITOR_AUTH_USER = "admin"
MONITOR_AUTH_PASSWORD = "change-me"
```

- 默认值：`"admin"` / `"change-me"`

### `MONITOR_SESSION_TTL`

登录会话有效期，单位秒。

- 默认值：`86400`

### `MONITOR_COOKIE_SECURE`

是否只通过 HTTPS 发送登录 Cookie。通过 HTTPS 访问工作台时建议设为 `True`。

- 默认值：`False`

### `MONITOR_RETENTION_DAYS`

趋势、网关指标和 WAF 事件的保留天数。

- 默认值：`7`

### `MONITOR_REFRESH_SECONDS`

工作台 SSE 不可用或断线时，前端回退轮询的间隔，单位秒。SSE 正常连接时按固定节奏推送：网关指标 1 秒、WAF 2 秒、代理池 3 秒、趋势 10 秒。

- 默认值：`5`

## 数据库配置

### `DB_CONN`

存放代理 IP 的数据库 URI，配置格式为：

```
db_type://[[user]:[pwd]]@ip:port/[db]
```

目前支持的 `db_type`：`redis`、`ssdb`。

配置示例：

```python
# Redis
DB_CONN = 'redis://@127.0.0.1:6379'
DB_CONN = 'redis://:123456@127.0.0.1:6379'
DB_CONN = 'redis://:123456@127.0.0.1:6379/15'

# SSDB
DB_CONN = 'ssdb://@127.0.0.1:8888'
DB_CONN = 'ssdb://:123456@127.0.0.1:8888'
```

### `TABLE_NAME`

存放代理的数据载体名称。SSDB 和 Redis 的存放结构为 hash。

- 默认值：`"use_proxy"`

## 采集配置

代理采集采用插件架构，调度器自动扫描 `fetcher/sources/` 目录，加载所有 `enabled=True` 的代理源。新增代理源只需在 `sources/` 下创建文件，无需修改配置。

查看当前启用的代理源：

```bash
python proxyPool.py fetcher
```

### `PROXY_FETCHER_EXCLUDE`

代理源黑名单。列表中的类名对应的代理源不会被加载，即使 `enabled=True`。适用于临时禁用某个代理源而不修改其源文件。

```python
PROXY_FETCHER_EXCLUDE = [
    # "BinglxFetcher",   # 临时禁用冰凌代理
]
```

如需永久禁用，建议直接在源文件中设置 `enabled = False`。

## 校验配置

### `HTTP_URL`

用于检验代理是否可用的地址。

- 默认值：`"http://httpbin.org"`

### `HTTPS_URL`

用于检验代理是否支持 HTTPS 的地址。

- 默认值：`"https://www.qq.com"`

### `VERIFY_TIMEOUT`

检验代理的超时时间，单位秒。使用代理访问 `HTTP_URL` / `HTTPS_URL` 耗时超过 `VERIFY_TIMEOUT` 时，视为代理不可用。

- 默认值：`10`

### `MAX_FAIL_COUNT`

检验代理允许的最大失败次数。超过则剔除代理。

- 默认值：`0`（即失败一次即删除）

### `POOL_SIZE_MIN`

代理检测定时任务运行前，若代理数量小于 `POOL_SIZE_MIN`，则先运行抓取程序。

- 默认值：`20`

## 代理属性

### `PROXY_REGION`

是否启用代理地域属性。开启后会尝试解析代理 IP 的地理位置信息。

- 默认值：`True`

## 调度配置

### `TIMEZONE`

调度器的时区设置。如果在虚拟机上运行时出现 `ValueError: Timezone offset does not match system offset` 错误，请设置该配置项。

- 默认值：`"Asia/Shanghai"`