# 监控工作台

监控工作台是一个独立的 React 单页应用，由 API 服务在 `/dashboard/` 路径下提供。它展示代理池、网关和 WAF 指标，并支持在线切换默认代理策略。

## 启动

工作台随 API 服务启动：

```console
python proxyPool.py server
```

访问：

```text
http://127.0.0.1:5010/dashboard/
```

如果使用 `python proxyPool.py all`，API 和网关会同时启动，工作台也能看到网关指标。

## 登录

工作台强制登录，默认账号：

```python
# setting.py
MONITOR_AUTH_USER = "admin"
MONITOR_AUTH_PASSWORD = "change-me"
```

请务必修改默认密码，推荐通过环境变量配置：

```console
MONITOR_AUTH_USER=admin
MONITOR_AUTH_PASSWORD=your-strong-password
```

会话有效期由 `MONITOR_SESSION_TTL` 控制（默认 24 小时）。如果通过 HTTPS 访问，请设置 `MONITOR_COOKIE_SECURE=True`。

工作台使用 Flask 签名 Cookie 保存登录态，Cookie 设置为 `HttpOnly`、`SameSite=Strict`。连续登录失败会触发临时锁定。

## 功能

### 代理池概览

- 代理总数、HTTP/HTTPS 分布
- 健康 / 有失败代理数量
- 平均失败次数、平均校验次数
- 来源和地区分布

### 代理列表

- 搜索代理地址、来源、地区
- 按 HTTP/HTTPS、来源、健康状态筛选
- 按地址、失败次数、校验次数、校验时间排序
- 分页
- 删除指定代理

### 实时推送

工作台通过 SSE（Server-Sent Events）接收实时数据：

| 数据 | 推送间隔 |
|------|----------|
| 网关指标 | 1 秒 |
| WAF 事件 | 2 秒 |
| 代理池与策略 | 3 秒 |
| 趋势数据 | 10 秒 |

- 断线时浏览器自动重连；
- SSE 不可用或连接失败时自动回退到轮询（间隔由 `MONITOR_REFRESH_SECONDS` 控制）；
- 反向代理需要关闭响应缓冲，接口已返回 `X-Accel-Buffering: no`；
- SSE 连接会占用一个 WSGI worker，多个并发工作台连接建议使用 gevent/eventlet worker 或独立部署。

### 趋势图

- 代理池总数 / HTTP / HTTPS 趋势（每分钟快照）
- 网关请求、成功、WAF 命中、错误趋势

调度器每分钟记录一次代理池快照；打开工作台时也会补充记录。历史数据保留 `MONITOR_RETENTION_DAYS` 天。

### 网关与 WAF 统计

- 24 小时网关请求量、成功率
- WAF 命中次数、最终拦截次数、重试次数
- 平均/最大延迟
- WAF 类型分布
- 最近 WAF 事件（时间、规则、分数、目标、代理、是否重试/最终拦截）

### 策略与配置

- 查看当前生效策略、配置默认策略、运行时覆盖
- 在线切换 `random` / `round_robin` / `weighted`
- 恢复配置默认策略
- 查看网关地址、重试、超时、WAF 阈值、请求体重放上限、指标保留天数等配置

运行时策略覆盖写入 SQLite，API 和网关进程会在约 2 秒内生效。

## 指标存储

指标使用 SQLite 存储：

```python
MONITOR_DB_PATH = "data/monitor.db"
```

- 默认相对于项目根目录；
- 多进程（API、scheduler、gateway）通过同一个 SQLite 文件共享指标；
- 使用 WAL 模式，写指标不会阻塞代理转发；
- 监控写入失败会被忽略，不影响代理池和网关主流程；
- Docker 部署时建议把 `data/` 挂载为持久卷。

## 配置

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `MONITOR_ENABLED` | `True` | 是否启用工作台指标 |
| `MONITOR_DB_PATH` | `data/monitor.db` | 指标 SQLite 路径 |
| `MONITOR_AUTH_USER` | `admin` | 登录用户名 |
| `MONITOR_AUTH_PASSWORD` | `change-me` | 登录密码，必须修改 |
| `MONITOR_SESSION_TTL` | `86400` | 会话有效期（秒） |
| `MONITOR_COOKIE_SECURE` | `False` | HTTPS 部署时设为 `True` |
| `MONITOR_RETENTION_DAYS` | `7` | 指标保留天数 |
| `MONITOR_REFRESH_SECONDS` | `5` | 前端轮询间隔（秒） |

## API

工作台数据接口位于 `/dashboard/api/`，除登录接口外均需要登录：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/dashboard/api/session` | GET | 当前登录状态 |
| `/dashboard/api/login` | POST | 登录 |
| `/dashboard/api/logout` | POST | 退出 |
| `/dashboard/api/overview` | GET | 概览、网关/WAF 统计、策略配置 |
| `/dashboard/api/stream` | GET | SSE 实时推送 |
| `/dashboard/api/proxies` | GET | 代理列表、筛选、分页 |
| `/dashboard/api/proxies/delete` | POST | 删除代理 |
| `/dashboard/api/trends` | GET | 代理池和网关趋势 |
| `/dashboard/api/waf` | GET | WAF 规则统计和最近事件 |
| `/dashboard/api/config` | GET | 配置摘要 |
| `/dashboard/api/strategy` | POST | 设置或重置运行时策略 |
| `/dashboard/api/health` | GET | 工作台存储健康状态 |

## 前端开发与构建

前端源码位于 `dashboard/`：

```console
cd dashboard
npm install
npm run dev      # 开发模式，API 代理到 127.0.0.1:5010
npm run build    # 输出到 ../monitor/static
```

生产环境需要先执行 `npm run build`，然后启动或重启 API 服务。仓库已包含构建产物，直接部署即可。

## 注意

- 工作台登录凭证与现有 API 鉴权相互独立，现有 `/get` 等接口默认仍然公开。
- 如果 API 部署在反向代理后，请确保正确转发 Cookie 和 `X-Forwarded-*` 头。
- 公网环境务必修改默认密码，并在 HTTPS 下启用 `MONITOR_COOKIE_SECURE`。
