import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Download, Plane, RotateCcw } from "lucide-react";
import { exportBoardingPass } from "../client";

type BarcodeFormat = "aztec" | "pdf417";

type FormState = {
  format: BarcodeFormat;
  first_name: string;
  last_name: string;
  booking_ref: string;
  from_code: string;
  to_code: string;
  flight_operator: string;
  flight_number: string;
  flight_date: string;
  day_in_year: string;
  travel_class: string;
  seat: string;
  boarding_index: string;
  raw_data: string;
};

const initialState: FormState = {
  format: "aztec",
  first_name: "",
  last_name: "",
  booking_ref: "",
  from_code: "",
  to_code: "",
  flight_operator: "",
  flight_number: "",
  flight_date: "",
  day_in_year: "",
  travel_class: "",
  seat: "",
  boarding_index: "",
  raw_data: "",
};

export default function BoardingPassPanel() {
  const [form, setForm] = useState<FormState>(initialState);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const exportMut = useMutation({
    mutationFn: exportBoardingPass,
    onSuccess: (blob) => {
      const date = new Date().toISOString().slice(0, 10);
      const link = document.createElement("a");
      const url = URL.createObjectURL(blob);
      link.href = url;
      link.download = `boarding_pass_${form.format}_${date}.png`;
      link.click();
      URL.revokeObjectURL(url);
      setError(null);
      setMessage("Файл boarding pass сформирован и скачан.");
    },
    onError: (e: unknown) => {
      setMessage(null);
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "Не удалось сформировать boarding pass.");
    },
  });

  const setField = <K extends keyof FormState>(field: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const runExport = () => {
    setMessage(null);
    setError(null);
    exportMut.mutate({
      format: form.format,
      first_name: form.first_name.trim() || undefined,
      last_name: form.last_name.trim() || undefined,
      booking_ref: form.booking_ref.trim() || undefined,
      from_code: form.from_code.trim() || undefined,
      to_code: form.to_code.trim() || undefined,
      flight_operator: form.flight_operator.trim() || undefined,
      flight_number: form.flight_number.trim() || undefined,
      flight_date: form.flight_date.trim() || undefined,
      day_in_year: form.day_in_year.trim() || undefined,
      travel_class: form.travel_class.trim() || undefined,
      seat: form.seat.trim() || undefined,
      boarding_index: form.boarding_index.trim() || undefined,
      raw_data: form.raw_data.trim() || undefined,
    });
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Симвология</span>
          <select
            className="app-input w-full py-2 px-3 text-sm"
            value={form.format}
            onChange={(e) => setField("format", e.target.value as BarcodeFormat)}
          >
            <option value="aztec">Aztec</option>
            <option value="pdf417">PDF417</option>
          </select>
        </label>
        <label className="text-sm md:col-span-2">
          <span className="mb-1 block text-slate-600">Raw payload (если нужно обойти сборку из полей)</span>
          <textarea
            className="app-input w-full py-2 px-3 text-sm min-h-24"
            value={form.raw_data}
            onChange={(e) => setField("raw_data", e.target.value)}
            placeholder="M1IVANOV/IVAN EBR123 SVOLED..."
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Имя</span>
          <input
            className="app-input w-full py-2 px-3 text-sm"
            value={form.first_name}
            onChange={(e) => setField("first_name", e.target.value)}
            placeholder="IVAN"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Фамилия</span>
          <input
            className="app-input w-full py-2 px-3 text-sm"
            value={form.last_name}
            onChange={(e) => setField("last_name", e.target.value)}
            placeholder="IVANOV"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Booking ref</span>
          <input
            className="app-input w-full py-2 px-3 text-sm"
            value={form.booking_ref}
            onChange={(e) => setField("booking_ref", e.target.value)}
            placeholder="EBR123"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Откуда</span>
          <input
            className="app-input w-full py-2 px-3 text-sm"
            value={form.from_code}
            onChange={(e) => setField("from_code", e.target.value)}
            placeholder="SVO"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Куда</span>
          <input
            className="app-input w-full py-2 px-3 text-sm"
            value={form.to_code}
            onChange={(e) => setField("to_code", e.target.value)}
            placeholder="LED"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Оператор</span>
          <input
            className="app-input w-full py-2 px-3 text-sm"
            value={form.flight_operator}
            onChange={(e) => setField("flight_operator", e.target.value)}
            placeholder="SU"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Номер рейса</span>
          <input
            className="app-input w-full py-2 px-3 text-sm"
            value={form.flight_number}
            onChange={(e) => setField("flight_number", e.target.value)}
            placeholder="1234"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Дата рейса</span>
          <input
            type="date"
            className="app-input w-full py-2 px-3 text-sm"
            value={form.flight_date}
            onChange={(e) => setField("flight_date", e.target.value)}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Day in year</span>
          <input
            className="app-input w-full py-2 px-3 text-sm"
            value={form.day_in_year}
            onChange={(e) => setField("day_in_year", e.target.value)}
            placeholder="032"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Класс</span>
          <input
            className="app-input w-full py-2 px-3 text-sm"
            value={form.travel_class}
            onChange={(e) => setField("travel_class", e.target.value)}
            placeholder="Y"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Место</span>
          <input
            className="app-input w-full py-2 px-3 text-sm"
            value={form.seat}
            onChange={(e) => setField("seat", e.target.value)}
            placeholder="12A"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Boarding index</span>
          <input
            className="app-input w-full py-2 px-3 text-sm"
            value={form.boarding_index}
            onChange={(e) => setField("boarding_index", e.target.value)}
            placeholder="001"
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={runExport}
          disabled={exportMut.isPending}
          className="app-btn-primary inline-flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-60"
        >
          <Plane className="h-4 w-4" />
          {exportMut.isPending ? "Формирование..." : "Сформировать и скачать PNG"}
        </button>
        <button
          type="button"
          onClick={() => {
            setForm(initialState);
            setMessage(null);
            setError(null);
          }}
          className="app-btn-secondary inline-flex items-center gap-2 px-4 py-2 text-sm"
        >
          <RotateCcw className="h-4 w-4" />
          Сбросить
        </button>
      </div>

      {message && <div className="text-sm text-emerald-700">{message}</div>}
      {error && <div className="text-sm text-rose-700">{error}</div>}
      <div className="text-xs text-slate-500">
        Если `raw payload` заполнен, backend использует его напрямую вместо сборки строки из полей.
      </div>
    </div>
  );
}
