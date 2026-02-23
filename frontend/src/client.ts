import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;

// ── Auth ──

export async function login(email: string, password: string) {
  const params = new URLSearchParams();
  params.append("username", email);
  params.append("password", password);
  const { data } = await api.post<{ access_token: string }>("/auth/login", params, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function getMe() {
  const { data } = await api.post("/auth/test-token");
  return data;
}

// ── Printers ──

export type PrinterType = "laser" | "label";

export interface Printer {
  id: string;
  printer_type: PrinterType;
  store_name: string;
  model: string;
  ip_address: string;
  is_online: boolean | null;
  status: string | null;
  toner_black: number | null;
  toner_cyan: number | null;
  toner_magenta: number | null;
  toner_yellow: number | null;
  last_polled_at: string | null;
  created_at: string;
}

export interface PrintersResponse {
  data: Printer[];
  count: number;
}

export async function getPrinters(store_name?: string, printer_type: PrinterType = "laser") {
  const params: Record<string, string> = { printer_type };
  if (store_name) params.store_name = store_name;
  const { data } = await api.get<PrintersResponse>("/printers/", { params });
  return data;
}

export async function createPrinter(printer: {
  printer_type?: PrinterType;
  store_name: string;
  model: string;
  ip_address: string;
  snmp_community?: string;
}) {
  const { data } = await api.post<Printer>("/printers/", printer);
  return data;
}

export async function updatePrinter(id: string, printer: Partial<Printer>) {
  const { data } = await api.patch<Printer>(`/printers/${id}`, printer);
  return data;
}

export async function deletePrinter(id: string) {
  await api.delete(`/printers/${id}`);
}

export async function pollPrinter(id: string) {
  const { data } = await api.post<Printer>(`/printers/${id}/poll`);
  return data;
}

export async function pollAllPrinters(printer_type: PrinterType = "laser") {
  const { data } = await api.post<PrintersResponse>("/printers/poll-all", null, {
    params: { printer_type },
  });
  return data;
}
