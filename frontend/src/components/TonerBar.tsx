interface TonerBarProps {
  label: string;
  level: number | null;
  color: string;
  bgColor: string;
}

export default function TonerBar({ label, level, color, bgColor }: TonerBarProps) {
  const pct = level ?? 0;
  const isUnknown = level === null;

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-7 text-gray-500 font-medium shrink-0">{label}</span>
      <div className={`flex-1 h-3 rounded-full ${bgColor} overflow-hidden`}>
        {!isUnknown && (
          <div
            className={`h-full rounded-full transition-all duration-500 ${color}`}
            style={{ width: `${pct}%` }}
          />
        )}
        {isUnknown && (
          <div className="h-full w-full bg-gray-300 flex items-center justify-center">
            <span className="text-[9px] text-gray-500">?</span>
          </div>
        )}
      </div>
      <span className="w-8 text-right tabular-nums text-gray-600 shrink-0">
        {isUnknown ? "—" : `${pct}%`}
      </span>
    </div>
  );
}
