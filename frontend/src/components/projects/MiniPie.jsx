// ==================== Mini Pie Chart SVG ====================
export const MiniPie = ({ percent, size = 28 }) => {
  const r = (size - 4) / 2;
  const c = size / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (percent / 100) * circumference;
  const color = percent >= 100 ? '#10b981' : percent >= 50 ? '#3b82f6' : percent > 0 ? '#f59e0b' : '#e2e8f0';
  return (
    <svg width={size} height={size} className="shrink-0">
      <circle cx={c} cy={c} r={r} fill="none" stroke="#e2e8f0" strokeWidth={3} />
      <circle cx={c} cy={c} r={r} fill="none" stroke={color} strokeWidth={3}
        strokeDasharray={circumference} strokeDashoffset={offset}
        strokeLinecap="round" transform={`rotate(-90 ${c} ${c})`} />
      <text x={c} y={c} textAnchor="middle" dominantBaseline="central" fontSize={8} fontWeight="bold" fill={color}>
        {percent}%
      </text>
    </svg>
  );
};
