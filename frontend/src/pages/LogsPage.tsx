import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertOctagon, AlertTriangle, Download, Info, RefreshCw, Search, Siren } from "lucide-react";
import { getEventLogs, getNetSupportHelperDownloadUrl, type EventSeverity } from "../client";

const SEVERITIES: Array<{ key: EventSeverity | "all"; label: string }> = [
  { key: "all", label: "Все" },
  { key: "info", label: "Info" },
  { key: "warning", label: "Warning" },
  { key: "error", label: "Error" },
  { key: "critical", label: "Critical" },
];

const DEVICE_KINDS: Array<{ key: "all" | "printer" | "media_player" | "switch" | "cash_register"; label: string }> = [
  { key: "all", label: "Все устройства" },
  { key: "printer", label: "Принтеры" },
  { key: "media_player", label: "Медиаплееры" },
  { key: "switch", label: "Сетевое оборудование" },
  { key: "cash_register", label: "Кассы" },
];

function severityBadge(severity: EventSeverity) {
  if (severity === "critical") {
    return <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700"><Siren className="h-3 w-3" />critical</span>;
  }
  if (severity === "error") {
    return <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700"><AlertOctagon className="h-3 w-3" />error</span>;
  }
  if (severity === "warning") {
    return <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"><AlertTriangle className="h-3 w-3" />warning</span>;
  }
  return <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700"><Info className="h-3 w-3" />info</span>;
}

