import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Plus, Search, Monitor, Music } from "lucide-react";
import {
  getMediaPlayers,
  pollAllMediaPlayers,
  pollMediaPlayer,
  createMediaPlayer,
  updateMediaPlayer,
  deleteMediaPlayer,
  type MediaPlayer,
  type DeviceType,
} from "../client";
import { useAuth } from "../auth";
import MediaPlayerCard from "../components/MediaPlayerCard";
import MediaPlayerForm from "../components/MediaPlayerForm";

type FilterKey = "all" | DeviceType;

const FILTERS: { key: FilterKey; label: string; icon: typeof Monitor }[] = [
  { key: "all", label: "Все", icon: Monitor },
  { key: "nettop", label: "Неттопы", icon: Monitor },
  { key: "iconbit", label: "Iconbit", icon: Music },
  { key: "twix", label: "Twix", icon: Music },
];

export default function MediaPlayersPage() {
  const { user } = useAuth();
  const isSuperuser = user?.is_superuser ?? false;
  const queryClient = useQueryClient();

  const [activeFilter, setActiveFilter] = useState<FilterKey>("all");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingPlayer, setEditingPlayer] = useState<MediaPlayer | null>(null);
  const [pollingIds, setPollingIds] = useState<Set<string>>(new Set());
  const [formError, setFormError] = useState<string | null>(null);

  const deviceTypeParam = activeFilter === "all" ? undefined : activeFilter;

  const { data, isLoading } = useQuery({
    queryKey: ["media-players", deviceTypeParam, search],
    queryFn: () => getMediaPlayers(search || undefined, deviceTypeParam),
  });

  const pollAllMut = useMutation({
    mutationFn: () => pollAllMediaPlayers(deviceTypeParam),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["media-players"] }),
  });

  const pollOneMut = useMutation({
    mutationFn: pollMediaPlayer,
    onMutate: (id) => setPollingIds((s) => new Set(s).add(id)),
    onSettled: (_d, _e, id) => {
      setPollingIds((s) => { const n = new Set(s); n.delete(id); return n; });
      queryClient.invalidateQueries({ queryKey: ["media-players"] });
    },
  });

  const extractError = (err: unknown): string => {
    if (err && typeof err === "object" && "response" in err) {
      const resp = (err as { response?: { data?: { detail?: string }; status?: number } }).response;
      const detail = resp?.data?.detail;
      if (detail === "Device with this IP already exists") return "Устройство с таким IP уже существует";
      if (resp?.status === 409) return "Устройство с таким IP уже существует";
      if (detail) return detail;
    }
    return "Не удалось сохранить устройство";
  };

  const createMut = useMutation({
    mutationFn: createMediaPlayer,
    onSuccess: () => {
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["media-players"] });
      setShowForm(false);
    },
    onError: (err) => setFormError(extractError(err)),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, ...rest }: { id: string; [key: string]: unknown }) =>
      updateMediaPlayer(id, rest),
    onSuccess: () => {
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["media-players"] });
      setEditingPlayer(null);
      setShowForm(false);
    },
    onError: (err) => setFormError(extractError(err)),
  });

  const deleteMut = useMutation({
    mutationFn: deleteMediaPlayer,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["media-players"] }),
  });

  const handleDelete = (id: string) => {
    if (confirm("Удалить устройство?")) deleteMut.mutate(id);
  };

  const players = data?.data ?? [];
  const total = players.length;
  const online = players.filter((p) => p.is_online === true).length;
  const offline = players.filter((p) => p.is_online === false).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Медиаплееры</h1>
          <p className="text-sm text-gray-500 mt-1">Неттопы, Iconbit и Twix устройства</p>
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
              onClick={() => { setEditingPlayer(null); setFormError(null); setShowForm(true); }}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
            >
              <Plus className="h-4 w-4" />
              Добавить
            </button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 grid-cols-3">
        <Stat label="Всего" value={total} color="text-gray-900" bg="bg-gray-100" />
        <Stat label="Онлайн" value={online} color="text-emerald-700" bg="bg-emerald-50" />
        <Stat label="Оффлайн" value={offline} color="text-red-700" bg="bg-red-50" />
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск по названию..."
          className="w-full rounded-lg border border-gray-300 pl-10 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        {FILTERS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveFilter(key)}
            className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition ${
              activeFilter === key
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="flex justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
        </div>
      ) : players.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <p className="text-lg">Нет устройств</p>
          <p className="text-sm mt-1">Добавьте первое устройство для мониторинга</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {players.map((player) => (
            <MediaPlayerCard
              key={player.id}
              player={player}
              onPoll={(id) => pollOneMut.mutate(id)}
              onEdit={(p) => { setEditingPlayer(p); setFormError(null); setShowForm(true); }}
              onDelete={handleDelete}
              isPolling={pollingIds.has(player.id) || pollAllMut.isPending}
              isSuperuser={isSuperuser}
            />
          ))}
        </div>
      )}

      {/* Modal form */}
      {showForm && (
        <MediaPlayerForm
          player={editingPlayer}
          loading={createMut.isPending || updateMut.isPending}
          error={formError}
          onClose={() => { setShowForm(false); setEditingPlayer(null); setFormError(null); }}
          onSave={(formData) => {
            setFormError(null);
            if (editingPlayer) {
              updateMut.mutate({ id: editingPlayer.id, ...formData });
            } else {
              createMut.mutate(formData);
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
