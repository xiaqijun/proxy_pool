# 项目结构

ProxyPool 项目目录结构如下：

```
proxy_pool/
├── api/                    # API 服务
│   └── proxyApi.py         #   Flask RESTful 接口
├── gateway/                # 稳定代理网关
│   └── proxyGateway.py     #   基于 asyncio 的 HTTP/HTTPS 转发
├── monitor/                # 监控工作台
│   ├── monitorApi.py       #   登录、概览、代理列表、趋势、WAF、策略接口
│   ├── monitorStore.py     #   SQLite 指标存储
│   └── static/             #   React 构建产物（Flask 直接提供）
├── dashboard/              # React + Vite 前端源码
│   ├── src/                #   页面与组件
│   └── vite.config.js      #   构建输出到 monitor/static
├── db/                     # 数据库层
│   ├── dbClient.py         #   抽象数据库接口
│   ├── redisClient.py      #   Redis 实现
│   └── ssdbClient.py       #   SSDB 实现
├── fetcher/                # 代理采集器
│   ├── baseFetcher.py      #   BaseFetcher 基类（共享解析方法）
│   └── sources/            #   各代理源独立文件
│       ├── proxyspace.py   #     Proxyspace（按国家 txt）
│       ├── proxyhub.py     #     Proxyhub
│       ├── kuaidaili.py    #     快代理
│       ├── geonode.py      #     Geonode
│       └── ...             #     其他代理源
├── handler/                # 业务处理器
│   ├── configHandler.py    #   配置读取
│   ├── logHandler.py       #   日志处理
│   └── proxyHandler.py     #   代理 CRUD 逻辑
├── helper/                 # 核心辅助模块
│   ├── scheduler.py        #   APScheduler 定时调度
│   ├── validator.py        #   代理可用性校验
│   ├── proxy.py            #   代理数据模型
│   ├── strategy.py         #   代理更换策略（随机/轮询/加权）
│   ├── waf.py              #   WAF 响应指纹检测
│   ├── launcher.py         #   API、网关、调度器启动入口
│   ├── fetch.py            #   采集任务执行
│   └── check.py            #   校验任务执行
├── util/                   # 工具库
│   ├── singleton.py        #   单例元类
│   ├── lazyProperty.py     #   惰性属性装饰器
│   ├── six.py              #   Python 2/3 兼容层
│   └── webRequest.py       #   HTTP 请求封装
├── tests/                  # 测试
│   ├── conftest.py         #   共享 fixtures
│   ├── unit/               #   单元测试（零外部依赖）
│   ├── api/                #   API 路由测试（Flask test client）
│   └── integration/        #   集成测试（RedisClient/SsdbClient CRUD）
├── docs/                   # MkDocs 文档源文件
├── proxyPool.py            # CLI 入口（click）
├── proxy_pool.sh           # 服务管理脚本
├── setting.py              # 全局配置文件
├── requirements.txt        # Python 依赖
├── requirements-test.txt   # 测试依赖（pytest、pytest-cov、fakeredis）
├── pyproject.toml          # pytest 配置
├── Dockerfile              # Docker 镜像构建
├── docker-compose.yml      # Docker Compose 编排
└── tox.ini                 # 多版本测试配置
```

## 核心模块说明

### `proxyPool.py` — 入口

基于 click 的命令行入口，提供 `schedule`、`server`、`gateway`、`all`、`fetcher` 五个子命令。`schedule` 启动代理采集和验证调度器，`server` 启动 Flask API 服务，`gateway` 启动稳定代理网关，`all` 同时启动 API 和网关，`fetcher` 查看当前启用的代理源列表。

### `api/proxyApi.py` — API 服务

Flask 应用，提供 `/get`、`/pop`、`/all`、`/count`、`/delete` 等接口，运行在 `setting.py` 配置的 `HOST:PORT`（默认 `0.0.0.0:5010`）。`/get` 支持通过 `strategy` 参数选择 `random`、`round_robin`、`weighted` 三种代理更换方式。

### `gateway/` — 稳定代理网关

基于 asyncio 的 HTTP 代理网关，客户端把 `GATEWAY_HOST:GATEWAY_PORT`（默认 `0.0.0.0:5011`）配置为 HTTP 代理后，网关会按策略为每个请求选择上游代理，支持普通 HTTP 转发和 HTTPS CONNECT 隧道。普通 HTTP 响应会经过 `helper/waf.py` 做 WAF 指纹检测，命中后自动切换代理重试。

### `monitor/` + `dashboard/` — 监控工作台

`monitor/monitorStore.py` 使用 SQLite 存储代理池快照、网关指标、WAF 事件和运行时策略；`monitor/monitorApi.py` 提供 `/dashboard/` 页面和 `/dashboard/api/*` 接口，强制登录。`dashboard/` 是独立的 React + Vite 前端，构建产物输出到 `monitor/static/`，由 Flask 直接提供。

工作台功能包括代理池概览与趋势、代理列表筛选/分页/删除、网关与 WAF 统计、实时刷新和在线策略切换。调度器每分钟记录一次代理池快照。

### `db/` — 数据库层

通过 `dbClient.py` 定义统一接口，`redisClient.py` 和 `ssdbClient.py` 分别实现 Redis 和 SSDB 的存取逻辑。使用 `setting.py` 中的 `DB_CONN` 连接字符串选择后端。

### `fetcher/` — 代理采集

采用插件架构。`baseFetcher.py` 定义 `BaseFetcher` 基类，提供共享解析方法和 `name`/`url`/`enabled` 属性约定。每个代理源在 `sources/` 目录下独立一个文件，继承 `BaseFetcher` 并实现 `fetch()` 方法。调度器自动扫描 `sources/` 目录，加载 `enabled=True` 的源。通过 `setting.py` 的 `PROXY_FETCHER_EXCLUDE` 黑名单可临时禁用指定源。

### `helper/scheduler.py` — 定时调度

基于 APScheduler，按配置间隔驱动采集器和验证器运行，自动维护代理池数量。

### `helper/validator.py` — 代理校验

使用 `HTTP_URL` 和 `HTTPS_URL` 测试代理可用性，超过 `MAX_FAIL_COUNT` 次失败的代理会被移除。

### `handler/` — 业务处理

- `configHandler.py`：封装 `setting.py` 配置项的读取
- `logHandler.py`：统一日志配置
- `proxyHandler.py`：代理的增删改查操作

### `setting.py` — 配置中心

所有运行时配置集中在此文件，包括 API 地址、数据库连接、采集器列表、校验参数等。详见 [配置参考](configuration.md)。