export default function LogsPage() {
  const [section, setSection] = useState<"events" | "nsm-helper">("events");
  const [severity, setSeverity] = useState<EventSeverity | "all">("all");
  const [deviceKind, setDeviceKind] = useState<"all" | "printer" | "media_player" | "switch" | "cash_register">("all");
  const [search, setSearch] = useState("");

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["event-logs", severity, deviceKind, search],
    queryFn: () => getEventLogs({ severity, device_kind: deviceKind, q: search || undefined, limit: 200 }),
    refetchInterval: 15_000,
  });

  const logs = data?.data ?? [];
  const total = data?.count ?? 0;
  const counts = useMemo(() => ({
    critical: logs.filter((l) => l.severity === "critical").length,
    errors: logs.filter((l) => l.severity === "error").length,
    warnings: logs.filter((l) => l.severity === "warning").length,
  }), [logs]);

  return (
    <div className="space-y-6">
      <div className="app-toolbar p-4 sm:p-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Настройки</h1>
          <p className="text-sm text-slate-500 mt-1">Логи событий и инструкции для NetSupport Helper</p>
        </div>
        <button
          onClick={() => refetch()}
          className="app-btn-secondary inline-flex items-center gap-2 px-4 py-2 text-sm"
          disabled={isFetching}
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          Обновить
        </button>
      </div>

      <div className="app-tabbar flex gap-1 p-1.5 w-fit max-w-full overflow-x-auto app-compact-scroll">
        <button
          onClick={() => setSection("events")}
          className={`app-tab inline-flex items-center gap-2 px-4 py-2 text-sm font-medium ${section === "events" ? "active" : "text-gray-500 hover:text-gray-700"}`}
        >
          Логи
        </button>
        <button
          onClick={() => setSection("nsm-helper")}
          className={`app-tab inline-flex items-center gap-2 px-4 py-2 text-sm font-medium ${section === "nsm-helper" ? "active" : "text-gray-500 hover:text-gray-700"}`}
        >
          NetSupport Helper
        </button>
      </div>

      {section === "nsm-helper" && (
        <div className="space-y-4">
          <div className="app-panel p-5 space-y-3">
            <h2 className="text-lg font-semibold text-slate-900">Установка на рабочий Windows ПК</h2>
            <ol className="list-decimal pl-5 space-y-2 text-sm text-gray-600">
              <li>Скачайте 3 скрипта ниже в одну папку на ПК оператора.</li>
              <li>Запустите PowerShell в этой папке от имени пользователя, который работает с InfraScope.</li>
              <li>Выполните: <code>powershell -ExecutionPolicy Bypass -File .\Install-InfraScopeNetSupportHelper.ps1</code></li>
              <li>Проверьте в <code>Win + R</code>: <code>infrascope-nsm://NETTOP-01</code></li>
              <li>Если не сработало: откройте лог <code>%TEMP%\infrascope-nsm.log</code>.</li>
              <li>После обновлений helper запускайте Install-скрипт повторно.</li>
            </ol>
          </div>

          <div className="app-panel p-5 space-y-3">
            <h3 className="text-base font-semibold text-slate-900">Скачать .ps1</h3>
            <div className="flex gap-2 flex-wrap">
              <a className="app-btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm" href={getNetSupportHelperDownloadUrl("Install-InfraScopeNetSupportHelper.ps1")}>
                <Download className="h-4 w-4" /> Install helper
              </a>
              <a className="app-btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm" href={getNetSupportHelperDownloadUrl("NetSupportUriHandler.ps1")}>
                <Download className="h-4 w-4" /> URI handler
              </a>
              <a className="app-btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm" href={getNetSupportHelperDownloadUrl("Uninstall-InfraScopeNetSupportHelper.ps1")}>
                <Download className="h-4 w-4" /> Uninstall helper
              </a>
            </div>
          </div>
        </div>
      )}

      {section === "events" && (
        <>

          <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
            <div className="app-stat bg-gray-100 px-4 py-3"><div className="text-2xl font-bold text-gray-900">{total}</div><div className="text-xs text-gray-500 mt-0.5">Всего</div></div>
            <div className="app-stat bg-red-50 px-4 py-3"><div className="text-2xl font-bold text-red-700">{counts.critical}</div><div className="text-xs text-gray-500 mt-0.5">Critical</div></div>
            <div className="app-stat bg-rose-50 px-4 py-3"><div className="text-2xl font-bold text-rose-700">{counts.errors}</div><div className="text-xs text-gray-500 mt-0.5">Error</div></div>
            <div className="app-stat bg-amber-50 px-4 py-3"><div className="text-2xl font-bold text-amber-700">{counts.warnings}</div><div className="text-xs text-gray-500 mt-0.5">Warning</div></div>
          </div>

          <div className="app-panel p-4 flex flex-col gap-3">
            <div className="relative max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="app-input w-full pl-10 pr-4 py-2 text-sm"
                placeholder="Поиск по событию, имени или IP..."
              />
            </div>
            <div className="flex gap-2 flex-wrap">
              {SEVERITIES.map((item) => (
                <button
                  key={item.key}
                  onClick={() => setSeverity(item.key)}
                  className={`app-btn-secondary px-3 py-1.5 text-xs ${severity === item.key ? "ring-2 ring-rose-400/50" : ""}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <div className="flex gap-2 flex-wrap">
              {DEVICE_KINDS.map((item) => (
                <button
                  key={item.key}
                  onClick={() => setDeviceKind(item.key)}
                  className={`app-btn-secondary px-3 py-1.5 text-xs ${deviceKind === item.key ? "ring-2 ring-rose-400/50" : ""}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="app-panel overflow-hidden app-compact-scroll">
            {isLoading ? (
              <div className="flex justify-center py-20">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-rose-500 border-t-transparent" />
              </div>
            ) : logs.length === 0 ? (
              <div className="text-center py-16 text-gray-400">Событий пока нет</div>
            ) : (
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Время</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Уровень</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Устройство</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Событие</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Сообщение</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-gray-50/80 transition">
                      <td className="px-4 py-3 text-xs text-gray-500">{new Date(log.created_at).toLocaleString("ru-RU")}</td>
                      <td className="px-4 py-3">{severityBadge(log.severity)}</td>
                      <td className="px-4 py-3">
                        <div className="text-sm text-gray-700">{log.device_name || "—"}</div>
                        <div className="text-xs text-gray-500">{log.ip_address || "—"}</div>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">{log.event_type}</td>
                      <td className="px-4 py-3 text-sm text-gray-700">{log.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
