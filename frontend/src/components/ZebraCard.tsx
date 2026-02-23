import { RefreshCw, Pencil, Trash2, Tag, ExternalLink } from "lucide-react";
import type { Printer } from "../client";

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
    return <span className="inline-flex items-center gap-1 text-xs text-gray-400"><span className="h-2 w-2 rounded-full bg-gray-300" />Не проверен</span>;
  }
  if (printer.is_online) {
    return <span className="inline-flex items-center gap-1 text-xs text-emerald-600"><span className="h-2 w-2 rounded-full bg-emerald-500" />Онлайн</span>;
  }
  return <span className="inline-flex items-center gap-1 text-xs text-red-500"><span className="h-2 w-2 rounded-full bg-red-500" />Оффлайн</span>;
}

export default function ZebraCard({ printer, onPoll, onEdit, onDelete, isPolling, isSuperuser }: Props) {
  const polledAt = printer.last_polled_at
    ? new Date(printer.last_polled_at).toLocaleString("ru-RU", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })
    : null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition p-5 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-amber-50 p-2">
            <Tag className="h-5 w-5 text-amber-600" />
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

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-100">
        <span className="text-[11px] text-gray-400">
          {polledAt ? `Проверено: ${polledAt}` : "Ещё не проверялся"}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onPoll(printer.id)}
            disabled={isPolling}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-blue-600 transition disabled:opacity-40"
            title="Проверить"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isPolling ? "animate-spin" : ""}`} />
          </button>
          <a
            href={`http://${printer.ip_address}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-blue-600 transition"
            title="Веб-панель"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
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
