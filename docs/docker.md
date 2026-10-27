# Docker 部署

## 使用 Docker 镜像

拉取并运行 Docker 镜像：

```console
docker pull jhao104/proxy_pool:latest

docker run --env DB_CONN=redis://:password@ip:port/0 -p 5010:5010 -p 5011:5011 jhao104/proxy_pool:latest
```

`DB_CONN` 环境变量会覆盖 `setting.py` 中的数据库连接配置。

容器内会同时启动 API 服务（`5010`）和稳定代理网关（`5011`）。网关认证、更换方式等可通过环境变量覆盖：

```console
docker run \
  --env DB_CONN=redis://:password@ip:port/0 \
  --env GATEWAY_STRATEGY=weighted \
  --env GATEWAY_AUTH=user:password \
  --env WAF_DETECT_ENABLED=true \
  --env WAF_SCORE_THRESHOLD=2 \
  --env MONITOR_AUTH_PASSWORD=your-strong-password \
  -v $(pwd)/data:/app/data \
  -p 5010:5010 -p 5011:5011 \
  jhao104/proxy_pool:latest
```

监控工作台地址：`http://127.0.0.1:5010/dashboard/`。指标 SQLite 文件默认位于 `/app/data/monitor.db`，建议挂载 `data/` 目录持久化。

生产环境（API、调度器、网关、Redis 分离，带持久卷）请使用 `docker-compose.prod.yml`，完整说明见 [托管部署](deployment.md)。

## 使用 docker-compose

项目根目录下的 `docker-compose.yml` 定义了 ProxyPool 和 Redis 两个服务：

```yaml
version: '2'
services:
  proxy_pool:
    build: .
    container_name: proxy_pool
    ports:
      - "5010:5010"
      - "5011:5011"
    links:
      - proxy_redis
    volumes:
      - ./data:/app/data
    environment:
      DB_CONN: "redis://@proxy_redis:6379/0"
      PROXY_STRATEGY: "random"
      GATEWAY_STRATEGY: "random"
      # GATEWAY_AUTH: "user:password"
      MONITOR_AUTH_USER: "admin"
      MONITOR_AUTH_PASSWORD: "change-me"
      MONITOR_DB_PATH: "data/monitor.db"
  proxy_redis:
    image: "redis"
    container_name: proxy_redis
```

启动：

```console
docker-compose up -d
```

## 容器环境注意事项

在 Docker 容器中，建议使用前台模式启动服务：

```console
./proxy_pool.sh start --fg
```

Dockerfile 中的 ENTRYPOINT 配置：

```dockerfile
ENTRYPOINT ["tini", "--", "bash", "proxy_pool.sh", "start", "--fg"]
```