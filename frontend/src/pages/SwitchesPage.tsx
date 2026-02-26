import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw, Search, Network } from "lucide-react";
import { useAuth } from "../auth";
import type { NetworkSwitch } from "../client";
import { getSwitches, createSwitch, updateSwitch, deleteSwitch, pollSwitch, pollAllSwitches } from "../client";
import {
  AUTO_REFRESH_INTERVAL_OPTIONS,
  type AutoRefreshMinutes,
  readAutoRefreshEnabled,
  readAutoRefreshIntervalMinutes,
  writeAutoRefreshEnabled,
  writeAutoRefreshIntervalMinutes,
} from "../autoRefresh";
import SwitchForm from "../components/SwitchForm";
import SwitchCard from "../components/SwitchCard";
import SwitchPortsTable from "../components/SwitchPortsTable";
import NetworkDiscoveryModal from "../components/NetworkDiscoveryModal";

export default function SwitchesPage() {
  const { user } = useAuth();
  const isSuperuser = user?.is_superuser ?? false;
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [showDiscovery, setShowDiscovery] = useState(false);
  const [editTarget, setEditTarget] = useState<NetworkSwitch | null>(null);
  const [pollingId, setPollingId] = useState<string | null>(null);
  const [portsTarget, setPortsTarget] = useState<NetworkSwitch | null>(null);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState<boolean>(() => readAutoRefreshEnabled());
  const [autoRefreshMinutes, setAutoRefreshMinutes] = useState<AutoRefreshMinutes>(() => readAutoRefreshIntervalMinutes());

  const { data, isLoading } = useQuery({
    queryKey: ["switches", search],
    queryFn: () => getSwitches(search || undefined),
    staleTime: 10_000,
  });

  const switches = data?.data ?? [];
  const onlineCount = switches.filter((s) => s.is_online === true).length;
  const sortedSwitches = [...switches].sort((a, b) => {
    const rank = (value: boolean | null) => (value === true ? 0 : value === null ? 1 : 2);
    return rank(a.is_online) - rank(b.is_online);
  });

  const pollMut = useMutation({
    mutationFn: (id: string) => pollSwitch(id),
    onMutate: (id) => setPollingId(id),
    onSettled: () => {
      setPollingId(null);
      queryClient.invalidateQueries({ queryKey: ["switches"] });
    },
  });
  const pollAllMut = useMutation({
    mutationFn: pollAllSwitches,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["switches"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteSwitch(id),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["switches"] }),
  });

  const handleSave = async (formData: Record<string, unknown>) => {
    if (editTarget) {
      await updateSwitch(editTarget.id, formData);
    } else {
      await createSwitch(formData as Parameters<typeof createSwitch>[0]);
    }
    setShowForm(false);
    setEditTarget(null);
    queryClient.invalidateQueries({ queryKey: ["switches"] });
  };

  const handleDelete = (id: string) => {
    if (confirm("Удалить свитч?")) deleteMut.mutate(id);
  };

  useEffect(() => {
    if (!autoRefreshEnabled) return;
    const timer = setInterval(() => {
      pollAllSwitches()
        .then(() => queryClient.invalidateQueries({ queryKey: ["switches"] }))
        .catch(() => undefined);
    }, autoRefreshMinutes * 60_000);
    return () => clearInterval(timer);
  }, [autoRefreshEnabled, autoRefreshMinutes, queryClient]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="app-toolbar p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Network className="h-6 w-6 text-teal-600" />
            Сетевое оборудование
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {switches.length} свитч(ей) &middot; {onlineCount} онлайн
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="inline-flex items-center gap-2 text-xs text-slate-600 px-2">
            <input
              type="checkbox"
              checked={autoRefreshEnabled}
              onChange={(e) => {
                const checked = e.target.checked;
                setAutoRefreshEnabled(checked);
                writeAutoRefreshEnabled(checked);
              }}
              className="h-4 w-4"
            />
            Авто
          </label>
          <select
            value={autoRefreshMinutes}
            onChange={(e) => {
              const minutes = Number(e.target.value) as AutoRefreshMinutes;
              setAutoRefreshMinutes(minutes);
              writeAutoRefreshIntervalMinutes(minutes);
            }}
            className="app-input px-2 py-2 text-xs"
            title="Интервал автообновления"
          >
            {AUTO_REFRESH_INTERVAL_OPTIONS.map((minutes) => (
              <option key={minutes} value={minutes}>
                {minutes} мин
              </option>
            ))}
          </select>
          <button
            onClick={() => pollAllMut.mutate()}
            disabled={pollAllMut.isPending}
            className="app-btn-secondary inline-flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-50 transition"
          >
            <RefreshCw className={`h-4 w-4 ${pollAllMut.isPending ? "animate-spin" : ""}`} />
            {pollAllMut.isPending ? "Опрос..." : "Опросить все"}
          </button>
          <button
            onClick={() => setShowDiscovery(true)}
            className="app-btn-secondary inline-flex items-center gap-2 px-4 py-2 text-sm transition"
          >
            <Search className="h-4 w-4" />
            Поиск сети
          </button>
          {isSuperuser && (
            <button
              onClick={() => { setEditTarget(null); setShowForm(true); }}
              className="app-btn-primary inline-flex items-center gap-2 px-4 py-2 text-sm transition shadow-sm bg-gradient-to-br from-teal-600 to-cyan-600"
            >
              <Plus className="h-4 w-4" />
              Добавить свитч
            </button>
          )}
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск по названию..."
          className="app-input w-full pl-10 pr-4 py-2 text-sm"
        />
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-teal-500 border-t-transparent" />
        </div>
      ) : sortedSwitches.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sortedSwitches.map((sw) => (
            <SwitchCard
              key={sw.id}
              sw={sw}
              onPoll={(id) => pollMut.mutate(id)}
              onEdit={(s) => { setEditTarget(s); setShowForm(true); }}
              onDelete={handleDelete}
              onOpenPorts={(s) => setPortsTarget(s)}
              isPolling={pollingId === sw.id}
              isSuperuser={isSuperuser}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-20 text-gray-400">
          <Network className="h-12 w-12 mx-auto mb-3 text-gray-300" />
          <p>Нет добавленных свитчей</p>
          {isSuperuser && (
            <button
              onClick={() => { setEditTarget(null); setShowForm(true); }}
              className="mt-3 text-teal-600 hover:text-teal-700 text-sm font-medium"
            >
              Добавить первый свитч
            </button>
          )}
        </div>
      )}

      {/* Form modal */}
      {showForm && (
        <SwitchForm
          initial={editTarget ?? undefined}
          onSave={handleSave}
          onCancel={() => { setShowForm(false); setEditTarget(null); }}
        />
      )}
      {portsTarget && (
        <SwitchPortsTable
          sw={portsTarget}
          isSuperuser={isSuperuser}
          onClose={() => setPortsTarget(null)}
        />
      )}
      {showDiscovery && <NetworkDiscoveryModal kind="switch" onClose={() => setShowDiscovery(false)} />}
    </div>
  );
}
