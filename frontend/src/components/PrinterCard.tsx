import { RefreshCw, Pencil, Trash2, ExternalLink, Printer as PrinterIcon, ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";
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
    return <span className="inline-flex items-center gap-1 text-xs text-emerald-600"><span className="h-2 w-2 rounded-full bg-emerald-500" />Онлайн</span>;
  }
  return <span className="inline-flex items-center gap-1 text-xs text-red-500"><span className="h-2 w-2 rounded-full bg-red-500" />Оффлайн</span>;
}

function MacStatus({ printer }: { printer: Printer }) {
  if (!printer.mac_status || printer.mac_status === "unavailable") {
    if (!printer.mac_address) return null;
    return (
      <div className="flex items-center gap-1.5 text-[11px] text-gray-400">
        <ShieldQuestion className="h-3 w-3" />
        <span className="font-mono">{printer.mac_address}</span>
        <span>— не проверен</span>
      </div>
    );
  }

  if (printer.mac_status === "verified") {
    return (
      <div className="flex items-center gap-1.5 text-[11px] text-emerald-600">
        <ShieldCheck className="h-3 w-3" />
        <span className="font-mono">{printer.mac_address}</span>
        <span>— подтверждён</span>
      </div>
    );
  }

  if (printer.mac_status === "mismatch") {
    return (
      <div className="flex items-center gap-1.5 text-[11px] text-red-600 font-medium">
        <ShieldAlert className="h-3 w-3" />
        <span className="font-mono">{printer.mac_address}</span>
        <span>— MAC не совпадает! Возможна смена устройства</span>
      </div>
    );
  }

  return null;
}

export default function PrinterCard({ printer, onPoll, onEdit, onDelete, isPolling, isSuperuser }: Props) {
  const polledAt = printer.last_polled_at
    ? new Date(printer.last_polled_at).toLocaleString("ru-RU", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })
    : null;

  return (
    <div className="app-panel app-card rounded-xl border shadow-sm hover:shadow-md transition flex flex-col">
      <div className="p-5 flex flex-col gap-4">
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

        {/* IP + MAC */}
        {printer.ip_address && (
          <div className="text-xs text-gray-400 font-mono">{printer.ip_address}</div>
        )}
        {printer.host_pc && (
          <div className="text-xs text-gray-500">
            <span className="text-gray-400">Hostname:</span> {printer.host_pc}
          </div>
        )}

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
            {printer.ip_address && (
              <a
                href={`http://${printer.ip_address}`}
                target="_blank"
                rel="noopener noreferrer"
                className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-blue-600 transition"
                title="Веб-панель"
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
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

      {/* MAC verification status — below the card */}
      {(printer.mac_address || printer.mac_status) && (
        <div className={`px-5 py-2 border-t rounded-b-xl ${
          printer.mac_status === "mismatch"
            ? "bg-red-50 border-red-200"
            : printer.mac_status === "verified"
            ? "bg-emerald-50 border-emerald-200"
            : "bg-gray-50 border-gray-200"
        }`}>
          <MacStatus printer={printer} />
        </div>
      )}
    </div>
  );
}
