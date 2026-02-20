import { RefreshCw, Pencil, Trash2, Printer as PrinterIcon } from "lucide-react";
import type { Printer } from "../client";
import TonerBar from "./TonerBar";

interface Props {
  printer: Printer;
  onPoll: (id: string) => void;
  onEdit: (printer: Printer) => void;
  onDelete: (id: string) => void;
  isPolling: boolean;
  isSuperuser: boolean;
}

function statusBadge(printer: Printer) {
  if (printer.is_online === null) {
    return <span className="inline-flex items-center gap-1 text-xs text-gray-400"><span className="h-2 w-2 rounded-full bg-gray-300" />Не опрошен</span>;
  }
  if (printer.is_online) {
    const label = printer.status === "printing" ? "Печатает" : printer.status === "idle" ? "Готов" : printer.status === "warmup" ? "Прогрев" : "Онлайн";
    return <span className="inline-flex items-center gap-1 text-xs text-emerald-600"><span className="h-2 w-2 rounded-full bg-emerald-500" />{label}</span>;
  }
  return <span className="inline-flex items-center gap-1 text-xs text-red-500"><span className="h-2 w-2 rounded-full bg-red-500" />Оффлайн</span>;
}

export default function PrinterCard({ printer, onPoll, onEdit, onDelete, isPolling, isSuperuser }: Props) {
  const polledAt = printer.last_polled_at
    ? new Date(printer.last_polled_at).toLocaleString("ru-RU", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })
    : null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition p-5 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-blue-50 p-2">
            <PrinterIcon className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <div className="font-medium text-sm text-gray-900">{printer.model}</div>
            <div className="text-xs text-gray-500">{printer.store_name}</div>
          </div>
        </div>
        {statusBadge(printer)}
      </div>

      {/* IP */}
      <div className="text-xs text-gray-400 font-mono">{printer.ip_address}</div>

      {/* Toner levels */}
      <div className="space-y-1.5">
        <TonerBar label="K" level={printer.toner_black} color="bg-gray-800" bgColor="bg-gray-100" />
        <TonerBar label="C" level={printer.toner_cyan} color="bg-cyan-500" bgColor="bg-cyan-50" />
        <TonerBar label="M" level={printer.toner_magenta} color="bg-pink-500" bgColor="bg-pink-50" />
        <TonerBar label="Y" level={printer.toner_yellow} color="bg-yellow-400" bgColor="bg-yellow-50" />
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-100">
        <span className="text-[11px] text-gray-400">
          {polledAt ? `Обновлено: ${polledAt}` : "Ещё не опрашивался"}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onPoll(printer.id)}
            disabled={isPolling}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-blue-600 transition disabled:opacity-40"
            title="Опросить"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isPolling ? "animate-spin" : ""}`} />
          </button>
          {isSuperuser && (
            <>
              <button
                onClick={() => onEdit(printer)}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-amber-600 transition"
                title="Редактировать"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => onDelete(printer.id)}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-red-600 transition"
                title="Удалить"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
