import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Cable, QrCode, SendHorizontal } from "lucide-react";
import { runOneCExchangeByBarcode } from "../client";
import OneCQrPanel from "../components/OneCQrPanel";

type Tab = "qr" | "products";
type ExchangeTarget = "duty_free" | "duty_paid";
type IdentifierKind = "kkm_number" | "serial_number" | "hostname" | "inventory_number" | "cash_number";

export default function OneCPage() {
  const [tab, setTab] = useState<Tab>("qr");
  const [target, setTarget] = useState<ExchangeTarget>("duty_free");
  const [identifierKind, setIdentifierKind] = useState<IdentifierKind>("kkm_number");
  const [barcode, setBarcode] = useState("");
  const [cashIdentifiers, setCashIdentifiers] = useState("");

  const exchangeMut = useMutation({
    mutationFn: runOneCExchangeByBarcode,
  });

  const submitExchange = () => {
    exchangeMut.mutate({
      target,
      barcode: barcode.trim(),
      cash_register_identifier_kind: identifierKind,
      cash_register_identifiers: cashIdentifiers
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean),
      source: "infrascope-1c-tab",
    });
  };

  return (
    <div className="space-y-6">
      <div className="app-panel p-3">
        <div className="app-tabbar flex gap-1 p-1.5 w-fit max-w-full overflow-x-auto app-compact-scroll">
          <button
            type="button"
            onClick={() => setTab("qr")}
            className={`app-tab inline-flex items-center gap-2 px-4 py-2 text-sm font-medium ${tab === "qr" ? "active" : "text-gray-500 hover:text-gray-700"}`}
          >
            <QrCode className="h-4 w-4" />
            QR генератор
          </button>
          <button
            type="button"
            onClick={() => setTab("products")}
            className={`app-tab inline-flex items-center gap-2 px-4 py-2 text-sm font-medium ${tab === "products" ? "active" : "text-gray-500 hover:text-gray-700"}`}
          >
            <Cable className="h-4 w-4" />
            Выгрузка товара
          </button>
        </div>
      </div>

      {tab === "qr" ? (
        <div className="app-panel p-4 sm:p-5">
          <OneCQrPanel />
        </div>
      ) : (
        <div className="app-panel p-4 sm:p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Канал обмена</span>
              <select
                className="app-input w-full py-2 px-3 text-sm"
                value={target}
                onChange={(e) => setTarget(e.target.value as ExchangeTarget)}
              >
                <option value="duty_free">Duty Free (отдельный домен)</option>
                <option value="duty_paid">Duty Paid (отдельный домен)</option>
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Штрихкод товара</span>
              <input
                className="app-input w-full py-2 px-3 text-sm"
                value={barcode}
                onChange={(e) => setBarcode(e.target.value)}
                placeholder="Например: 4601234567890"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Идентификатор кассы</span>
              <select
                className="app-input w-full py-2 px-3 text-sm"
                value={identifierKind}
                onChange={(e) => setIdentifierKind(e.target.value as IdentifierKind)}
              >
                <option value="kkm_number">ККМ номер (рекомендуется)</option>
                <option value="serial_number">Серийный номер</option>
                <option value="hostname">Hostname</option>
                <option value="inventory_number">Инвентарный номер</option>
                <option value="cash_number">Номер кассы</option>
              </select>
            </label>
            <label className="text-sm md:col-span-2">
              <span className="mb-1 block text-slate-600">
                Целевые кассы (через запятую, по выбранному идентификатору)
              </span>
              <input
                className="app-input w-full py-2 px-3 text-sm"
                value={cashIdentifiers}
                onChange={(e) => setCashIdentifiers(e.target.value)}
                placeholder="Например: 40070001, 40070002"
              />
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={submitExchange}
              disabled={exchangeMut.isPending || !barcode.trim()}
              className="app-btn-primary inline-flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-60"
            >
              <SendHorizontal className="h-4 w-4" />
              {exchangeMut.isPending ? "Отправка..." : "Запустить выгрузку"}
            </button>
          </div>

          {exchangeMut.isSuccess && (
            <div className={`text-sm ${exchangeMut.data.ok ? "text-emerald-600" : "text-rose-600"}`}>
              {exchangeMut.data.message}
              {exchangeMut.data.request_id ? ` (request_id: ${exchangeMut.data.request_id})` : ""}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
