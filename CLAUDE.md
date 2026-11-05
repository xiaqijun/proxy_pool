# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指导。

## 技术栈
Python (3.8–3.11)、Flask (API)、Redis/SSDB (代理存储)、SQLite (监控指标)、APScheduler (调度)、React + Vite (监控工作台)。Python 依赖版本固定记录在 `requirements.txt` 中，前端依赖见 `dashboard/package.json`。

## 常用命令
- 安装依赖：`pip install -r requirements.txt`
- 运行代理爬取/验证调度器：`python proxyPool.py schedule`
- 运行 API 服务器：`python proxyPool.py server`
- 查看启用的代理源：`python proxyPool.py fetcher`
- 构建监控工作台：`cd dashboard && npm install && npm run build`
- 开发监控工作台：`cd dashboard && npm run dev`
- 生产部署：`cp .env.example .env && docker compose -f docker-compose.prod.yml up -d --build`
- 运行单元测试：`pytest tests/unit/`
- 运行 API 测试：`pytest tests/api/`
- 运行集成测试（需真实 Redis）：`pytest tests/integration/ -m integration`
- 运行全部测试：`pytest`
- 查看覆盖率：`pytest --cov=. --cov-report=term-missing`

## 测试

### 目录结构
```
tests/
├── conftest.py              # 共享 fixtures（app、client、fake_redis、proxy_obj、reset_singleton）
├── unit/                    # 纯逻辑，零外部依赖
│   ├── test_proxy.py        # Proxy 类：构造、序列化、setter、add_source
│   ├── test_db_client.py    # DbClient.parseDbConn URI 解析
│   ├── test_config.py       # ConfigHandler 环境变量覆盖
│   ├── test_validator.py    # formatValidator 正则匹配
│   ├── test_base_fetcher.py # BaseFetcher 基类解析方法
│   ├── test_strategy.py     # 随机/轮询/加权策略与权重计算
│   ├── test_waf.py          # WAF 指纹、评分、自定义规则、压缩/chunked 解码
│   ├── test_gateway.py      # 网关头部解析、认证、策略解析
│   ├── test_gateway_forward.py # 网关 HTTP/HTTPS/WAF 真实转发（本地假上游）
│   ├── test_monitor_store.py # 监控 SQLite 快照/网关指标/WAF/策略
│   └── test_fetcher_sources.py # 各代理源 fetcher yield 逻辑
├── api/                     # Flask 测试客户端，mock ProxyHandler
│   ├── test_proxy_api.py    # /get /pop /all /count /delete /strategies /gateway 全路由
│   └── test_monitor_api.py  # 工作台登录、概览、代理列表、策略、趋势等
└── integration/             # 需要真实 Redis，标记 @pytest.mark.integration
    ├── test_redis_client.py # RedisClient 完整 CRUD
    └── test_ssdb_client.py  # SsdbClient 完整 CRUD
```

