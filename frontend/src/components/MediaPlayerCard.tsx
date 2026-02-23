import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Pencil, Trash2, Monitor, Music, ExternalLink, Clock, Cpu, Network, Wifi, Play, Square, Volume2 } from "lucide-react";
import type { MediaPlayer } from "../client";
import { getIconbitStatus, iconbitPlay, iconbitStop } from "../client";

interface Props {
  player: MediaPlayer;
  onPoll: (id: string) => void;
  onEdit: (player: MediaPlayer) => void;
  onDelete: (id: string) => void;
  isPolling: boolean;
  isSuperuser: boolean;
}

const DEVICE_STYLES: Record<string, { bg: string; iconBg: string; iconColor: string; icon: typeof Monitor }> = {
  nettop: { bg: "bg-blue-50", iconBg: "bg-blue-50", iconColor: "text-blue-600", icon: Monitor },
  iconbit: { bg: "bg-purple-50", iconBg: "bg-purple-50", iconColor: "text-purple-600", icon: Music },
  twix: { bg: "bg-orange-50", iconBg: "bg-orange-50", iconColor: "text-orange-600", icon: Music },
};

const DEVICE_LABELS: Record<string, string> = {
  nettop: "Неттоп",
  iconbit: "Iconbit",
  twix: "Twix",
};

function statusBadge(player: MediaPlayer) {
  if (player.is_online === null) {
    return <span className="inline-flex items-center gap-1 text-xs text-gray-400"><span className="h-2 w-2 rounded-full bg-gray-300" />Не проверен</span>;
  }
  if (player.is_online) {
    return <span className="inline-flex items-center gap-1 text-xs text-emerald-600"><span className="h-2 w-2 rounded-full bg-emerald-500" />Онлайн</span>;
  }
  return <span className="inline-flex items-center gap-1 text-xs text-red-500"><span className="h-2 w-2 rounded-full bg-red-500" />Оффлайн</span>;
}

function webPanelUrl(player: MediaPlayer): string {
  if (player.device_type === "iconbit") return `http://${player.ip_address}:8081`;
  return `http://${player.ip_address}`;
}

function IconbitControls({ playerId }: { playerId: string }) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);

  const { data: ibStatus } = useQuery({
    queryKey: ["iconbit-status", playerId],
    queryFn: () => getIconbitStatus(playerId),
    refetchInterval: 10_000,
    staleTime: 5_000,
  });

  const playMut = useMutation({
    mutationFn: () => iconbitPlay(playerId),
    onMutate: () => setBusy(true),
    onSettled: () => {
      setBusy(false);
      queryClient.invalidateQueries({ queryKey: ["iconbit-status", playerId] });
    },
  });

  const stopMut = useMutation({
    mutationFn: () => iconbitStop(playerId),
    onMutate: () => setBusy(true),
    onSettled: () => {
      setBusy(false);
      queryClient.invalidateQueries({ queryKey: ["iconbit-status", playerId] });
    },
  });

  if (!ibStatus) return null;

  return (
    <div className="mt-1 space-y-1.5">
      <div className="flex items-center gap-1.5 text-xs">
        <Volume2 className="h-3 w-3 text-purple-400 shrink-0" />
        {ibStatus.is_playing && ibStatus.now_playing ? (
          <span className="text-purple-700 font-medium truncate" title={ibStatus.now_playing}>
            {ibStatus.now_playing.length > 40 ? ibStatus.now_playing.slice(0, 40) + "..." : ibStatus.now_playing}
          </span>
        ) : (
          <span className="text-gray-400 italic">Не воспроизводится</span>
        )}
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={() => playMut.mutate()}
          disabled={busy}
          className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 text-[11px] font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-40 transition"
          title="Воспроизвести"
        >
          <Play className="h-3 w-3" />
          Play
        </button>
        <button
          onClick={() => stopMut.mutate()}
          disabled={busy}
          className="inline-flex items-center gap-1 rounded-md bg-red-50 px-2 py-1 text-[11px] font-medium text-red-600 hover:bg-red-100 disabled:opacity-40 transition"
          title="Остановить"
        >
          <Square className="h-3 w-3" />
          Stop
        </button>
        {ibStatus.files.length > 0 && (
          <span className="text-[10px] text-gray-400 ml-auto">
            {ibStatus.files.length} файл{ibStatus.files.length > 1 ? "ов" : ""}
            {ibStatus.free_space && ` · ${ibStatus.free_space}`}
          </span>
        )}
      </div>
    </div>
  );
}

export default function MediaPlayerCard({ player, onPoll, onEdit, onDelete, isPolling, isSuperuser }: Props) {
  const style = DEVICE_STYLES[player.device_type] ?? DEVICE_STYLES.nettop;
  const Icon = style.icon;
  const deviceLabel = DEVICE_LABELS[player.device_type] ?? player.device_type;
  const isIconbit = player.device_type === "iconbit";

  const polledAt = player.last_polled_at
    ? new Date(player.last_polled_at).toLocaleString("ru-RU", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" })
    : null;

  const ports = player.open_ports?.split(",").filter(Boolean) ?? [];

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition flex flex-col">
      <div className="p-5 flex flex-col gap-3">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`rounded-lg ${style.iconBg} p-2`}>
              <Icon className={`h-5 w-5 ${style.iconColor}`} />
            </div>
            <div>
              <div className="font-medium text-sm text-gray-900">{player.name}</div>
              <div className="text-xs text-gray-500">{player.model}</div>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            {statusBadge(player)}
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${style.bg} ${style.iconColor}`}>
              {deviceLabel}
            </span>
          </div>
        </div>

        {/* Device info */}
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <Wifi className="h-3 w-3 text-gray-400" />
            <span className="font-mono">{player.ip_address}</span>
          </div>

          {player.mac_address && (
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <Network className="h-3 w-3 text-gray-400" />
              <span className="font-mono">{player.mac_address}</span>
            </div>
          )}

          {player.hostname && (
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <Monitor className="h-3 w-3 text-gray-400" />
              <span>{player.hostname}</span>
            </div>
          )}

          {player.os_info && (
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <Cpu className="h-3 w-3 text-gray-400" />
              <span className="truncate" title={player.os_info}>
                {player.os_info.length > 60 ? player.os_info.slice(0, 60) + "..." : player.os_info}
              </span>
            </div>
          )}

          {player.uptime && (
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <Clock className="h-3 w-3 text-gray-400" />
              <span>Uptime: {player.uptime}</span>
            </div>
          )}

          {ports.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-gray-500 flex-wrap">
              <span className="text-gray-400">Порты:</span>
              {ports.map((p) => (
                <span key={p} className="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-[10px] font-mono">
                  {p}
                </span>
              ))}
            </div>
          )}

          {isIconbit && player.is_online && <IconbitControls playerId={player.id} />}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-gray-100">
          <span className="text-[11px] text-gray-400">
            {polledAt ? `Обновлено: ${polledAt}` : "Ещё не опрашивался"}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPoll(player.id)}
              disabled={isPolling}
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-blue-600 transition disabled:opacity-40"
              title="Опросить"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isPolling ? "animate-spin" : ""}`} />
            </button>
            <a
              href={webPanelUrl(player)}
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
                  onClick={() => onEdit(player)}
                  className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-amber-600 transition"
                  title="Редактировать"
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => onDelete(player.id)}
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
    </div>
  );
}
