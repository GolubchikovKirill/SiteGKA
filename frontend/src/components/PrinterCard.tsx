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
  showLowTonerDetails?: boolean;
  tonerPredictionDays?: Partial<Record<"black" | "cyan" | "magenta" | "yellow", number | null>>;
  offlineRiskLevel?: "low" | "medium" | "high" | string | null;
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

export default function PrinterCard({
  printer,
  onPoll,
  onEdit,
  onDelete,
  isPolling,
  isSuperuser,
  showLowTonerDetails = false,
  tonerPredictionDays,
  offlineRiskLevel,
}: Props) {
  const polledAt = printer.last_polled_at
    ? new Date(printer.last_polled_at).toLocaleString("ru-RU", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })
    : null;
  const lowTonerItems = [
    { key: "K", level: printer.toner_black, name: printer.toner_black_name },
    { key: "C", level: printer.toner_cyan, name: printer.toner_cyan_name },
    { key: "M", level: printer.toner_magenta, name: printer.toner_magenta_name },
    { key: "Y", level: printer.toner_yellow, name: printer.toner_yellow_name },
  ].filter((item) => item.level !== null && item.level <= 15);

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
          <div className="flex flex-col items-end gap-1">
            {statusBadge(printer)}
            {offlineRiskLevel && (
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${
                  offlineRiskLevel === "high"
                    ? "bg-red-100 text-red-700"
                    : offlineRiskLevel === "medium"
                      ? "bg-amber-100 text-amber-700"
                      : "bg-emerald-100 text-emerald-700"
                }`}
              >
                Риск: {offlineRiskLevel}
              </span>
            )}
          </div>
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
          <TonerBar label={printer.toner_black_name ? `K (${printer.toner_black_name})` : "K"} level={printer.toner_black} color="bg-gray-800" bgColor="bg-gray-100" />
          <TonerBar label={printer.toner_cyan_name ? `C (${printer.toner_cyan_name})` : "C"} level={printer.toner_cyan} color="bg-cyan-500" bgColor="bg-cyan-50" />
          <TonerBar label={printer.toner_magenta_name ? `M (${printer.toner_magenta_name})` : "M"} level={printer.toner_magenta} color="bg-pink-500" bgColor="bg-pink-50" />
          <TonerBar label={printer.toner_yellow_name ? `Y (${printer.toner_yellow_name})` : "Y"} level={printer.toner_yellow} color="bg-yellow-400" bgColor="bg-yellow-50" />
        </div>
        {tonerPredictionDays && Object.keys(tonerPredictionDays).length > 0 && (
          <div className="text-[11px] text-gray-500">
            ML прогноз:{" "}
            {(["black", "cyan", "magenta", "yellow"] as const)
              .filter((c) => tonerPredictionDays[c] != null)
              .map((c) => `${c[0].toUpperCase()}: ${Math.max(Math.round(tonerPredictionDays[c] || 0), 0)} дн.`)
              .join(" · ")}
          </div>
        )}
        {showLowTonerDetails && lowTonerItems.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            <div className="font-medium mb-1">К замене:</div>
            <div className="space-y-0.5">
              {lowTonerItems.map((item) => (
                <div key={item.key}>
                  {item.key}: {item.name || "модель не указана"} ({item.level}%)
                  {tonerPredictionDays?.[item.key === "K" ? "black" : item.key === "C" ? "cyan" : item.key === "M" ? "magenta" : "yellow"] != null && (
                    <span className="ml-1 text-[11px] text-amber-900/80">
                      ~{Math.max(Math.round(tonerPredictionDays[item.key === "K" ? "black" : item.key === "C" ? "cyan" : item.key === "M" ? "magenta" : "yellow"] || 0), 0)} дн.
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

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
