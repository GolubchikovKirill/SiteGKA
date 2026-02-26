import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Plus, Search, Printer as PrinterIcon, Tag, Wifi } from "lucide-react";
import {
  getPrinters,
  pollAllPrinters,
  pollPrinter,
  createPrinter,
  updatePrinter,
  deletePrinter,
  type Printer,
  type PrinterType,
} from "../client";
import { useAuth } from "../auth";
import PrinterCard from "../components/PrinterCard";
import ZebraCard from "../components/ZebraCard";
import PrinterForm from "../components/PrinterForm";
import NetworkScanner from "../components/NetworkScanner";

type TabKey = PrinterType | "scanner";
type StatusFilter = "all" | "online" | "offline";

const TABS: { key: TabKey; label: string; icon: typeof PrinterIcon }[] = [
  { key: "laser", label: "Картриджные", icon: PrinterIcon },
  { key: "label", label: "Этикеточные", icon: Tag },
  { key: "scanner", label: "Поиск в сети", icon: Wifi },
];

export default function Dashboard() {
  const { user } = useAuth();
  const isSuperuser = user?.is_superuser ?? false;
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<TabKey>("laser");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingPrinter, setEditingPrinter] = useState<Printer | null>(null);
  const [pollingIds, setPollingIds] = useState<Set<string>>(new Set());
  const [formError, setFormError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const printerTab = activeTab === "laser" || activeTab === "label" ? activeTab : "laser";

  const { data, isLoading } = useQuery({
    queryKey: ["printers", printerTab, search],
    queryFn: () => getPrinters(search || undefined, printerTab),
    enabled: activeTab !== "scanner",
  });

  const pollAllMut = useMutation({
    mutationFn: () => pollAllPrinters(printerTab),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["printers"] }),
  });

  const pollOneMut = useMutation({
    mutationFn: pollPrinter,
    onMutate: (id) => setPollingIds((s) => new Set(s).add(id)),
    onSettled: (_d, _e, id) => {
      setPollingIds((s) => { const n = new Set(s); n.delete(id); return n; });
      queryClient.invalidateQueries({ queryKey: ["printers"] });
    },
  });

  const extractError = (err: unknown): string => {
    if (err && typeof err === "object" && "response" in err) {
      const resp = (err as { response?: { data?: { detail?: string }; status?: number } }).response;
      const detail = resp?.data?.detail;
      if (detail === "Printer with this IP already exists") return "Принтер с таким IP уже существует";
      if (resp?.status === 409) return "Принтер с таким IP уже существует";
      if (detail) return detail;
    }
    return "Не удалось сохранить принтер";
  };

  const createMut = useMutation({
    mutationFn: createPrinter,
    onSuccess: () => {
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["printers"] });
      setShowForm(false);
    },
    onError: (err) => setFormError(extractError(err)),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, ...rest }: { id: string; [key: string]: unknown }) =>
      updatePrinter(id, rest),
    onSuccess: () => {
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["printers"] });
      setEditingPrinter(null);
      setShowForm(false);
    },
    onError: (err) => setFormError(extractError(err)),
  });

  const deleteMut = useMutation({
    mutationFn: deletePrinter,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["printers"] }),
  });

  const handleDelete = (id: string) => {
    if (confirm("Удалить принтер?")) deleteMut.mutate(id);
  };

  const printers = data?.data ?? [];
  const sortedPrinters = [...printers].sort((a, b) => {
    const rank = (value: boolean | null) => (value === true ? 0 : value === null ? 1 : 2);
    return rank(a.is_online) - rank(b.is_online);
  });
  const visiblePrinters = sortedPrinters.filter((printer) => {
    if (statusFilter === "online") return printer.is_online === true;
    if (statusFilter === "offline") return printer.is_online === false;
    return true;
  });

  const total = printers.length;
  const online = printers.filter((p) => p.is_online === true).length;
  const offline = printers.filter((p) => p.is_online === false).length;
  const lowToner = printerTab === "laser"
    ? printers.filter((p) => {
        const levels = [p.toner_black, p.toner_cyan, p.toner_magenta, p.toner_yellow].filter((l): l is number => l !== null && l >= 0);
        return levels.some((l) => l < 15);
      }).length
    : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="app-toolbar p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Мониторинг принтеров</h1>
          <p className="text-sm text-slate-500 mt-1">Состояние оборудования, доступность и расходники</p>
        </div>
        {activeTab !== "scanner" && (
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => pollAllMut.mutate()}
              disabled={pollAllMut.isPending}
              className="app-btn-primary inline-flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-50 transition"
            >
              <RefreshCw className={`h-4 w-4 ${pollAllMut.isPending ? "animate-spin" : ""}`} />
              {pollAllMut.isPending ? "Опрос..." : "Опросить все"}
            </button>
            {isSuperuser && (
              <button
                onClick={() => { setEditingPrinter(null); setFormError(null); setShowForm(true); }}
                className="app-btn-secondary inline-flex items-center gap-2 px-4 py-2 text-sm transition"
              >
                <Plus className="h-4 w-4" />
                Добавить
              </button>
            )}
          </div>
        )}
      </div>

      {/* Stats (only for printer tabs) */}
      {activeTab !== "scanner" && (
        <div className={`grid gap-4 ${printerTab === "laser" ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-3"}`}>
          <Stat label="Всего" value={total} color="text-gray-900" bg="bg-gray-100" isActive={statusFilter === "all"} onClick={() => setStatusFilter("all")} />
          <Stat label="Онлайн" value={online} color="text-emerald-700" bg="bg-emerald-50" isActive={statusFilter === "online"} onClick={() => setStatusFilter("online")} />
          <Stat label="Оффлайн" value={offline} color="text-red-700" bg="bg-red-50" isActive={statusFilter === "offline"} onClick={() => setStatusFilter("offline")} />
          {printerTab === "laser" && (
            <Stat label="Мало тонера" value={lowToner} color="text-amber-700" bg="bg-amber-50" />
          )}
        </div>
      )}

      {/* Search (only for printer tabs) */}
      {activeTab !== "scanner" && (
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по магазину..."
            className="app-input w-full pl-10 pr-4 py-2 text-sm"
          />
        </div>
      )}

      {/* Sub-tabs */}
      <div className="app-tabbar flex gap-1 p-1.5 w-fit max-w-full overflow-x-auto app-compact-scroll">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`app-tab inline-flex items-center gap-2 px-4 py-2 text-sm font-medium ${
              activeTab === key
                ? "active"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Scanner view */}
      {activeTab === "scanner" && <NetworkScanner />}

      {/* Printer grid */}
      {activeTab !== "scanner" && (
        <>
          {isLoading ? (
            <div className="flex justify-center py-20">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
            </div>
          ) : visiblePrinters.length === 0 ? (
            <div className="text-center py-20 text-gray-400">
              <p className="text-lg">Нет {printerTab === "laser" ? "принтеров" : "этикеточных принтеров"}</p>
              <p className="text-sm mt-1">Добавьте {printerTab === "laser" ? "первый принтер" : "принтер этикеток"} для мониторинга</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {visiblePrinters.map((printer) =>
                printerTab === "laser" ? (
                  <PrinterCard
                    key={printer.id}
                    printer={printer}
                    onPoll={(id) => pollOneMut.mutate(id)}
                    onEdit={(p) => { setEditingPrinter(p); setFormError(null); setShowForm(true); }}
                    onDelete={handleDelete}
                    isPolling={pollingIds.has(printer.id) || pollAllMut.isPending}
                    isSuperuser={isSuperuser}
                  />
                ) : (
                  <ZebraCard
                    key={printer.id}
                    printer={printer}
                    onPoll={(id) => pollOneMut.mutate(id)}
                    onEdit={(p) => { setEditingPrinter(p); setFormError(null); setShowForm(true); }}
                    onDelete={handleDelete}
                    isPolling={pollingIds.has(printer.id) || pollAllMut.isPending}
                    isSuperuser={isSuperuser}
                  />
                )
              )}
            </div>
          )}
        </>
      )}

      {/* Modal form */}
      {showForm && activeTab !== "scanner" && (
        <PrinterForm
          printer={editingPrinter}
          printerType={printerTab}
          loading={createMut.isPending || updateMut.isPending}
          error={formError}
          onClose={() => { setShowForm(false); setEditingPrinter(null); setFormError(null); }}
          onSave={(formData) => {
            setFormError(null);
            if (editingPrinter) {
              updateMut.mutate({ id: editingPrinter.id, ...formData });
            } else {
              createMut.mutate({ printer_type: printerTab, ...formData });
            }
          }}
        />
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  color,
  bg,
  isActive,
  onClick,
}: {
  label: string;
  value: number;
  color: string;
  bg: string;
  isActive?: boolean;
  onClick?: () => void;
}) {
  if (!onClick) {
    return (
      <div className={`app-stat ${bg} w-full px-4 py-3 text-left`}>
        <div className={`text-2xl font-bold ${color}`}>{value}</div>
        <div className="text-xs text-gray-500 mt-0.5">{label}</div>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={`app-stat ${bg} w-full px-4 py-3 text-left transition ${isActive ? "ring-2 ring-rose-400/50" : "hover:-translate-y-0.5 hover:shadow-md"}`}
    >
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
    </button>
  );
}
