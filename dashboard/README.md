# ProxyPool 监控工作台前端

React + Vite 独立前端，构建产物输出到 `../monitor/static`，由 Flask 在 `/dashboard/` 下提供。

## 开发

```bash
cd dashboard
npm install
npm run dev
```

开发服务器默认 `http://127.0.0.1:5173`，`/dashboard/api` 会代理到 `http://127.0.0.1:5010`。

## 构建

```bash
cd dashboard
npm install
npm run build
```

构建后启动/重启 `python proxyPool.py server`，访问：

```text
http://127.0.0.1:5010/dashboard/
```

默认账号 `admin`，密码由 `MONITOR_AUTH_PASSWORD` 配置（默认 `change-me`，请务必修改）。