### 测试分层
- **unit/**：不依赖外部服务，用 `unittest.mock` 或 `fakeredis` 模拟，CI 必跑
- **api/**：使用 Flask `app.test_client()`，mock 掉 `ProxyHandler`，不依赖数据库
- **integration/**：需要真实 Redis，通过 `@pytest.mark.integration` 标记，按需执行

### 测试依赖
`pytest`、`pytest-cov`、`fakeredis`（纯 Python Redis 模拟，无需真实服务）

### 关键约定
- 测试函数命名：`test_` 前缀 + 下划线命名（`test_get_with_https`）
- 每个测试前自动重置 `Singleton._inst`，避免单例泄漏
- 集成测试与单元测试共存：单元测试用 fakeredis 跑，集成测试标记后按需执行

## 高层架构
免费代理池项目，爬取公开代理源、验证代理可用性、持久化存储到 Redis/SSDB，并通过 Flask RESTful API 提供代理服务。

### 核心组件
- **爬取器** (`fetcher/`)：插件架构。`baseFetcher.py` 定义 `BaseFetcher` 基类（提供 `parseProxiesFromText`/`yieldUniqueProxies` 共享方法，约定 `name`/`url`/`enabled` 属性和 `fetch()` 方法）。每个代理源在 `sources/` 目录下独立文件，继承 `BaseFetcher`。调度器自动扫描目录加载 `enabled=True` 的源。`setting.py` 的 `PROXY_FETCHER_EXCLUDE` 黑名单可临时禁用指定源。
- **数据库层** (`db/`)：抽象 `dbClient` 接口，包含 Redis (`redisClient.py`) 和 SSDB (`ssdbClient.py`) 两种实现。通过 `setting.py` 中的 `DB_CONN` 配置连接（格式：`redis://:pwd@ip:port/db` 或 `ssdb://:pwd@ip:port`）。
- **调度器** (`helper/scheduler.py`)：基于 APScheduler 的定时任务，驱动爬取器运行并触发验证。时区通过 `setting.py` 中的 `TIMEZONE` 配置。
- **验证器** (`helper/validator.py`)：使用 `HTTP_URL` (http://httpbin.org) 和 `HTTPS_URL` (https://www.qq.com) 测试代理，超时时间由 `VERIFY_TIMEOUT` 指定（默认 10 秒）。超过 `MAX_FAIL_COUNT` 的代理会被移除。当代理池数量低于 `POOL_SIZE_MIN`（默认 20）时触发重新爬取。
- **代理策略** (`helper/strategy.py`)：提供 `random`（随机）、`round_robin`（轮询）、`weighted`（按成功率加权）三种代理选择方式。`StrategyManager` 为单例；轮询游标保存在进程内，通过 key 隔离不同用途。
- **API** (`api/proxyApi.py`)：Flask 接口，包含以下端点：
  - `/get`：按策略获取一个代理（`?type=https` 筛选 HTTPS；`?strategy=random|round_robin|weighted` 指定更换方式；`?format=text` 返回纯文本）
  - `/pop`：获取并删除一个代理
  - `/all`：列出所有代理
  - `/count`：代理数量统计
  - `/delete`：通过 `?proxy=host:port` 删除指定代理
  - `/strategies`：列出支持的更换方式
  - `/gateway`：查看网关配置
  - 服务运行在 `HOST:PORT`（默认 `0.0.0.0:5010`），配置来自 `setting.py`。
- **代理网关** (`gateway/proxyGateway.py`)：基于 asyncio 的稳定代理入口，客户端把 `GATEWAY_HOST:GATEWAY_PORT`（默认 `0.0.0.0:5011`）当 HTTP 代理使用。普通请求转发绝对 URI，HTTPS 通过 CONNECT 隧道；每个请求按 `GATEWAY_STRATEGY` 选择上游代理，连接失败或 WAF 拦截时最多重试 `GATEWAY_RETRY` 次。可选 `GATEWAY_AUTH` Basic 认证，并允许用 `策略名:password` 作为认证信息临时切换策略。
- **WAF 检测** (`helper/waf.py`)：对普通 HTTP 响应做指纹评分检测，内置 Cloudflare、Akamai、AWS WAF、Imperva、Sucuri、F5、ModSecurity、阿里云、腾讯云、百度云加速、安全狗等规则，并支持自定义响应头/关键词/状态码。命中后网关自动切换代理；所有代理都被拦截时返回最后一次 WAF 响应并附加 `X-ProxyPool-WAF` 头。HTTPS CONNECT 隧道不可检测。
- **监控工作台** (`monitor/`)：`monitorStore.py` 使用 SQLite 存储代理池快照、网关指标、WAF 事件和运行时策略；`monitorApi.py` 提供 `/dashboard/` 页面和 `/dashboard/api/*` 登录保护接口。`dashboard/` 是 React + Vite 前端，构建到 `monitor/static/`。支持概览/趋势、代理列表筛选分页删除、网关/WAF 统计、SSE 实时推送和在线策略切换。调度器每分钟记录代理池快照。
- **命令行入口** (`proxyPool.py`)：基于 click 的命令行工具，包含 `schedule`、`server`、`gateway`、`all`、`fetcher` 子命令。

### 扩展代理源
1. 在 `fetcher/sources/` 目录下新建 `.py` 文件，继承 `BaseFetcher`，声明 `name`/`url`/`enabled` 属性，实现 `fetch()` 方法 yield 出 `host:port` 字符串。
2. 调度器下一轮采集自动发现并启用，无需修改配置。可用 `python proxyPool.py fetcher` 查看启用列表。

## 关键配置
所有运行时配置均在 `setting.py` 中：
- `HOST`/`PORT`：API 绑定的地址和端口
- `DB_CONN`：数据库连接字符串
- `PROXY_FETCHER_EXCLUDE`：爬取器黑名单（自动扫描 `enabled=True` 的源，排除黑名单中的）
- `HTTP_URL`/`HTTPS_URL`：验证目标 URL
- `VERIFY_TIMEOUT`：验证超时时间（默认 10 秒）
- `MAX_FAIL_COUNT`：代理被移除前允许的最大失败次数
- `POOL_SIZE_MIN`：触发重新爬取的最小代理池数量阈值
- `PROXY_REGION`：是否启用代理地区属性（默认 `True`）
- `PROXY_STRATEGY`：默认代理更换方式（`random`/`round_robin`/`weighted`）
- `GATEWAY_ENABLED`：`all` 命令是否同时启动网关（默认 `True`）
- `GATEWAY_HOST`/`GATEWAY_PORT`：网关监听地址和端口（默认 `0.0.0.0:5011`）
- `GATEWAY_STRATEGY`：网关默认代理更换方式
- `GATEWAY_AUTH`：网关 Basic 认证（`username:password`，留空不认证）
- `GATEWAY_RETRY`：网关连接上游失败或命中 WAF 时的最大尝试次数
- `GATEWAY_CONNECT_TIMEOUT`/`GATEWAY_HEADER_TIMEOUT`：网关连接/读取头部超时
- `WAF_DETECT_ENABLED`：网关是否检测 WAF（默认 `True`）
- `WAF_SCORE_THRESHOLD`：WAF 指纹命中分数阈值（默认 `2`）
- `WAF_BODY_PREFIX_SIZE`/`WAF_BODY_READ_TIMEOUT`：响应体前缀读取大小/超时
- `WAF_MAX_REPLAY_BODY`：WAF 重试时允许缓存并重放的请求体上限
- `WAF_CUSTOM_HEADERS`/`WAF_CUSTOM_KEYWORDS`/`WAF_CUSTOM_STATUS`：自定义 WAF 规则
- `MONITOR_ENABLED`：是否启用监控工作台
- `MONITOR_DB_PATH`：监控指标 SQLite 路径（默认 `data/monitor.db`）
- `MONITOR_AUTH_USER`/`MONITOR_AUTH_PASSWORD`：工作台强制登录账号密码
- `MONITOR_SESSION_TTL`/`MONITOR_COOKIE_SECURE`：会话有效期和 HTTPS Cookie 策略
- `MONITOR_RETENTION_DAYS`/`MONITOR_REFRESH_SECONDS`：指标保留天数和前端刷新间隔
- `TIMEZONE`：调度器时区（默认 `Asia/Shanghai`）

## 代码风格与命名规范
- **文件头**：每个 `.py` 文件必须包含以下标准头部：
  ```python
  # -*- coding: utf-8 -*-
  """
  -------------------------------------------------
     File Name：     fileName.py
     Description :   文件功能描述
     Author :        JHao
     date：          yyyy/mm/dd
  -------------------------------------------------
     Change Activity:
                     yyyy/mm/dd: 修改内容简述 (修改时添加此行)
  -------------------------------------------------
  """
  __author__ = 'JHao'
  ```
- **缩进**：4 个空格（Python 标准）
- **文件命名**：驼峰命名，如 `proxyFetcher.py`、`dbClient.py`、`redisClient.py`、`webRequest.py`
- **类命名**：帕斯卡命名，如 `ProxyFetcher`、`RedisClient`、`SsdbClient`、`ProxyValidator`
- **方法命名**：混合风格——数据库/爬取器方法使用驼峰命名（`getAll`、`getCount`、`changeTable`、`parseProxiesFromText`），属性和辅助方法使用下划线命名（`user_agent`、`fail_count`、`check_count`）
- **爬取器文件**：小写命名（如 `kuaidaili.py`、`proxyspace.py`），类名 PascalCase（如 `KuaidailiFetcher`、`ProxyspaceFetcher`）
- **常量**（在 `setting.py` 中）：大写下划线命名（`DB_CONN`、`PROXY_FETCHER_EXCLUDE`、`HTTP_URL`、`MAX_FAIL_COUNT`）
- **变量**：下划线命名（`proxy_obj`、`proxy_str`、`https`）
- **注释/文档字符串**：源文件头部和行内注释通常使用中文（普通话）
- **单例模式**：使用自定义 `Singleton` 元类（`util/singleton.py`）结合 `six.withMetaclass` 实现

## 注意事项
- 运行测试前需先安装测试依赖：`pip install pytest pytest-cov fakeredis`
- 单元测试和 API 测试不依赖外部服务，可直接运行；集成测试需启动 Redis
