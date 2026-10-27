# 部署到托管环境

ProxyPool 不是一个纯前端网站，它包含 API、调度器和网关三个常驻进程，需要 Redis、持久磁盘和可访问的 TCP 端口。因此能不能部署，取决于托管平台是否支持这些能力。

## 能力对照

| 托管类型 | 可行性 | 说明 |
|----------|--------|------|
| VPS / 云服务器 / 自建 Docker 主机 | ✅ 推荐 | 完整支持 API、调度器、网关、Redis、SQLite、SSE |
| Fly.io / Railway / Render 等容器平台 | ⚠️ 可行 | 需要持久卷、Background Worker、原始 TCP 端口；不同平台限制不同 |
| Kubernetes / 云容器实例 | ⚠️ 可行 | 需要持久卷、托管 Redis、单独部署 worker；网关需要 TCP Service/LB |
| 传统虚拟主机 / 共享主机 / cPanel | ❌ 不可行 | 不能常驻 Python 进程，不能开放 TCP 代理端口 |
| Vercel / Netlify / Cloudflare Pages | ❌ 不可行 | 无状态 Serverless，无法运行调度器、网关和长期 SSE |
| Heroku 免费/普通 Dyno | ⚠️ 不推荐 | 文件系统临时、无原始 TCP 入口，网关无法公开使用 |

> 关键约束：**调度器必须常驻且只能运行一个实例**；**网关需要可访问的 TCP 端口**；**监控 SQLite 需要持久磁盘**。

## 推荐架构

```text
                    HTTPS / SSE
  Browser  ───────────────────────────►  Nginx / Caddy
                                              │
                                              ▼
                                         API :5010
                                              │
  Client ─── HTTP proxy :5011 ──────────►  Gateway
                                              │
                     Scheduler ───────────────┤
                                              ▼
                                      Redis  +  SQLite
```

- API：`python proxyPool.py server`，提供 `/get` 和 `/dashboard/`
- Scheduler：`python proxyPool.py schedule`，采集和校验代理，写入快照
- Gateway：`python proxyPool.py gateway`，提供稳定代理地址
- Redis：代理池存储
- SQLite：监控指标，放在持久卷 `data/`

## Docker Compose 部署

仓库提供生产编排文件：

```bash
cp .env.example .env
# 编辑 .env，修改 Redis、工作台、网关密码
docker compose -f docker-compose.prod.yml up -d --build

docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
```

启动后：

- 工作台：`http://服务器IP:5010/dashboard/`
- 网关：`http://服务器IP:5011`
- 网关认证：`.env` 中的 `GATEWAY_AUTH`

### `.env` 必填项

```dotenv
REDIS_PASSWORD=...
MONITOR_AUTH_USER=admin
MONITOR_AUTH_PASSWORD=...
GATEWAY_AUTH=proxyuser:...
```

生产编排会强制要求这三个密码，未设置时 Compose 会拒绝启动。

`API_PORT` 和 `GATEWAY_PORT` 同时控制容器内监听端口和宿主机端口映射，修改后执行 `docker compose -f docker-compose.prod.yml up -d` 即可生效。

> Redis 密码建议使用字母数字组合，避免 `@`、`:` 等 URL 特殊字符；如果必须使用，需要对 `DB_CONN` 中的密码做 URL 编码。

### 数据持久化

生产编排使用两个 Docker named volume：

- `redis_data`：Redis AOF
- `monitor_data`：`/app/data/monitor.db`

查看卷：

```bash
docker volume ls | grep proxy_pool
```

备份：

```bash
# Redis
docker exec proxy_pool_redis redis-cli -a "$REDIS_PASSWORD" BGSAVE

# SQLite（在监控数据目录所在容器执行）
docker exec proxy_pool_api python -c "import sqlite3; sqlite3.connect('/app/data/monitor.db').execute('VACUUM INTO \"/app/data/monitor-backup.db\"')"
```

## 反向代理 / HTTPS

示例配置见仓库中的 `deploy/nginx.conf`。工作台和 API 走普通 HTTP 反向代理；网关是 HTTP 正向代理，必须使用 TCP 透传（Nginx `stream` 或云厂商 TCP 负载均衡）。

SSE 关键配置：

