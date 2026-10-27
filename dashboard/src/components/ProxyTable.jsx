const COLUMNS = [
  { key: "proxy", label: "代理地址" },
  { key: "https", label: "协议" },
  { key: "source", label: "来源" },
  { key: "region", label: "地区" },
  { key: "health", label: "健康度" },
  { key: "last_time", label: "最后校验" },
  { key: "actions", label: "" },
];

function statusText(item) {
  if (item.last_status === true) return "可用";
  if (item.last_status === false) return "失败";
  return "未校验";
}

export default function ProxyTable({ data, filters, onFilter, onDelete, loading }) {
  const items = data?.items || [];
  const total = data?.total || 0;
  const page = data?.page || filters.page || 1;
  const pageSize = data?.page_size || filters.page_size || 20;
  const totalPages = Math.max(Math.ceil(total / pageSize), 1);

  const update = (key, value) => {
    onFilter({ [key]: value, ...(key === "page" ? {} : { page: 1 }) });
  };

  return (
    <section className="panel proxy-panel">
      <div className="panel-head">
        <div>
          <h2>代理列表</h2>
          <span className="panel-sub">共 {total} 个代理</span>
        </div>
        <div className="proxy-filters">
          <input
            className="search-input"
            value={filters.q}
            onChange={(event) => update("q", event.target.value)}
            placeholder="搜索 IP / 来源 / 地区"
          />
          <select value={filters.https} onChange={(event) => update("https", event.target.value)}>
            <option value="all">全部协议</option>
            <option value="http">HTTP</option>
            <option value="https">HTTPS</option>
          </select>
          <select value={filters.source} onChange={(event) => update("source", event.target.value)}>
            <option value="">全部来源</option>
            {(data?.sources || []).map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
          <select value={filters.status} onChange={(event) => update("status", event.target.value)}>
            <option value="all">全部状态</option>
            <option value="healthy">健康</option>
            <option value="failing">有失败</option>
          </select>
          <select value={filters.sort} onChange={(event) => update("sort", event.target.value)}>
            <option value="proxy">按地址</option>
            <option value="fail_count">按失败次数</option>
            <option value="check_count">按校验次数</option>
            <option value="last_time">按校验时间</option>
          </select>
          <select value={filters.order} onChange={(event) => update("order", event.target.value)}>
            <option value="asc">升序</option>
            <option value="desc">降序</option>
          </select>
          <select
            value={pageSize}
            onChange={(event) => update("page_size", Number(event.target.value))}
          >
            {[10, 20, 50, 100].map((size) => (
              <option key={size} value={size}>
                {size} 条/页
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className={`table-wrap ${loading ? "is-loading" : ""}`}>
        <table>
          <thead>
            <tr>
              {COLUMNS.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={COLUMNS.length} className="empty-cell">
                  {loading ? "加载中..." : "没有匹配的代理"}
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.proxy}>
                  <td>
                    <span className="mono">{item.proxy}</span>
                  </td>
                  <td>
                    <span className={`badge ${item.https ? "badge-green" : "badge-blue"}`}>
                      {item.https ? "HTTPS" : "HTTP"}
                    </span>
                  </td>
                  <td>
                    <span className="muted">{item.source || "-"}</span>
                  </td>
                  <td>{item.region || "-"}</td>
                  <td>
                    <div className="health-cell">
                      <span className={`badge ${item.healthy ? "badge-green" : "badge-red"}`}>
                        {item.healthy ? "健康" : "有失败"}
                      </span>
                      <span className="muted small">
                        {item.fail_count}/{item.check_count}
                      </span>
                      <span className={`status-text status-${statusText(item)}`}>
                        {statusText(item)}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className="muted small">{item.last_time || "-"}</span>
                  </td>
                  <td>
                    <button
                      className="btn tiny danger"
                      onClick={() => onDelete(item.proxy)}
                      title="从代理池删除"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <span className="muted small">
          第 {page} / {totalPages} 页
        </span>
        <div className="pagination-actions">
          <button
            className="btn tiny"
            disabled={page <= 1}
            onClick={() => update("page", page - 1)}
          >
            上一页
          </button>
          <button
            className="btn tiny"
            disabled={page >= totalPages}
            onClick={() => update("page", page + 1)}
          >
            下一页
          </button>
        </div>
      </div>
    </section>
  );
}
