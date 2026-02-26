import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { NetworkSwitch, SwitchPort } from "../client";
import {
  getSwitchPorts,
  setSwitchPortAdminState,
  setSwitchPortDescription,
  setSwitchPortPoe,
  setSwitchPortVlan,
} from "../client";

interface Props {
  sw: NetworkSwitch;
  isSuperuser: boolean;
  onClose: () => void;
}

function formatStatus(value: string | null) {
  if (!value) return "—";
  if (value === "up") return "UP";
  if (value === "down") return "DOWN";
  return value;
}

export default function SwitchPortsTable({ sw, isSuperuser, onClose }: Props) {
  const [q, setQ] = useState("");
  const [descDraft, setDescDraft] = useState<Record<string, string>>({});
  const [vlanDraft, setVlanDraft] = useState<Record<string, string>>({});
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["switch-ports", sw.id, q],
    queryFn: () => getSwitchPorts(sw.id, q || undefined),
  });

  const rows = data?.data ?? [];
  const key = useMemo(() => ["switch-ports", sw.id, q] as const, [sw.id, q]);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: key });
  };

  const adminMut = useMutation({
    mutationFn: ({ port, state }: { port: string; state: "up" | "down" }) =>
      setSwitchPortAdminState(sw.id, port, state),
    onSettled: refresh,
  });
  const descMut = useMutation({
    mutationFn: ({ port, description }: { port: string; description: string }) =>
      setSwitchPortDescription(sw.id, port, description),
    onSettled: refresh,
  });
  const vlanMut = useMutation({
    mutationFn: ({ port, vlan }: { port: string; vlan: number }) => setSwitchPortVlan(sw.id, port, vlan),
    onSettled: refresh,
  });
  const poeMut = useMutation({
    mutationFn: ({ port, action }: { port: string; action: "on" | "off" | "cycle" }) =>
      setSwitchPortPoe(sw.id, port, action),
    onSettled: refresh,
  });

  const saveDescription = (row: SwitchPort) => {
    const draft = (descDraft[row.port] ?? row.description ?? "").trim();
    descMut.mutate({ port: row.port, description: draft });
  };
  const saveVlan = (row: SwitchPort) => {
    const value = Number(vlanDraft[row.port] ?? row.vlan ?? 1);
    if (Number.isNaN(value) || value < 1 || value > 4094) return;
    vlanMut.mutate({ port: row.port, vlan: value });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl w-full max-w-7xl max-h-[90vh] overflow-hidden border border-gray-200 shadow-xl">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Порты: {sw.name}</h3>
            <p className="text-xs text-gray-500">{sw.ip_address} · {sw.vendor.toUpperCase()}</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Фильтр по порту/описанию"
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm w-64"
            />
            <button onClick={onClose} className="px-3 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">
              Закрыть
            </button>
          </div>
        </div>
        <div className="overflow-auto max-h-[75vh]">
          {isLoading ? (
            <div className="p-8 text-sm text-gray-500 text-center">Загрузка портов...</div>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-gray-50 sticky top-0 z-10">
                <tr className="text-left text-gray-600">
                  <th className="px-3 py-2">Порт</th>
                  <th className="px-3 py-2">Admin/Oper</th>
                  <th className="px-3 py-2">VLAN</th>
                  <th className="px-3 py-2">Speed</th>
                  <th className="px-3 py-2">PoE</th>
                  <th className="px-3 py-2">Описание</th>
                  <th className="px-3 py-2">Операции</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.port} className="border-t border-gray-100 align-top">
                    <td className="px-3 py-2 font-mono">{row.port}</td>
                    <td className="px-3 py-2">{formatStatus(row.admin_status)} / {formatStatus(row.oper_status)}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        <input
                          value={vlanDraft[row.port] ?? String(row.vlan ?? "")}
                          onChange={(e) => setVlanDraft((prev) => ({ ...prev, [row.port]: e.target.value }))}
                          className="w-16 rounded border border-gray-300 px-2 py-1 text-xs"
                        />
                        {isSuperuser && (
                          <button
                            onClick={() => saveVlan(row)}
                            className="px-2 py-1 rounded border border-gray-300 hover:bg-gray-50"
                          >
                            Save
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2">{row.speed_mbps ? `${row.speed_mbps} Mbps` : "—"}</td>
                    <td className="px-3 py-2">
                      <div>{row.poe_enabled === null ? "—" : row.poe_enabled ? "on" : "off"}</div>
                      <div className="text-gray-400">{row.poe_power_w ?? "—"} W</div>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        <input
                          value={descDraft[row.port] ?? row.description ?? ""}
                          onChange={(e) => setDescDraft((prev) => ({ ...prev, [row.port]: e.target.value }))}
                          className="w-52 rounded border border-gray-300 px-2 py-1 text-xs"
                        />
                        {isSuperuser && (
                          <button
                            onClick={() => saveDescription(row)}
                            className="px-2 py-1 rounded border border-gray-300 hover:bg-gray-50"
                          >
                            Save
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      {isSuperuser ? (
                        <div className="flex flex-wrap gap-1">
                          <button
                            onClick={() => adminMut.mutate({ port: row.port, state: "up" })}
                            className="px-2 py-1 rounded border border-green-200 text-green-700 hover:bg-green-50"
                          >
                            Up
                          </button>
                          <button
                            onClick={() => adminMut.mutate({ port: row.port, state: "down" })}
                            className="px-2 py-1 rounded border border-red-200 text-red-700 hover:bg-red-50"
                          >
                            Down
                          </button>
                          <button
                            onClick={() => poeMut.mutate({ port: row.port, action: "cycle" })}
                            className="px-2 py-1 rounded border border-amber-200 text-amber-700 hover:bg-amber-50"
                          >
                            PoE cycle
                          </button>
                          <button
                            onClick={() => poeMut.mutate({ port: row.port, action: "on" })}
                            className="px-2 py-1 rounded border border-indigo-200 text-indigo-700 hover:bg-indigo-50"
                          >
                            PoE on
                          </button>
                          <button
                            onClick={() => poeMut.mutate({ port: row.port, action: "off" })}
                            className="px-2 py-1 rounded border border-gray-300 text-gray-700 hover:bg-gray-50"
                          >
                            PoE off
                          </button>
                        </div>
                      ) : (
                        <span className="text-gray-400">read-only</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
