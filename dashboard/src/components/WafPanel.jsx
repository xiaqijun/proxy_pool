function formatTime(ts) {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString([], {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function truncate(value, max = 42) {
  const text = String(value || "");
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

export default function WafPanel({ data, loading }) {
  const rules = data?.rules || data?.rules_24h || [];
  const recent = data?.recent || [];
  const maxCount = Math.max(...rules.map((item) => item.count), 1);

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>WAF 拦截</h2>
          <span className="panel-sub">最近 24 小时命中分布</span>
        </div>
        {loading ? <span className="live-dot muted">同步中</span> : null}
      </div>

      {rules.length === 0 ? (
        <div className="empty-block">暂无 WAF 命中记录</div>
      ) : (
        <div className="waf-bars">
          {rules.map((item) => (
            <div className="waf-bar-row" key={item.rule}>
              <span className="waf-rule">{item.rule}</span>
              <div className="waf-bar-track">
                <div
                  className="waf-bar-fill"
                  style={{ width: `${Math.max((item.count / maxCount) * 100, 6)}%` }}
                />
              </div>
              <span className="waf-count">
                {item.count}
                {item.blocked ? <em> / {item.blocked} 拦截</em> : null}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="subhead">
        <h3>最近事件</h3>
      </div>
      {recent.length === 0 ? (
        <div className="empty-block small">暂无事件</div>
      ) : (
        <div className="table-wrap waf-table-wrap">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>WAF</th>
                <th>分数</th>
                <th>目标</th>
                <th>代理</th>
                <th>结果</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((event, index) => (
                <tr key={`${event.ts}-${event.rule}-${index}`}>
                  <td className="muted small">{formatTime(event.ts)}</td>
                  <td>
                    <span className="badge badge-orange">{event.rule}</span>
                  </td>
                  <td>{event.score}</td>
                  <td className="mono small" title={event.target}>
                    {truncate(event.target)}
                  </td>
                  <td className="mono small">{event.proxy || "-"}</td>
                  <td>
                    {event.blocked ? (
                      <span className="badge badge-red">最终拦截</span>
                    ) : event.retried ? (
                      <span className="badge badge-blue">已重试</span>
                    ) : (
                      "-"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
