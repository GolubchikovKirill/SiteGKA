import { useState, type FormEvent } from "react";
import { X, AlertCircle } from "lucide-react";
import type { Printer, PrinterType } from "../client";

interface Props {
  printer?: Printer | null;
  printerType: PrinterType;
  onSave: (data: { store_name: string; model: string; ip_address: string; snmp_community: string }) => void;
  onClose: () => void;
  loading: boolean;
  error?: string | null;
}

export default function PrinterForm({ printer, printerType, onSave, onClose, loading, error }: Props) {
  const isLabel = printerType === "label";
  const [storeName, setStoreName] = useState(printer?.store_name ?? "");
  const [model, setModel] = useState(printer?.model ?? (isLabel ? "Zebra ZDesigner GK420t" : ""));
  const [ipAddress, setIpAddress] = useState(printer?.ip_address ?? "");
  const [community, setCommunity] = useState("public");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSave({
      store_name: storeName.trim(),
      model: model.trim(),
      ip_address: ipAddress.trim(),
      snmp_community: community.trim(),
    });
  };

  const title = printer
    ? isLabel ? "Редактировать принтер этикеток" : "Редактировать принтер"
    : isLabel ? "Добавить принтер этикеток" : "Добавить принтер";

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
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-gray-700">Магазин / Локация</label>
            <input
              required
              value={storeName}
              onChange={(e) => setStoreName(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="A1"
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-gray-700">Модель принтера</label>
            <input
              required
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder={isLabel ? "Zebra ZDesigner GK420t" : "HP LaserJet M404dn"}
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

          {!isLabel && (
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700">SNMP Community</label>
              <input
                value={community}
                onChange={(e) => setCommunity(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="public"
              />
            </div>
          )}

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
