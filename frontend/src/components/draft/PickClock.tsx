interface Props {
  seconds: number;
  total: number;
  active: boolean;
}

export function PickClock({ seconds, total, active }: Props) {
  if (!active) return null;

  const pct = seconds / total;
  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference * (1 - pct);

  const color = seconds > total * 0.4 ? '#22c55e' : seconds > total * 0.2 ? '#f59e0b' : '#ef4444';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <svg width={44} height={44} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={22} cy={22} r={radius} fill="none" stroke="var(--border)" strokeWidth={3} />
        <circle
          cx={22} cy={22} r={radius} fill="none"
          stroke={color} strokeWidth={3}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s linear' }}
        />
      </svg>
      <span style={{ fontSize: 20, fontWeight: 700, color, minWidth: 32 }}>{seconds}s</span>
    </div>
  );
}
