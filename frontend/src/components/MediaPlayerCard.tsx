import { RefreshCw, Pencil, Trash2, Monitor, Music, ExternalLink, Clock, Cpu, Network, Wifi } from "lucide-react";
import type { MediaPlayer } from "../client";

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

export default function MediaPlayerCard({ player, onPoll, onEdit, onDelete, isPolling, isSuperuser }: Props) {
  const style = DEVICE_STYLES[player.device_type] ?? DEVICE_STYLES.nettop;
  const Icon = style.icon;
  const deviceLabel = DEVICE_LABELS[player.device_type] ?? player.device_type;

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
              <div className="font-medium text-sm text-gray-900">{player.model}</div>
              <div className="text-xs text-gray-500">{player.name}</div>
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
            {player.mac_address && (
              <span className="text-gray-300 ml-1">| {player.mac_address}</span>
            )}
          </div>

          {player.hostname && (
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <Network className="h-3 w-3 text-gray-400" />
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
              href={`http://${player.ip_address}`}
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
