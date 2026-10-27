import { useEffect, useState } from "react";

function formatBytes(value) {
  const number = Number(value || 0);
  if (number >= 1024 * 1024) return `${(number / 1024 / 1024).toFixed(1)} MB`;
  if (number >= 1024) return `${(number / 1024).toFixed(0)} KB`;
  return `${number} B`;
}

export default function ConfigPanel({ config, strategy, onStrategy, busy }) {
  const [selected, setSelected] = useState("");

  useEffect(() => {
    setSelected(strategy?.effective || "");
  }, [strategy?.effective]);

  const gateway = config?.gateway || {};
  const waf = config?.waf || {};
  const monitor = config?.monitor || {};
  const supported = strategy?.supported || [];

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>策略与配置</h2>
          <span className="panel-sub">运行时策略覆盖会同步到 API 和网关</span>
        </div>
      </div>

      <div className="strategy-box">
        <div className="strategy-current">
          <span className="muted small">当前生效</span>
          <strong>{strategy?.effective || "-"}</strong>
          <span className="muted small">
            配置默认：{strategy?.config_default || "-"}
            {strategy?.override ? " · 已覆盖" : ""}
          </span>
        </div>
        <div className="strategy-controls">
          <select value={selected} onChange={(event) => setSelected(event.target.value)}>
            {supported.map((item) => (
              <option key={item.name} value={item.name}>
                {item.name} · {item.description}
              </option>
            ))}
          </select>
          <button
            className="btn primary"
            disabled={!selected || busy || selected === strategy?.effective}
            onClick={() => onStrategy(selected)}
          >
            应用
          </button>
          <button
            className="btn"
            disabled={!strategy?.override || busy}
            onClick={() => onStrategy(null)}
          >
            恢复默认
          </button>
        </div>
      </div>

      <div className="config-grid">
        <div>
          <span>版本</span>
          <strong>{config?.version || "-"}</strong>
        </div>
        <div>
          <span>网关地址</span>
          <strong className="mono">{gateway.address || "-"}</strong>
        </div>
        <div>
          <span>网关重试</span>
          <strong>{gateway.retry ?? "-"} 次</strong>
        </div>
        <div>
          <span>连接超时</span>
          <strong>{gateway.connect_timeout ?? "-"} s</strong>
        </div>
        <div>
          <span>WAF 检测</span>
          <strong>{waf.enabled ? "开启" : "关闭"}</strong>
        </div>
        <div>
          <span>WAF 阈值</span>
          <strong>{waf.score_threshold ?? "-"}</strong>
        </div>
        <div>
          <span>请求体重放上限</span>
          <strong>{formatBytes(waf.max_replay_body)}</strong>
        </div>
        <div>
          <span>指标保留</span>
          <strong>{monitor.retention_days ?? "-"} 天</strong>
        </div>
        <div>
          <span>刷新间隔</span>
          <strong>{monitor.refresh_seconds ?? "-"} s</strong>
        </div>
        <div>
          <span>WAF 自定义规则</span>
          <strong>
            {(waf.custom_headers || 0) +
              (waf.custom_keywords || 0) +
              (waf.custom_status?.length || 0)}{" "}
            条
          </strong>
        </div>
      </div>
    </section>
  );
}
