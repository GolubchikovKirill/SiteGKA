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

export async function logout() {
  try {
    await api.post("/auth/logout");
  } catch {
    // ignore errors on logout
  }
}

export async function getMe() {
  const { data } = await api.post("/auth/test-token");
  return data;
}

// ── Users ──

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface UsersResponse {
  data: User[];
  count: number;
}

export async function getUsers() {
  const { data } = await api.get<UsersResponse>("/users/");
  return data;
}

export async function createUser(user: {
  email: string;
  password: string;
  full_name?: string;
  is_superuser?: boolean;
}) {
  const { data } = await api.post<User>("/users/", user);
  return data;
}

export async function updateUser(
  id: string,
  user: { email?: string; password?: string; full_name?: string; is_superuser?: boolean; is_active?: boolean },
) {
  const { data } = await api.patch<User>(`/users/${id}`, user);
  return data;
}

export async function deleteUser(id: string) {
  await api.delete(`/users/${id}`);
}

// ── Printers ──

export type PrinterType = "laser" | "label";
export type ConnectionType = "ip" | "usb";

export interface Printer {
  id: string;
  printer_type: PrinterType;
  connection_type: ConnectionType;
  store_name: string;
  model: string;
  ip_address: string | null;
  mac_address: string | null;
  mac_status: string | null;
  host_pc: string | null;
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
  connection_type?: ConnectionType;
  store_name: string;
  model: string;
  ip_address?: string;
  snmp_community?: string;
  host_pc?: string;
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

// ── Scanner ──

export interface DiscoveredDevice {
  ip: string;
  mac: string | null;
  open_ports: number[];
  hostname: string | null;
  is_known: boolean;
  known_printer_id: string | null;
  ip_changed: boolean;
  old_ip: string | null;
}

export interface ScanProgress {
  status: "idle" | "running" | "done" | "error";
  scanned: number;
  total: number;
  found: number;
  message: string | null;
}

export interface ScanResultsResponse {
  progress: ScanProgress;
  devices: DiscoveredDevice[];
}

export async function startScan(subnet: string, ports: string = "9100,631,80,443") {
  const { data } = await api.post<ScanProgress>("/scanner/scan", { subnet, ports });
  return data;
}

export async function getScanStatus() {
  const { data } = await api.get<ScanProgress>("/scanner/status");
  return data;
}

export async function getScanResults() {
  const { data } = await api.get<ScanResultsResponse>("/scanner/results");
  return data;
}

export async function getScannerSettings() {
  const { data } = await api.get<{ subnet: string; ports: string }>("/scanner/settings");
  return data;
}

export async function addDiscoveredPrinter(printer: {
  printer_type?: PrinterType;
  store_name: string;
  model: string;
  ip_address: string;
  snmp_community?: string;
}) {
  const { data } = await api.post<Printer>("/scanner/add", printer);
  return data;
}

export async function updatePrinterIp(printerId: string, newIp: string, newMac?: string) {
  const params: Record<string, string> = { new_ip: newIp };
  if (newMac) params.new_mac = newMac;
  const { data } = await api.post<Printer>(`/scanner/update-ip/${printerId}`, null, { params });
  return data;
}

// ── Media Players ──

export type DeviceType = "nettop" | "iconbit" | "twix";

export interface MediaPlayer {
  id: string;
  device_type: DeviceType;
  name: string;
  model: string;
  ip_address: string;
  mac_address: string | null;
  is_online: boolean | null;
  hostname: string | null;
  os_info: string | null;
  uptime: string | null;
  open_ports: string | null;
  last_polled_at: string | null;
  created_at: string;
}

export interface MediaPlayersResponse {
  data: MediaPlayer[];
  count: number;
}

export async function getMediaPlayers(name?: string, device_type?: DeviceType) {
  const params: Record<string, string> = {};
  if (name) params.name = name;
  if (device_type) params.device_type = device_type;
  const { data } = await api.get<MediaPlayersResponse>("/media-players/", { params });
  return data;
}

export async function createMediaPlayer(player: {
  device_type: DeviceType;
  name: string;
  model: string;
  ip_address: string;
  mac_address?: string;
}) {
  const { data } = await api.post<MediaPlayer>("/media-players/", player);
  return data;
}

export async function updateMediaPlayer(id: string, player: Partial<MediaPlayer>) {
  const { data } = await api.patch<MediaPlayer>(`/media-players/${id}`, player);
  return data;
}

export async function deleteMediaPlayer(id: string) {
  await api.delete(`/media-players/${id}`);
}

export async function pollMediaPlayer(id: string) {
  const { data } = await api.post<MediaPlayer>(`/media-players/${id}/poll`);
  return data;
}

export async function pollAllMediaPlayers(device_type?: DeviceType) {
  const params: Record<string, string> = {};
  if (device_type) params.device_type = device_type;
  const { data } = await api.post<MediaPlayersResponse>("/media-players/poll-all", null, { params });
  return data;
}

// ── Iconbit control ──

export interface IconbitStatus {
  now_playing: string | null;
  is_playing: boolean;
  files: string[];
  free_space: string | null;
}

export async function getIconbitStatus(playerId: string) {
  const { data } = await api.get<IconbitStatus>(`/media-players/${playerId}/iconbit/status`);
  return data;
}

export async function iconbitPlay(playerId: string) {
  const { data } = await api.post(`/media-players/${playerId}/iconbit/play`);
  return data;
}

export async function iconbitStop(playerId: string) {
  const { data } = await api.post(`/media-players/${playerId}/iconbit/stop`);
  return data;
}

export async function iconbitPlayFile(playerId: string, filename: string) {
  const { data } = await api.post(`/media-players/${playerId}/iconbit/play-file`, { filename });
  return data;
}

export async function iconbitDeleteFile(playerId: string, filename: string) {
  const { data } = await api.post(`/media-players/${playerId}/iconbit/delete-file`, { filename });
  return data;
}

export async function iconbitUpload(playerId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post(`/media-players/${playerId}/iconbit/upload`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function iconbitBulkPlay() {
  const { data } = await api.post("/media-players/iconbit/bulk-play");
  return data as { success: number; failed: number };
}

export async function iconbitBulkStop() {
  const { data } = await api.post("/media-players/iconbit/bulk-stop");
  return data as { success: number; failed: number };
}

export async function iconbitBulkUpload(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/media-players/iconbit/bulk-upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data as { success: number; failed: number; file: string };
}

export async function iconbitBulkDeleteFile(filename: string) {
  const { data } = await api.post("/media-players/iconbit/bulk-delete-file", { filename });
  return data as { success: number; failed: number };
}

export async function iconbitBulkPlayFile(filename: string) {
  const { data } = await api.post("/media-players/iconbit/bulk-play-file", { filename });
  return data as { success: number; failed: number };
}

export async function iconbitBulkReplace(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/media-players/iconbit/bulk-replace", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120_000,
  });
  return data as { success: number; failed: number; file: string };
}
