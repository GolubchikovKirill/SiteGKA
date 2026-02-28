import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  type Edge,
  type Node,
  type NodeMouseHandler,
  type EdgeMouseHandler,
} from "reactflow";
import "reactflow/dist/style.css";
import {
  getServiceFlowMap,
  getServiceFlowTimeseries,
  type ServiceFlowEdge,
  type ServiceFlowNode,
  type ServiceFlowRecentEvent,
} from "../client";

const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  frontend: { x: 40, y: 210 },
  backend: { x: 300, y: 210 },
  worker: { x: 300, y: 410 },
  "polling-service": { x: 580, y: 90 },
  "discovery-service": { x: 580, y: 220 },
  "network-control-service": { x: 580, y: 350 },
  "ml-service": { x: 580, y: 480 },
  kafka: { x: 860, y: 180 },
  jaeger: { x: 860, y: 360 },
};

type SelectionState =
  | { kind: "node"; node: ServiceFlowNode }
  | { kind: "edge"; edge: ServiceFlowEdge }
  | null;

function formatRate(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "—";
  return value.toFixed(2);
}

function statusClass(status: string): string {
  if (status === "healthy") return "text-emerald-600";
  if (status === "degraded") return "text-amber-600";
  if (status === "down") return "text-rose-600";
  return "text-slate-500";
}

function edgeColor(status: string, transport: string): string {
  if (status === "down") return "#e11d48";
  if (status === "degraded") return "#d97706";
  if (transport === "kafka") return "#7c3aed";
  if (status === "healthy") return "#059669";
  return "#64748b";
}

