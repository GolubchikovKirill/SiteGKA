import { useState, type FormEvent } from "react";
import { X, AlertCircle, Monitor, Music } from "lucide-react";
import type { MediaPlayer, DeviceType } from "../client";

interface Props {
  player?: MediaPlayer | null;
  onSave: (data: { device_type: DeviceType; name: string; model: string; ip_address: string }) => void;
  onClose: () => void;
  loading: boolean;
  error?: string | null;
}

const DEVICE_TYPES: { value: DeviceType; label: string; icon: typeof Monitor }[] = [
  { value: "nettop", label: "Неттоп", icon: Monitor },
  { value: "iconbit", label: "Iconbit", icon: Music },
  { value: "twix", label: "Twix", icon: Music },
];

const DEFAULT_MODELS: Record<DeviceType, string> = {
  nettop: "",
  iconbit: "Iconbit",
  twix: "Twix",
};

export default function MediaPlayerForm({ player, onSave, onClose, loading, error }: Props) {
  const [deviceType, setDeviceType] = useState<DeviceType>(player?.device_type ?? "nettop");
  const [name, setName] = useState(player?.name ?? "");
  const [model, setModel] = useState(player?.model ?? "");
  const [ipAddress, setIpAddress] = useState(player?.ip_address ?? "");

  const handleTypeChange = (type: DeviceType) => {
    setDeviceType(type);
    if (!player && !model) {
      setModel(DEFAULT_MODELS[type]);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSave({
      device_type: deviceType,
      name: name.trim(),
      model: model.trim(),
      ip_address: ipAddress.trim(),
    });
  };

  const title = player ? "Редактировать устройство" : "Добавить устройство";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100 transition">
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {error && (
          <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2.5 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {!player && (
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700">Тип устройства</label>
              <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                {DEVICE_TYPES.map(({ value, label, icon: Icon }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => handleTypeChange(value)}
                    className={`flex-1 inline-flex items-center justify-center gap-1.5 rounded-md px-2 py-2 text-sm font-medium transition ${
                      deviceType === value ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-gray-700">Название / Локация</label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Магазин A1 — касса"
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-gray-700">Модель</label>
            <input
              required
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder={deviceType === "nettop" ? "Intel NUC" : "Iconbit XDS74K"}
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-gray-700">IP-адрес</label>
            <input
              required
              value={ipAddress}
              onChange={(e) => setIpAddress(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="192.168.1.100"
              pattern="^(\d{1,3}\.){3}\d{1,3}$"
              title="Введите корректный IPv4 адрес"
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {loading ? "Сохранение..." : "Сохранить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
