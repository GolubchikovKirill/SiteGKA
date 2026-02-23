interface TonerBarProps {
  label: string;
  level: number | null;
  color: string;
  bgColor: string;
}

export default function TonerBar({ label, level, color, bgColor }: TonerBarProps) {
  const isNeverPolled = level === null;
  const isSomeRemaining = level === -3;
  const isUnknown = level === -2;
  const isSpecial = isNeverPolled || isSomeRemaining || isUnknown;
  const pct = isSpecial ? 0 : level;

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-7 text-gray-500 font-medium shrink-0">{label}</span>
      <div className={`flex-1 h-3 rounded-full ${bgColor} overflow-hidden`}>
        {!isSpecial && (
          <div
            className={`h-full rounded-full transition-all duration-500 ${color}`}
            style={{ width: `${pct}%` }}
          />
        )}
        {isSomeRemaining && (
          <div className={`h-full w-[15%] rounded-full ${color} opacity-50`} />
        )}
        {(isUnknown || isNeverPolled) && (
          <div className="h-full w-full bg-gray-200 flex items-center justify-center">
            <span className="text-[9px] text-gray-400">?</span>
          </div>
        )}
      </div>
      <span className="w-14 text-right text-gray-500 shrink-0 truncate" title={isSomeRemaining ? "Есть тонер, точный уровень неизвестен" : isUnknown ? "Нет данных (неориг. чип)" : undefined}>
        {isNeverPolled ? "—" : isSomeRemaining ? "Есть" : isUnknown ? "Нет данных" : `${pct}%`}
      </span>
    </div>
  );
}
