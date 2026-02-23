import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Plus, Search, Printer as PrinterIcon, Tag } from "lucide-react";
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

const TABS: { key: PrinterType; label: string; icon: typeof PrinterIcon }[] = [
  { key: "laser", label: "Картриджные", icon: PrinterIcon },
  { key: "label", label: "Этикетки", icon: Tag },
];

export default function Dashboard() {
  const { user } = useAuth();
  const isSuperuser = user?.is_superuser ?? false;
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<PrinterType>("laser");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingPrinter, setEditingPrinter] = useState<Printer | null>(null);
  const [pollingIds, setPollingIds] = useState<Set<string>>(new Set());
  const [formError, setFormError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["printers", activeTab, search],
    queryFn: () => getPrinters(search || undefined, activeTab),
  });

  const pollAllMut = useMutation({
    mutationFn: () => pollAllPrinters(activeTab),
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
    mutationFn: ({ id, ...rest }: { id: string; store_name: string; model: string; ip_address: string; snmp_community?: string }) =>
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

  const total = printers.length;
  const online = printers.filter((p) => p.is_online === true).length;
  const offline = printers.filter((p) => p.is_online === false).length;
  const lowToner = activeTab === "laser"
    ? printers.filter((p) => {
        const levels = [p.toner_black, p.toner_cyan, p.toner_magenta, p.toner_yellow].filter((l): l is number => l !== null && l >= 0);
        return levels.some((l) => l < 15);
      }).length
    : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Мониторинг принтеров</h1>
          <p className="text-sm text-gray-500 mt-1">Состояние оборудования и доступность</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => pollAllMut.mutate()}
            disabled={pollAllMut.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition"
          >
            <RefreshCw className={`h-4 w-4 ${pollAllMut.isPending ? "animate-spin" : ""}`} />
            {pollAllMut.isPending ? "Опрос..." : "Опросить все"}
          </button>
          {isSuperuser && (
            <button
              onClick={() => { setEditingPrinter(null); setFormError(null); setShowForm(true); }}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
            >
              <Plus className="h-4 w-4" />
              Добавить
            </button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className={`grid gap-4 ${activeTab === "laser" ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-3"}`}>
        <Stat label="Всего" value={total} color="text-gray-900" bg="bg-gray-100" />
        <Stat label="Онлайн" value={online} color="text-emerald-700" bg="bg-emerald-50" />
        <Stat label="Оффлайн" value={offline} color="text-red-700" bg="bg-red-50" />
        {activeTab === "laser" && (
          <Stat label="Мало тонера" value={lowToner} color="text-amber-700" bg="bg-amber-50" />
        )}
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск по магазину... (А = A)"
          className="w-full rounded-lg border border-gray-300 pl-10 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Sub-tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition ${
              activeTab === key
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Printer grid */}
      {isLoading ? (
        <div className="flex justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
        </div>
      ) : printers.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <p className="text-lg">Нет {activeTab === "laser" ? "принтеров" : "этикеточных принтеров"}</p>
          <p className="text-sm mt-1">Добавьте {activeTab === "laser" ? "первый принтер" : "принтер этикеток"} для мониторинга</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {printers.map((printer) =>
            activeTab === "laser" ? (
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

      {/* Modal form */}
      {showForm && (
        <PrinterForm
          printer={editingPrinter}
          printerType={activeTab}
          loading={createMut.isPending || updateMut.isPending}
          error={formError}
          onClose={() => { setShowForm(false); setEditingPrinter(null); setFormError(null); }}
          onSave={(formData) => {
            setFormError(null);
            if (editingPrinter) {
              updateMut.mutate({ id: editingPrinter.id, ...formData });
            } else {
              createMut.mutate({ printer_type: activeTab, ...formData });
            }
          }}
        />
      )}
    </div>
  );
}

function Stat({ label, value, color, bg }: { label: string; value: number; color: string; bg: string }) {
  return (
    <div className={`rounded-xl ${bg} px-4 py-3`}>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
    </div>
  );
}
