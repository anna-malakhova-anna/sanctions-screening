import "./StatTile.css";

type Tone = "good" | "warning" | "critical" | "neutral";

export function StatTile({
  label,
  value,
  tone = "neutral",
  hint,
}: {
  label: string;
  value: string;
  tone?: Tone;
  hint: string;
}) {
  return (
    <div className={`stat-tile stat-tile--${tone}`} title={hint}>
      <div className="stat-tile__value tabular">{value}</div>
      <div className="stat-tile__label">{label}</div>
    </div>
  );
}
