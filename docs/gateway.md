# 稳定代理网关

代理网关提供一个固定的代理地址。客户端只需要配置一次，后续请求由网关按策略自动选择、更换上游代理，适合不想在业务代码里反复调用 `/get` 的场景。

## 启动

```console
# 单独启动网关
python proxyPool.py gateway

# 同时启动 API 和网关
python proxyPool.py all
```

默认监听 `0.0.0.0:5011`，可通过 `GATEWAY_HOST` / `GATEWAY_PORT` 修改。生产环境建议把网关作为独立进程启动；`all` 命令会把网关放在 API 进程的后台线程中，适合本地或简单部署。

## 客户端配置

把网关地址配置为 HTTP 代理即可。

```console
# HTTP
curl -x http://127.0.0.1:5011 http://httpbin.org/ip

# HTTPS（CONNECT 隧道）
curl -x http://127.0.0.1:5011 https://httpbin.org/ip
```

Python `requests`：

```python
import requests

proxies = {
    "http": "http://127.0.0.1:5011",
    "https": "http://127.0.0.1:5011",
}
print(requests.get("https://httpbin.org/ip", proxies=proxies, timeout=10).text)
```

浏览器或系统代理：HTTP 代理和 HTTPS 代理都填写 `127.0.0.1:5011`。

## 更换方式

网关默认使用 `GATEWAY_STRATEGY` 指定的方式：

| 策略 | 说明 |
|------|------|
| `random` | 每次请求随机选择 |
| `round_robin` | 按代理地址稳定排序后轮询 |
| `weighted` | 按校验成功率加权随机 |

### 同一个网关切换策略

开启 `GATEWAY_AUTH` 后，可以用“策略名:密码”作为代理认证信息：

```python
# setting.py
GATEWAY_AUTH = "user:password"
```

```console
curl -x http://round_robin:password@127.0.0.1:5011 http://httpbin.org/ip
curl -x http://weighted:password@127.0.0.1:5011 http://httpbin.org/ip
```

普通认证 `user:password` 仍然可用，此时使用默认策略。

未开启 `GATEWAY_AUTH` 时，也可以直接把策略名作为代理用户名（密码任意）来切换：

```console
curl -x http://round_robin:any@127.0.0.1:5011 http://httpbin.org/ip
```

## 认证

`GATEWAY_AUTH` 留空表示不认证。网关监听在 `0.0.0.0` 且未配置认证时，启动日志会输出安全警告。建议在公网环境务必配置认证，或只监听 `127.0.0.1`。

## WAF 自动检测

网关转发普通 HTTP 响应时会读取响应头、状态码和响应体前缀，识别 WAF 拦截页；命中后自动换下一个代理重试。

### 内置指纹

- Cloudflare
- Akamai
- AWS WAF
- Imperva / Incapsula
- Sucuri
- F5 BIG-IP ASM
- ModSecurity
- Barracuda
- FortiWeb
- 阿里云 WAF
- 腾讯云 WAF
- 百度云加速
- 安全狗
- 创宇盾
- 通用 WAF 拦截页关键词

检测采用评分机制：强指纹（如 `CF-Mitigated: challenge`）可直接命中，弱指纹（如 `Server: cloudflare`）需要配合可疑状态码或其他指纹。默认阈值为 `WAF_SCORE_THRESHOLD = 2`。

### 命中后的行为

- 请求体较小且可重放时，自动换下一个代理重试，最多 `GATEWAY_RETRY` 次；
- 所有代理都被 WAF 拦截时，返回最后一次 WAF 响应，并附加 `X-ProxyPool-WAF`、`X-ProxyPool-WAF-Score` 响应头；
- 连接失败和 WAF 命中都会切换到下一个代理，最多 `GATEWAY_RETRY` 次；
- 不会把已发送的请求体重复提交给同一个上游代理。

### 请求体限制

为了在 WAF 命中后重放请求，网关会缓存不超过 `WAF_MAX_REPLAY_BODY` 的请求体。以下情况只流式转发，不做 WAF 重试：

- `Transfer-Encoding: chunked`
- 请求体超过 `WAF_MAX_REPLAY_BODY`
- 带 `Expect: 100-continue`

### 自定义规则

```python
# setting.py

# 响应头存在即命中；也可以写 "header-name:value-substring"
WAF_CUSTOM_HEADERS = [
    "x-my-waf",
    "x-company-waf: blocked",
]

# 响应体关键词，大小写不敏感
WAF_CUSTOM_KEYWORDS = [
    "custom block page",
    "自定义拦截页面",
]

# 这些状态码直接判定为 WAF
WAF_CUSTOM_STATUS = [418]
```

也可以通过环境变量配置，多个值用逗号分隔：

```console
WAF_CUSTOM_HEADERS="x-my-waf,x-company-waf: blocked"
WAF_CUSTOM_KEYWORDS="custom block page,自定义拦截页面"
WAF_CUSTOM_STATUS="418,403"
```

### 配置项

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `WAF_DETECT_ENABLED` | `True` | 是否开启网关 WAF 检测 |
| `WAF_SCORE_THRESHOLD` | `2` | 指纹命中分数阈值 |
| `WAF_BODY_PREFIX_SIZE` | `32768` | 读取响应体前缀的最大字节数 |
| `WAF_BODY_READ_TIMEOUT` | `2` | 读取响应体前缀的超时秒数 |
| `WAF_MAX_REPLAY_BODY` | `1048576` | 可缓存并重放的请求体上限 |
| `WAF_CUSTOM_HEADERS` | `[]` | 自定义响应头规则 |
| `WAF_CUSTOM_KEYWORDS` | `[]` | 自定义响应体关键词 |
| `WAF_CUSTOM_STATUS` | `[]` | 直接判定为 WAF 的状态码 |

### WAF 检测限制

- HTTPS 通过 CONNECT 隧道转发，内容已加密，网关无法检测目标站 WAF；
- 只读取响应体前缀，关键词跨越前缀边界或使用 br 等不支持的压缩编码时可能漏检；
- 通用关键词可能对正常 403 页面产生误判，可通过提高 `WAF_SCORE_THRESHOLD` 或关闭 `WAF_DETECT_ENABLED` 调整；
- 开启 WAF 检测后，网关会在转发前读取响应体前缀，可能增加首包延迟；`text/event-stream` 等流式响应会跳过响应体检测；
- WAF 检测只影响网关 HTTP 转发，不会修改代理池数据。

## 重试

当连接上游代理失败时，网关会自动选择下一个代理重试，最多 `GATEWAY_RETRY` 次。WAF 命中后的重试也受该次数限制。已经发送过请求体后不会重试，避免重复提交数据。

## 限制

- 只支持 HTTP/HTTPS 代理协议，不支持 SOCKS5。
- 普通 HTTP 请求使用独立上游连接，HTTPS 通过 CONNECT 隧道转发。
- 不支持 WebSocket 等需要长期保持的上层协议。
- 网关不会修改代理池内容；代理的采集和验证仍由 `schedule` 进程负责。

## Docker

容器默认同时启动 API（`5010`）和网关（`5011`）：

```console
docker run \
  --env DB_CONN=redis://:password@ip:port/0 \
  --env GATEWAY_STRATEGY=weighted \
  --env GATEWAY_AUTH=user:password \
  -p 5010:5010 -p 5011:5011 \
  jhao104/proxy_pool:latest
```