```nginx
proxy_http_version 1.1;
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 3600s;
proxy_set_header Connection "";
```

如果不关闭缓冲，工作台会一直显示“轮询模式”或更新很慢。

网关 TCP 透传示例：

```nginx
stream {
    upstream proxy_pool_gateway {
        server 127.0.0.1:5011;
    }
    server {
        listen 5011;
        proxy_pass proxy_pool_gateway;
        proxy_timeout 3600s;
    }
}
```

如果托管平台不支持 `stream` 模块，直接暴露 5011，或使用云厂商的 TCP 负载均衡/端口转发。

## 常见托管平台说明

### Fly.io

- 使用 Dockerfile 部署。
- 为 API 和 scheduler 分别建 process group，或拆成两个 app。
- 给 `/app/data` 挂载 volume。
- 为 5011 配置 TCP service；API 使用 HTTP service。
- 多实例 scheduler 会重复采集，必须只保留一个 worker。

### Railway

- 使用 Dockerfile 部署。
- 添加 Redis 插件。
- 给 API/scheduler 添加持久卷，挂载到 `/app/data`。
- 为 5011 开启 TCP Proxy。
- scheduler 使用同一个镜像，启动命令 `python proxyPool.py schedule`。

### Render

- Web Service 部署 API，Persistent Disk 挂载到 `/app/data`。
- Background Worker 部署 `python proxyPool.py schedule`。
- 网关是否能公开取决于平台是否提供原始 TCP/端口转发；不提供时只能在内部/VPN 使用。

### Heroku

- 文件系统临时，SQLite 指标会丢失。
- 普通 Dyno 没有原始 TCP 入口，网关无法作为公共代理使用。
- 不建议部署完整项目。

### Vercel / Netlify / Cloudflare Pages

- 只能托管静态前端，不能运行 API、调度器、网关、Redis 和长期 SSE。
- 工作台前端可以静态托管，但后端仍需部署在常驻服务器上。

## 安全建议

- **必须修改** `MONITOR_AUTH_PASSWORD` 和 `GATEWAY_AUTH`。
- 网关不要无认证暴露到公网；开放代理容易被滥用并触发主机商投诉。
- 网关本身不终止 TLS，客户端到网关的代理认证信息是明文；请只在可信网络/VPN 使用，或在前面加支持 TLS 的 TCP 代理/防火墙白名单。
- 开启 HTTPS 后设置 `MONITOR_COOKIE_SECURE=true`。
- 用防火墙限制 5010/5011 的来源 IP；工作台可只允许办公网访问。
- 如果网关只供内部服务使用，放到内网或 VPN，不要公网暴露。
- 在反向代理层增加请求频率限制。
- 注意免费代理采集和转发可能违反主机商 AUP，请确认使用场景。

## 扩展与限制

- **SSE** 每个连接占用一个 WSGI worker；默认 gunicorn 4 个 worker，适合少量工作台连接。大量并发时使用 gevent/eventlet worker 或单独部署工作台。
- **SQLite** 适合同一台主机/同一个 Docker 卷上的多进程共享；不要把 `data/` 放在 NFS 等网络文件系统上。
- **调度器只能一个实例**，否则会重复采集和校验。
- **网关水平扩展** 需要 TCP 负载均衡，并且多个 gateway 共享 Redis 和 SQLite 指标文件。
- 免费代理在机房 IP 上质量通常较低，这是代理源本身的限制，不是部署问题。

## 故障排查

```bash
# 查看服务状态
docker compose -f docker-compose.prod.yml ps

# API 日志
docker compose -f docker-compose.prod.yml logs -f api

# 调度器日志
docker compose -f docker-compose.prod.yml logs -f scheduler

# 网关日志
docker compose -f docker-compose.prod.yml logs -f gateway

# 测试 API
curl http://127.0.0.1:5010/count/

# 测试工作台
curl -I http://127.0.0.1:5010/dashboard/

# 测试网关（需 GATEWAY_AUTH）
curl -x http://proxyuser:password@127.0.0.1:5011 http://httpbin.org/ip
```

如果工作台一直显示“轮询模式”，检查反向代理是否关闭了 SSE 缓冲；如果实时连接正常，状态显示“实时推送”。
