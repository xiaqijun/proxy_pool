const WIDTH = 760;
const HEIGHT = 210;
const PAD = { left: 42, right: 16, top: 16, bottom: 28 };

function formatTime(seconds) {
  const date = new Date(seconds * 1000);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function project(point, minX, maxX, maxY) {
  const chartWidth = WIDTH - PAD.left - PAD.right;
  const chartHeight = HEIGHT - PAD.top - PAD.bottom;
  return {
    x:
      PAD.left +
      (maxX === minX ? chartWidth / 2 : ((point.x - minX) / (maxX - minX)) * chartWidth),
    y: PAD.top + chartHeight - (point.y / maxY) * chartHeight,
  };
}

function buildPath(points, minX, maxX, maxY) {
  return points
    .map((point, index) => {
      const { x, y } = project(point, minX, maxX, maxY);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

export default function TrendChart({ series = [], emptyText = "暂无趋势数据" }) {
  const usable = series.filter((item) => item.points && item.points.length > 0);
  const all = usable.flatMap((item) => item.points);

  if (all.length === 0) {
    return <div className="chart-empty">{emptyText}</div>;
  }

  const xs = all.map((point) => point.x);
  const ys = all.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const maxY = Math.max(...ys, 1);
  const chartHeight = HEIGHT - PAD.top - PAD.bottom;

  return (
    <div className="trend-chart">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="趋势图">
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = PAD.top + chartHeight * ratio;
          const label = Math.round(maxY * (1 - ratio));
          return (
            <g key={ratio}>
              <line
                x1={PAD.left}
                y1={y}
                x2={WIDTH - PAD.right}
                y2={y}
                className="chart-grid"
              />
              <text x={PAD.left - 8} y={y + 4} className="chart-axis" textAnchor="end">
                {label}
              </text>
            </g>
          );
        })}

        {usable.map((item) => (
          <g key={item.name}>
            <path
              d={buildPath(item.points, minX, maxX, maxY)}
              fill="none"
              stroke={item.color}
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            {item.points.length === 1 ? (
              <circle
                cx={project(item.points[0], minX, maxX, maxY).x}
                cy={project(item.points[0], minX, maxX, maxY).y}
                r="3"
                fill={item.color}
              />
            ) : null}
          </g>
        ))}

        <text x={PAD.left} y={HEIGHT - 8} className="chart-axis" textAnchor="start">
          {formatTime(minX)}
        </text>
        <text
          x={WIDTH - PAD.right}
          y={HEIGHT - 8}
          className="chart-axis"
          textAnchor="end"
        >
          {formatTime(maxX)}
        </text>
      </svg>

      <div className="chart-legend">
        {usable.map((item) => (
          <span key={item.name} className="legend-item">
            <i style={{ backgroundColor: item.color }} />
            {item.name}
          </span>
        ))}
      </div>
    </div>
  );
}
