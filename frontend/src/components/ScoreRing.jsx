// Animated circular score indicator (0..1 -> percentage ring)
export default function ScoreRing({ value, size = 72, label }) {
  const pct = Math.round((value || 0) * 100);
  const r = (size - 10) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  const hue = pct >= 70 ? "url(#gradGood)" : pct >= 45 ? "url(#gradMid)" : "url(#gradLow)";

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <defs>
            <linearGradient id="gradGood" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#34d399" />
              <stop offset="100%" stopColor="#22d3ee" />
            </linearGradient>
            <linearGradient id="gradMid" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#818cf8" />
              <stop offset="100%" stopColor="#e879f9" />
            </linearGradient>
            <linearGradient id="gradLow" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#fb7185" />
              <stop offset="100%" stopColor="#f59e0b" />
            </linearGradient>
          </defs>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(148,163,184,0.25)" strokeWidth="6" />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={hue}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 0.9s cubic-bezier(0.22, 1, 0.36, 1)" }}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-white">
          {pct}
        </span>
      </div>
      {label && <span className="text-[10px] uppercase tracking-wider text-slate-400">{label}</span>}
    </div>
  );
}
