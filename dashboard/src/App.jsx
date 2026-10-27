import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import ConfigPanel from "./components/ConfigPanel";
import Login from "./components/Login";
import ProxyTable from "./components/ProxyTable";
import StatCard from "./components/StatCard";
import TrendChart from "./components/TrendChart";
import WafPanel from "./components/WafPanel";

const DEFAULT_FILTERS = {
  q: "",
  https: "all",
  source: "",
  status: "all",
  sort: "proxy",
  order: "asc",
  page: 1,
  page_size: 20,
};

const EMPTY_PROXIES = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  sources: [],
  regions: [],
};

export default function App() {
  const [auth, setAuth] = useState({ loading: true, user: null });
  const [loginError, setLoginError] = useState("");
  const [overview, setOverview] = useState(null);
  const [trends, setTrends] = useState(null);
  const [wafData, setWafData] = useState(null);
  const [proxyData, setProxyData] = useState(EMPTY_PROXIES);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [live, setLive] = useState(true);
  const [sseConnected, setSseConnected] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [proxyLoading, setProxyLoading] = useState(false);
  const [strategyBusy, setStrategyBusy] = useState(false);
  const toastTimer = useRef(null);

  const notify = (message) => {
    setToast(message);
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(""), 3200);
  };

  const refreshOverview = async () => {
    try {
      const data = await api.overview();
      setOverview(data);
      setError("");
    } catch (err) {
      if (err.message !== "unauthorized") setError(err.message || "概览加载失败");
    }
  };

  const refreshTrends = async () => {
    try {
      setTrends(await api.trends(24));
    } catch (err) {
      if (err.message !== "unauthorized") setError(err.message || "趋势加载失败");
    }
  };

  const refreshWaf = async () => {
    try {
      setWafData(await api.waf(24));
    } catch (err) {
      if (err.message !== "unauthorized") setError(err.message || "WAF 数据加载失败");
    }
  };

  const refreshProxies = async (nextFilters = filters) => {
    setProxyLoading(true);
    try {
      const data = await api.proxies(nextFilters);
      setProxyData(data);
    } catch (err) {
      if (err.message !== "unauthorized") setError(err.message || "代理列表加载失败");
    } finally {
      setProxyLoading(false);
    }
  };

  const refreshAll = async () => {
    await Promise.allSettled([
      refreshOverview(),
      refreshTrends(),
      refreshWaf(),
      refreshProxies(filters),
    ]);
  };

  useEffect(() => {
    const onUnauthorized = () => setAuth({ loading: false, user: null });
    window.addEventListener("monitor:unauthorized", onUnauthorized);
    api
      .session()
      .then((data) => setAuth({ loading: false, user: data.user }))
      .catch(() => setAuth({ loading: false, user: null }));
    return () => window.removeEventListener("monitor:unauthorized", onUnauthorized);
  }, []);

  useEffect(() => {
    if (!auth.user) return;
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.user]);

  useEffect(() => {
    if (!auth.user) return;
    const timer = window.setTimeout(() => refreshProxies(filters), 260);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, auth.user]);

  const refreshSeconds = Math.max(
    Number(overview?.config?.monitor?.refresh_seconds || 5),
    2
  );

  useEffect(() => {
    if (!auth.user || !live || sseConnected) return;
    const overviewTimer = window.setInterval(() => {
      refreshOverview();
    }, refreshSeconds * 1000);
    const slowTimer = window.setInterval(() => {
      refreshTrends();
      refreshWaf();
    }, 30000);
    return () => {
      window.clearInterval(overviewTimer);
      window.clearInterval(slowTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.user, live, sseConnected, refreshSeconds]);

  useEffect(() => {
    if (!auth.user || !live) {
      setSseConnected(false);
      return;
    }
    if (typeof window.EventSource === "undefined") {
      setSseConnected(false);
      return;
    }

    const source = new EventSource("/dashboard/api/stream");
    let closed = false;
    const parse = (event) => {
      try {
        return JSON.parse(event.data);
      } catch {
        return null;
      }
    };

    source.onopen = () => {
      if (!closed) setSseConnected(true);
    };
    source.onerror = () => {
      if (!closed) setSseConnected(false);
    };

    source.addEventListener("pool", (event) => {
      const data = parse(event);
      if (!data) return;
      setOverview((previous) => ({
        ...(previous || {}),
        pool: data.pool,
        strategy: data.strategy,
        config: data.config,
        generated_at: data.generated_at,
      }));
    });

    source.addEventListener("gateway", (event) => {
      const data = parse(event);
      if (!data) return;
      setOverview((previous) => ({
        ...(previous || {}),
        gateway: data.gateway,
        generated_at: data.generated_at,
      }));
    });

    source.addEventListener("waf", (event) => {
      const data = parse(event);
      if (data) setWafData(data);
    });

    source.addEventListener("trends", (event) => {
      const data = parse(event);
      if (data) setTrends(data);
    });

    source.addEventListener("server-error", (event) => {
      const data = parse(event);
      setError(data?.src || "实时数据推送异常");
    });

    return () => {
      closed = true;
      source.close();
      setSseConnected(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.user, live]);

  useEffect(() => {
    if (!auth.user) return;
    const sessionTimer = window.setInterval(() => {
      api.session().catch(() => {});
    }, 60000);
    return () => window.clearInterval(sessionTimer);
  }, [auth.user]);

  const handleLogin = async (username, password) => {
    setLoginError("");
    try {
      const data = await api.login(username, password);
      setAuth({ loading: false, user: data.user });
    } catch (err) {
      setLoginError(err.message || "登录失败");
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch {
      // ignore
    }
    setAuth({ loading: false, user: null });
    setOverview(null);
    setTrends(null);
    setWafData(null);
    setProxyData(EMPTY_PROXIES);
    setFilters(DEFAULT_FILTERS);
  };

  const handleFilter = (patch) => {
    setFilters((previous) => ({ ...previous, ...patch }));
  };

  const handleDelete = async (proxy) => {
    if (!window.confirm(`确定从代理池删除 ${proxy}？`)) return;
    try {
      await api.deleteProxy(proxy);
      notify(`已删除 ${proxy}`);
      await Promise.allSettled([refreshProxies(filters), refreshOverview()]);
    } catch (err) {
      setError(err.message || "删除失败");
    }
  };

  const handleStrategy = async (strategy) => {
    setStrategyBusy(true);
    try {
      const result = await api.setStrategy(strategy);
      setOverview((previous) =>
        previous
          ? {
              ...previous,
              strategy: result.strategy,
              config: { ...previous.config, strategy: result.strategy },
            }
          : previous
      );
      notify(strategy ? `默认策略已切换为 ${strategy}` : "已恢复配置默认策略");
      await refreshOverview();
    } catch (err) {
      setError(err.message || "切换策略失败");
    } finally {
      setStrategyBusy(false);
    }
  };

  if (auth.loading) {
    return <div className="boot-screen">正在连接监控工作台...</div>;
  }

  if (!auth.user) {
    return <Login onLogin={handleLogin} error={loginError} />;
  }

  const pool = overview?.pool || {};
  const gateway = overview?.gateway || {};
  const strategy = overview?.strategy || {};
  const config = overview?.config || {};

  const proxySeries = [
    {
      name: "总数",
      color: "#60a5fa",
      points: (trends?.proxy || []).map((point) => ({ x: point.ts, y: point.total })),
    },
    {
      name: "HTTP",
      color: "#34d399",
      points: (trends?.proxy || []).map((point) => ({ x: point.ts, y: point.http })),
    },
    {
      name: "HTTPS",
      color: "#c084fc",
      points: (trends?.proxy || []).map((point) => ({ x: point.ts, y: point.https })),
    },
  ];

  const gatewaySeries = [
    {
      name: "请求",
      color: "#60a5fa",
      points: (trends?.gateway || []).map((point) => ({ x: point.ts, y: point.requests })),
    },
    {
      name: "成功",
      color: "#34d399",
      points: (trends?.gateway || []).map((point) => ({ x: point.ts, y: point.success })),
    },
    {
      name: "WAF",
      color: "#fb923c",
      points: (trends?.gateway || []).map((point) => ({ x: point.ts, y: point.waf_detected })),
    },
    {
      name: "错误",
      color: "#f87171",
      points: (trends?.gateway || []).map((point) => ({ x: point.ts, y: point.errors })),
    },
  ];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-dot" />
          <div>
            <div className="brand-title">ProxyPool</div>
            <div className="brand-sub">监控工作台</div>
          </div>
        </div>

        <div className="topbar-actions">
          <span className={`live-pill ${live ? "on" : ""}`}>
            <i />
            {!live ? "已暂停" : sseConnected ? "实时推送" : "轮询模式"}
          </span>
          <button className="btn tiny" onClick={() => setLive((value) => !value)}>
            {live ? "暂停" : "继续"}
          </button>
          <button className="btn tiny" onClick={refreshAll}>
            手动刷新
          </button>
          <span className="muted small updated-at">
            {overview
              ? `更新于 ${new Date(overview.generated_at * 1000).toLocaleTimeString()}`
              : "等待数据"}
          </span>
          <span className="user-pill">{auth.user}</span>
          <button className="btn tiny" onClick={handleLogout}>
            退出
          </button>
        </div>
      </header>

      <main className="dashboard-main">
        {error ? (
          <div className="banner error-banner">
            <span>{error}</span>
            <button className="banner-close" onClick={() => setError("")} aria-label="关闭">
              ×
            </button>
          </div>
        ) : null}

        <section className="stat-grid">
          <StatCard label="代理总数" value={pool.total ?? "—"} hint={`健康 ${pool.healthy ?? 0} · 失败 ${pool.failing ?? 0}`} />
          <StatCard label="HTTP / HTTPS" value={`${pool.http ?? 0} / ${pool.https ?? 0}`} hint="当前池内协议分布" tone="green" />
          <StatCard label="平均失败次数" value={pool.avg_fail_count ?? "—"} hint={`平均校验 ${pool.avg_check_count ?? 0} 次`} tone="violet" />
          <StatCard label="网关请求（24h）" value={gateway.requests ?? 0} hint={`成功率 ${gateway.success_rate ?? 0}%`} tone="cyan" />
          <StatCard label="WAF 命中（24h）" value={gateway.waf_detected ?? 0} hint={`最终拦截 ${gateway.waf_blocked ?? 0}`} tone="orange" />
          <StatCard label="平均延迟" value={`${gateway.avg_latency_ms ?? 0} ms`} hint={`最大 ${gateway.latency_max ?? 0} ms`} tone="red" />
        </section>

        <section className="two-column">
          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>代理池趋势</h2>
                <span className="panel-sub">最近 24 小时 · 每分钟快照</span>
              </div>
            </div>
            <TrendChart
              series={proxySeries}
              emptyText="暂无快照，工作台运行一分钟后会生成趋势"
            />
          </div>

          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>网关请求趋势</h2>
                <span className="panel-sub">最近 24 小时 · 请求 / 成功 / WAF / 错误</span>
              </div>
            </div>
            <TrendChart
              series={gatewaySeries}
              emptyText="暂无网关请求，启动 gateway 并产生流量后显示"
            />
          </div>
        </section>

        <section className="two-column">
          <WafPanel data={wafData || overview?.waf} />
          <ConfigPanel
            config={config}
            strategy={strategy}
            onStrategy={handleStrategy}
            busy={strategyBusy}
          />
        </section>

        <ProxyTable
          data={proxyData}
          filters={filters}
          onFilter={handleFilter}
          onDelete={handleDelete}
          loading={proxyLoading}
        />
      </main>

      {toast ? <div className="toast">{toast}</div> : null}
    </div>
  );
}
