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
  last_seen_at: string | null;
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

// ── Event logs ──

export type EventSeverity = "info" | "warning" | "error" | "critical";
export type EventDeviceKind = "printer" | "media_player" | "switch" | "cash_register" | null;

export interface EventLog {
  id: string;
  severity: EventSeverity;
  category: string;
  event_type: string;
  message: string;
  device_kind: EventDeviceKind;
  device_name: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface EventLogsResponse {
  data: EventLog[];
  count: number;
}

export async function getEventLogs(params?: {
  skip?: number;
  limit?: number;
  severity?: EventSeverity | "all";
  device_kind?: "printer" | "media_player" | "switch" | "cash_register" | "all";
  q?: string;
}) {
  const query: Record<string, string | number> = {
    skip: params?.skip ?? 0,
    limit: params?.limit ?? 100,
  };
  if (params?.severity && params.severity !== "all") query.severity = params.severity;
  if (params?.device_kind && params.device_kind !== "all") query.device_kind = params.device_kind;
  if (params?.q) query.q = params.q;
  const { data } = await api.get<EventLogsResponse>("/logs/", { params: query });
  return data;
}

export function getNetSupportHelperDownloadUrl(
  filename: "Install-InfraScopeNetSupportHelper.ps1" | "NetSupportUriHandler.ps1" | "Uninstall-InfraScopeNetSupportHelper.ps1",
) {
  return `/api/v1/support-tools/netsupport-helper/${encodeURIComponent(filename)}`;
}

// ── Observability / Service Flow ──

export interface ServiceFlowLink {
  label: string;
  url: string;
}

export interface ServiceFlowNode {
  id: string;
  label: string;
  kind: string;
  status: "healthy" | "degraded" | "down" | "unknown" | string;
  req_rate: number | null;
  error_rate: number | null;
  p95_latency_ms: number | null;
  last_seen: string | null;
  links: ServiceFlowLink[];
}

export interface ServiceFlowEdge {
  source: string;
  target: string;
  transport: "http" | "kafka" | string;
  operation: string;
  status: "healthy" | "degraded" | "down" | "unknown" | string;
  req_rate: number | null;
  error_rate: number | null;
  p95_latency_ms: number | null;
}

export interface ServiceFlowRecentEvent {
  id: string;
  created_at: string;
  severity: EventSeverity | string;
  category: string;
  event_type: string;
  message: string;
  device_kind: EventDeviceKind | string;
  device_name: string | null;
  ip_address: string | null;
  trace_id: string | null;
}

export interface ServiceFlowMapResponse {
  generated_at: string;
  nodes: ServiceFlowNode[];
  edges: ServiceFlowEdge[];
  recent_events: ServiceFlowRecentEvent[];
}

export interface ServiceFlowTimeseriesPoint {
  timestamp: string;
  req_rate: number | null;
  error_rate: number | null;
  p95_latency_ms: number | null;
}

export interface ServiceFlowTimeseriesResponse {
  entity: string;
  points: ServiceFlowTimeseriesPoint[];
}

export async function getServiceFlowMap() {
  const { data } = await api.get<ServiceFlowMapResponse>("/observability/service-map");
  return data;
}

export async function getServiceFlowTimeseries(params?: {
  service?: string;
  source?: string;
  target?: string;
  minutes?: number;
  step_seconds?: number;
}) {
  const { data } = await api.get<ServiceFlowTimeseriesResponse>("/observability/service-map/timeseries", {
    params: {
      service: params?.service,
      source: params?.source,
      target: params?.target,
      minutes: params?.minutes ?? 60,
      step_seconds: params?.step_seconds ?? 30,
    },
  });
  return data;
}

// ── ML ──

export interface MLTonerPrediction {
  id: string;
  printer_id: string | null;
  printer_name: string | null;
  toner_color: "black" | "cyan" | "magenta" | "yellow" | string;
  toner_model: string | null;
  current_level: number | null;
  days_to_replacement: number | null;
  predicted_replacement_at: string | null;
  confidence: number;
  model_version: string;
  created_at: string;
}

export interface MLOfflineRiskPrediction {
  id: string;
  device_kind: string;
  device_id: string | null;
  device_name: string | null;
  address: string | null;
  risk_score: number;
  risk_level: "low" | "medium" | "high" | string;
  confidence: number;
  model_version: string;
  created_at: string;
}

export interface MLModelStatus {
  model_family: string;
  version: string;
  status: string;
  train_rows: number;
  metric_primary: number | null;
  metric_secondary: number | null;
  trained_at: string;
  activated_at: string | null;
}

export async function getTonerPredictions(printer_id?: string) {
  const params: Record<string, string> = {};
  if (printer_id) params.printer_id = printer_id;
  const { data } = await api.get<{ data: MLTonerPrediction[]; count: number }>("/ml/predictions/toner", { params });
  return data;
}

export async function getOfflineRiskPredictions(device_kind?: string) {
  const params: Record<string, string> = {};
  if (device_kind) params.device_kind = device_kind;
  const { data } = await api.get<{ data: MLOfflineRiskPrediction[]; count: number }>("/ml/predictions/offline-risk", {
    params,
  });
  return data;
}

export async function getMLModelStatus() {
  const { data } = await api.get<{ data: MLModelStatus[]; count: number }>("/ml/models/status");
  return data;
}

export async function runMLCycle() {
  const { data } = await api.post<{ message: string }>("/ml/run-cycle");
  return data;
}

// ── Cash registers ──

export interface CashRegister {
  id: string;
  kkm_number: string;
  store_code: string | null;
  serial_number: string | null;
  inventory_number: string | null;
  terminal_id_rs: string | null;
  terminal_id_sber: string | null;
  windows_version: string | null;
  kkm_type: "retail" | "shtrih";
  cash_number: string | null;
  hostname: string;
  comment: string | null;
  is_online: boolean | null;
  reachability_reason: "dns_unresolved" | "port_closed" | null;
  last_polled_at: string | null;
  created_at: string;
}

export interface CashRegistersResponse {
  data: CashRegister[];
  count: number;
}

export async function getCashRegisters(q?: string) {
  const params: Record<string, string> = {};
  if (q) params.q = q;
  const { data } = await api.get<CashRegistersResponse>("/cash-registers/", { params });
  return data;
}

export async function createCashRegister(payload: {
  kkm_number: string;
  store_code?: string;
  serial_number?: string;
  inventory_number?: string;
  terminal_id_rs?: string;
  terminal_id_sber?: string;
  windows_version?: string;
  kkm_type: "retail" | "shtrih";
  cash_number?: string;
  hostname: string;
  comment?: string;
}) {
  const { data } = await api.post<CashRegister>("/cash-registers/", payload);
  return data;
}

export async function updateCashRegister(id: string, payload: Partial<CashRegister>) {
  const { data } = await api.patch<CashRegister>(`/cash-registers/${id}`, payload);
  return data;
}

export async function deleteCashRegister(id: string) {
  await api.delete(`/cash-registers/${id}`);
}

export async function pollCashRegister(id: string) {
  const { data } = await api.post<CashRegister>(`/cash-registers/${id}/poll`);
  return data;
}

export async function pollAllCashRegisters() {
  const { data } = await api.post<CashRegistersResponse>("/cash-registers/poll-all");
  return data;
}

export function getCashRegistersExportUrl(q?: string) {
  const query = q ? `?q=${encodeURIComponent(q)}` : "";
  return `/api/v1/cash-registers/export${query}`;
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
  toner_black_name: string | null;
  toner_cyan_name: string | null;
  toner_magenta_name: string | null;
  toner_yellow_name: string | null;
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
  toner_black_name?: string;
  toner_cyan_name?: string;
  toner_magenta_name?: string;
  toner_yellow_name?: string;
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

export interface DiscoveredNetworkDevice {
  ip: string;
  mac: string | null;
  open_ports: number[];
  hostname: string | null;
  model_info: string | null;
  vendor: string | null;
  device_kind: string | null;
  is_known: boolean;
  known_device_id: string | null;
  ip_changed: boolean;
  old_ip: string | null;
}

export interface DiscoveryResultsResponse {
  progress: ScanProgress;
  devices: DiscoveredNetworkDevice[];
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

export async function startIconbitDiscoveryScan(subnet: string, ports: string = "8081,80,443") {
  const { data } = await api.post<ScanProgress>("/media-players/discover/scan", { subnet, ports });
  return data;
}

export async function getIconbitDiscoveryResults() {
  const { data } = await api.get<DiscoveryResultsResponse>("/media-players/discover/results");
  return data;
}

export async function addDiscoveredIconbit(payload: {
  ip_address: string;
  name?: string;
  model?: string;
  mac_address?: string;
}) {
  const { data } = await api.post<MediaPlayer>("/media-players/discover/add", payload);
  return data;
}

export async function updateDiscoveredIconbitIp(playerId: string, newIp: string, newMac?: string) {
  const params: Record<string, string> = { new_ip: newIp };
  if (newMac) params.new_mac = newMac;
  const { data } = await api.post<MediaPlayer>(`/media-players/discover/update-ip/${playerId}`, null, { params });
  return data;
}

export async function startSwitchDiscoveryScan(subnet: string, ports: string = "22,80,443") {
  const { data } = await api.post<ScanProgress>("/switches/discover/scan", { subnet, ports });
  return data;
}

export async function getSwitchDiscoveryResults() {
  const { data } = await api.get<DiscoveryResultsResponse>("/switches/discover/results");
  return data;
}

export async function addDiscoveredSwitch(payload: {
  ip_address: string;
  name?: string;
  hostname?: string;
  vendor?: string;
}) {
  const { data } = await api.post<NetworkSwitch>("/switches/discover/add", payload);
  return data;
}

export async function updateDiscoveredSwitchIp(switchId: string, newIp: string) {
  const { data } = await api.post<NetworkSwitch>(`/switches/discover/update-ip/${switchId}`, null, {
    params: { new_ip: newIp },
  });
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
  hostname?: string;
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

export async function rediscoverMediaPlayers() {
  const { data } = await api.post<MediaPlayersResponse>("/media-players/rediscover");
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
  state: string | null;
  position: number | null;
  duration: number | null;
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

// ── Network Switches ──

export interface NetworkSwitch {
  id: string;
  name: string;
  ip_address: string;
  ssh_username: string;
  ssh_port: number;
  ap_vlan: number;
  vendor: "cisco" | "dlink" | "generic";
  management_protocol: "snmp" | "ssh" | "snmp+ssh";
  snmp_version: "2c";
  snmp_community_ro: string;
  snmp_community_rw: string | null;
  model_info: string | null;
  ios_version: string | null;
  hostname: string | null;
  uptime: string | null;
  is_online: boolean | null;
  last_polled_at: string | null;
  created_at: string;
}

export interface NetworkSwitchesResponse {
  data: NetworkSwitch[];
  count: number;
}

export interface AccessPoint {
  mac_address: string;
  port: string;
  vlan: number;
  ip_address: string | null;
  cdp_name: string | null;
  cdp_platform: string | null;
  poe_power: string | null;
  poe_status: string | null;
}

export interface SwitchPort {
  port: string;
  if_index: number;
  description: string | null;
  admin_status: string | null;
  oper_status: string | null;
  status_text: string | null;
  vlan_text: string | null;
  duplex_text: string | null;
  speed_text: string | null;
  media_type: string | null;
  speed_mbps: number | null;
  duplex: string | null;
  vlan: number | null;
  port_mode: string | null;
  access_vlan: number | null;
  trunk_native_vlan: number | null;
  trunk_allowed_vlans: string | null;
  poe_enabled: boolean | null;
  poe_power_w: number | null;
  mac_count: number | null;
}

export interface SwitchPortsResponse {
  data: SwitchPort[];
  count: number;
}

export async function getSwitches(name?: string) {
  const params: Record<string, string> = {};
  if (name) params.name = name;
  const { data } = await api.get<NetworkSwitchesResponse>("/switches/", { params });
  return data;
}

export async function createSwitch(sw: {
  name: string;
  ip_address: string;
  ssh_username: string;
  ssh_password: string;
  enable_password: string;
  ssh_port: number;
  ap_vlan: number;
  vendor: "cisco" | "dlink" | "generic";
  management_protocol: "snmp" | "ssh" | "snmp+ssh";
  snmp_version: "2c";
  snmp_community_ro: string;
  snmp_community_rw?: string;
}) {
  const { data } = await api.post<NetworkSwitch>("/switches/", sw);
  return data;
}

export async function updateSwitch(id: string, sw: Record<string, unknown>) {
  const { data } = await api.patch<NetworkSwitch>(`/switches/${id}`, sw);
  return data;
}

export async function deleteSwitch(id: string) {
  await api.delete(`/switches/${id}`);
}

export async function pollSwitch(id: string) {
  const { data } = await api.post<NetworkSwitch>(`/switches/${id}/poll`);
  return data;
}

export async function pollAllSwitches() {
  await api.post("/switches/poll-all");
}

export async function getSwitchAPs(id: string) {
  const { data } = await api.get<AccessPoint[]>(`/switches/${id}/access-points`);
  return data;
}

export async function rebootAP(switchId: string, iface: string, method: string = "poe") {
  const { data } = await api.post(`/switches/${switchId}/reboot-ap`, { interface: iface, method });
  return data;
}

export async function getSwitchPorts(id: string, q?: string, skip = 0, limit = 100) {
  const params: Record<string, string | number> = { skip, limit };
  if (q) params.q = q;
  const { data } = await api.get<SwitchPortsResponse>(`/switches/${id}/ports`, { params });
  return data;
}

export async function setSwitchPortAdminState(id: string, port: string, admin_state: "up" | "down") {
  const encoded = encodeURIComponent(port);
  const { data } = await api.post(`/switches/${id}/ports/${encoded}/admin-state`, { admin_state });
  return data as { message: string };
}

export async function setSwitchPortDescription(id: string, port: string, description: string) {
  const encoded = encodeURIComponent(port);
  const { data } = await api.post(`/switches/${id}/ports/${encoded}/description`, { description });
  return data as { message: string };
}

export async function setSwitchPortVlan(id: string, port: string, vlan: number) {
  const encoded = encodeURIComponent(port);
  const { data } = await api.post(`/switches/${id}/ports/${encoded}/vlan`, { vlan });
  return data as { message: string };
}

export async function setSwitchPortPoe(id: string, port: string, action: "on" | "off" | "cycle") {
  const encoded = encodeURIComponent(port);
  const { data } = await api.post(`/switches/${id}/ports/${encoded}/poe`, { action });
  return data as { message: string };
}

export async function setSwitchPortMode(
  id: string,
  port: string,
  payload: {
    mode: "access" | "trunk";
    access_vlan?: number;
    native_vlan?: number;
    allowed_vlans?: string;
  },
) {
  const encoded = encodeURIComponent(port);
  const { data } = await api.post(`/switches/${id}/ports/${encoded}/mode`, payload);
  return data as { message: string };
}
