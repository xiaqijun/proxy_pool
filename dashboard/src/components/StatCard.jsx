const TONES = ["blue", "green", "violet", "orange", "red", "cyan"];

export default function StatCard({ label, value, hint, tone = "blue" }) {
  const toneClass = TONES.includes(tone) ? tone : "blue";
  return (
    <div className={`stat-card tone-${toneClass}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint ? <div className="stat-hint">{hint}</div> : null}
    </div>
  );
}