function TimelineChart({
  points,
}: {
  points: Array<{ timestamp: string; req_rate: number | null; error_rate: number | null }>;
}) {
  const values = points.map((p) => p.req_rate ?? 0);
  const max = Math.max(1, ...values);
  const d = points
    .map((p, i) => {
      const x = (i / Math.max(points.length - 1, 1)) * 100;
      const y = 100 - ((p.req_rate ?? 0) / max) * 100;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <div className="rounded-xl border p-3 app-surface">
      <div className="mb-2 text-sm font-medium">Timeline (request rate)</div>
      <svg viewBox="0 0 100 100" className="h-28 w-full">
        <polyline fill="none" stroke="currentColor" strokeWidth="2" className="text-rose-600" points={d} />
      </svg>
    </div>
  );
}

export default function ServiceFlowMapPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [edgeTypeFilter, setEdgeTypeFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [traceId, setTraceId] = useState("");
  const [live, setLive] = useState(true);
  const [selection, setSelection] = useState<SelectionState>(null);

  const mapQuery = useQuery({
    queryKey: ["service-flow-map"],
    queryFn: () => getServiceFlowMap(),
    refetchInterval: live ? 15_000 : false,
  });

  const timeseriesQuery = useQuery({
    queryKey: [
      "service-flow-timeseries",
      selection?.kind,
      selection?.kind === "node" ? selection.node.id : "",
      selection?.kind === "edge" ? selection.edge.source : "",
      selection?.kind === "edge" ? selection.edge.target : "",
    ],
    queryFn: () =>
      getServiceFlowTimeseries(
        selection?.kind === "edge"
          ? { source: selection.edge.source, target: selection.edge.target, minutes: 90, step_seconds: 20 }
          : { service: selection?.kind === "node" ? selection.node.id : "backend", minutes: 90, step_seconds: 20 },
      ),
    enabled: !!selection,
    refetchInterval: live ? 20_000 : false,
  });

  const filteredNodes = useMemo(() => {
    const nodes = mapQuery.data?.nodes ?? [];
    return nodes.filter((node) => {
      const byStatus = statusFilter === "all" || node.status === statusFilter;
      const bySearch =
        search.trim().length === 0 ||
        node.id.toLowerCase().includes(search.toLowerCase()) ||
        node.label.toLowerCase().includes(search.toLowerCase());
      return byStatus && bySearch;
    });
  }, [mapQuery.data?.nodes, search, statusFilter]);

  const visibleNodeIds = useMemo(() => new Set(filteredNodes.map((node) => node.id)), [filteredNodes]);

  const filteredEdges = useMemo(() => {
    const edges = mapQuery.data?.edges ?? [];
    return edges.filter((edge) => {
      const byTransport = edgeTypeFilter === "all" || edge.transport === edgeTypeFilter;
      const byNodes = visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target);
      return byTransport && byNodes;
    });
  }, [edgeTypeFilter, mapQuery.data?.edges, visibleNodeIds]);

  const recentEvents = useMemo(() => {
    const events = mapQuery.data?.recent_events ?? [];
    if (!traceId.trim()) return events.slice(0, 12);
    return events
      .filter((event) => (event.trace_id ?? "").toLowerCase().includes(traceId.toLowerCase()))
      .slice(0, 12);
  }, [mapQuery.data?.recent_events, traceId]);

  const flowNodes: Node[] = useMemo(
    () =>
      filteredNodes.map((node) => {
        const position = NODE_POSITIONS[node.id] ?? { x: 120, y: 120 };
        const label = `${node.label}\nRPS ${formatRate(node.req_rate)} | ERR ${formatRate(node.error_rate)}`;
        return {
          id: node.id,
          data: { label },
          position,
          sourcePosition: "right",
          targetPosition: "left",
          style: {
            borderRadius: 14,
            border: "1px solid #d1d5db",
            fontSize: 12,
            width: 190,
            whiteSpace: "pre-line",
            background:
              node.status === "healthy"
                ? "#ecfdf5"
                : node.status === "degraded"
                  ? "#fffbeb"
                  : node.status === "down"
                    ? "#fff1f2"
                    : "#f8fafc",
          },
        };
      }),
    [filteredNodes],
  );

  const flowEdges: Edge[] = useMemo(
    () =>
      filteredEdges.map((edge) => ({
        id: `${edge.source}-${edge.target}-${edge.operation}`,
        source: edge.source,
        target: edge.target,
        label: `${edge.transport.toUpperCase()} | ${formatRate(edge.req_rate)} rps`,
        labelStyle: { fontSize: 11 },
        markerEnd: { type: MarkerType.ArrowClosed },
        style: {
          stroke: edgeColor(edge.status, edge.transport),
          strokeWidth: Math.max(1.5, Math.min(8, (edge.req_rate ?? 0) + 1)),
        },
      })),
    [filteredEdges],
  );

  const onNodeClick: NodeMouseHandler = (_evt, clickedNode) => {
    const node = filteredNodes.find((item) => item.id === clickedNode.id);
    if (node) setSelection({ kind: "node", node });
  };

  const onEdgeClick: EdgeMouseHandler = (_evt, clickedEdge) => {
    const edge = filteredEdges.find((item) => `${item.source}-${item.target}-${item.operation}` === clickedEdge.id);
    if (edge) setSelection({ kind: "edge", edge });
  };

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border p-4 app-surface">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Service Flow Map</h1>
            <p className="text-sm text-slate-500">Карта связей сервисов, ошибок и нагрузки в реальном времени</p>
          </div>
          <button className="app-btn-secondary rounded-lg border px-3 py-2 text-sm" onClick={() => setLive((v) => !v)}>
            {live ? "Live ON" : "Live OFF"}
          </button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-xl border px-3 py-2 text-sm app-input"
          placeholder="Поиск сервиса"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-xl border px-3 py-2 text-sm app-input"
        >
          <option value="all">Все статусы</option>
          <option value="healthy">Healthy</option>
          <option value="degraded">Degraded</option>
          <option value="down">Down</option>
          <option value="unknown">Unknown</option>
        </select>
        <select
          value={edgeTypeFilter}
          onChange={(e) => setEdgeTypeFilter(e.target.value)}
          className="rounded-xl border px-3 py-2 text-sm app-input"
        >
          <option value="all">Все связи</option>
          <option value="http">HTTP</option>
          <option value="kafka">Kafka</option>
        </select>
        <input
          value={traceId}
          onChange={(e) => setTraceId(e.target.value)}
          className="rounded-xl border px-3 py-2 text-sm app-input"
          placeholder="Фильтр по trace_id"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="rounded-2xl border p-3 app-surface">
          <div className="mb-2 text-xs text-slate-500">
            Последнее обновление: {mapQuery.data?.generated_at ? new Date(mapQuery.data.generated_at).toLocaleString() : "—"}
          </div>
          <div className="h-[620px] w-full rounded-xl border">
            <ReactFlow nodes={flowNodes} edges={flowEdges} fitView onNodeClick={onNodeClick} onEdgeClick={onEdgeClick}>
              <Background />
              <Controls />
              <MiniMap />
            </ReactFlow>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border p-4 app-surface">
            <div className="mb-2 text-sm font-semibold">Выбранный элемент</div>
            {!selection && <div className="text-sm text-slate-500">Кликни на node/edge на карте</div>}
            {selection?.kind === "node" && (
              <div className="space-y-1 text-sm">
                <div className="font-medium">{selection.node.label}</div>
                <div className={statusClass(selection.node.status)}>Status: {selection.node.status}</div>
                <div>RPS: {formatRate(selection.node.req_rate)}</div>
                <div>ERR: {formatRate(selection.node.error_rate)}</div>
                <div>P95: {selection.node.p95_latency_ms ? `${selection.node.p95_latency_ms.toFixed(1)} ms` : "—"}</div>
                <div className="pt-2 space-y-1">
                  {selection.node.links.map((link) => (
                    <a key={link.url} href={link.url} target="_blank" rel="noreferrer" className="block text-rose-600 underline">
                      {link.label}
                    </a>
                  ))}
                </div>
              </div>
            )}
            {selection?.kind === "edge" && (
              <div className="space-y-1 text-sm">
                <div className="font-medium">
                  {selection.edge.source} → {selection.edge.target}
                </div>
                <div className={statusClass(selection.edge.status)}>Status: {selection.edge.status}</div>
                <div>Transport: {selection.edge.transport}</div>
                <div>Operation: {selection.edge.operation}</div>
                <div>RPS: {formatRate(selection.edge.req_rate)}</div>
                <div>ERR: {formatRate(selection.edge.error_rate)}</div>
                <div>P95: {selection.edge.p95_latency_ms ? `${selection.edge.p95_latency_ms.toFixed(1)} ms` : "—"}</div>
              </div>
            )}
          </div>

          <TimelineChart points={timeseriesQuery.data?.points ?? []} />

          <div className="rounded-2xl border p-4 app-surface">
            <div className="mb-2 text-sm font-semibold">Recent Events</div>
            <div className="max-h-72 space-y-2 overflow-auto pr-1">
              {recentEvents.map((event: ServiceFlowRecentEvent) => (
                <div key={event.id} className="rounded-lg border p-2 text-xs">
                  <div className="flex justify-between gap-2">
                    <span className={statusClass(event.severity)}>{event.severity}</span>
                    <span className="text-slate-500">{new Date(event.created_at).toLocaleTimeString()}</span>
                  </div>
                  <div className="font-medium">{event.event_type}</div>
                  <div className="text-slate-600">{event.message}</div>
                  {event.trace_id && <div className="text-slate-500">trace_id: {event.trace_id}</div>}
                </div>
              ))}
              {!recentEvents.length && <div className="text-xs text-slate-500">Нет событий по текущему фильтру</div>}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
