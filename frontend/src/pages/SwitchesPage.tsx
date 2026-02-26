import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Network } from "lucide-react";
import { useAuth } from "../auth";
import type { NetworkSwitch } from "../client";
import { getSwitches, createSwitch, updateSwitch, deleteSwitch, pollSwitch } from "../client";
import SwitchForm from "../components/SwitchForm";
import SwitchCard from "../components/SwitchCard";
import SwitchPortsTable from "../components/SwitchPortsTable";

export default function SwitchesPage() {
  const { user } = useAuth();
  const isSuperuser = user?.is_superuser ?? false;
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editTarget, setEditTarget] = useState<NetworkSwitch | null>(null);
  const [pollingId, setPollingId] = useState<string | null>(null);
  const [portsTarget, setPortsTarget] = useState<NetworkSwitch | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["switches", search],
    queryFn: () => getSwitches(search || undefined),
    staleTime: 10_000,
  });

  const switches = data?.data ?? [];
  const onlineCount = switches.filter((s) => s.is_online === true).length;

  const pollMut = useMutation({
    mutationFn: (id: string) => pollSwitch(id),
    onMutate: (id) => setPollingId(id),
    onSettled: () => {
      setPollingId(null);
      queryClient.invalidateQueries({ queryKey: ["switches"] });
    },
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Network className="h-6 w-6 text-teal-600" />
            Сетевое оборудование
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {switches.length} свитч(ей) &middot; {onlineCount} онлайн
          </p>
        </div>
        {isSuperuser && (
          <button
            onClick={() => { setEditTarget(null); setShowForm(true); }}
            className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 transition shadow-sm"
          >
            <Plus className="h-4 w-4" />
            Добавить свитч
          </button>
        )}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск по названию..."
          className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:border-teal-500 focus:ring-1 focus:ring-teal-500 outline-none"
        />
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-teal-500 border-t-transparent" />
        </div>
      ) : switches.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {switches.map((sw) => (
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
    </div>
  );
}
