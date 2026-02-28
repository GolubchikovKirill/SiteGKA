from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.models import EventLog
from app.schemas import (
    ServiceFlowEdgePublic,
    ServiceFlowLinkPublic,
    ServiceFlowMapPublic,
    ServiceFlowNodePublic,
    ServiceFlowRecentEventPublic,
    ServiceFlowTimeseriesPointPublic,
    ServiceFlowTimeseriesPublic,
)

_NODE_DEFS = [
    {"id": "frontend", "label": "Frontend", "kind": "gateway", "job": ""},
    {"id": "backend", "label": "API Gateway", "kind": "gateway", "job": "backend"},
    {"id": "worker", "label": "Worker", "kind": "worker", "job": "worker"},
    {"id": "polling-service", "label": "Polling", "kind": "service", "job": "polling-service"},
    {"id": "discovery-service", "label": "Discovery", "kind": "service", "job": "discovery-service"},
    {"id": "network-control-service", "label": "Network Control", "kind": "service", "job": "network-control-service"},
    {"id": "ml-service", "label": "ML Service", "kind": "service", "job": "ml-service"},
    {"id": "kafka", "label": "Kafka", "kind": "infra", "job": ""},
    {"id": "jaeger", "label": "Jaeger", "kind": "infra", "job": ""},
]

_DEFAULT_EDGES = [
    ("frontend", "backend", "http", "ui requests"),
    ("backend", "polling-service", "http", "internal proxy"),
    ("backend", "discovery-service", "http", "internal proxy"),
    ("backend", "network-control-service", "http", "internal proxy"),
    ("backend", "ml-service", "http", "ml calls"),
    ("backend", "kafka", "kafka", "event publish"),
    ("worker", "polling-service", "http", "task dispatch"),
    ("worker", "discovery-service", "http", "task dispatch"),
    ("worker", "ml-service", "http", "task dispatch"),
]


def _query_scalar(query: str) -> float | None:
    try:
        with httpx.Client(timeout=2.0) as client:
            res = client.get(f"{settings.PROMETHEUS_API_URL.rstrip('/')}/api/v1/query", params={"query": query})
        res.raise_for_status()
        payload = res.json()
        result = payload.get("data", {}).get("result") or []
        if not result:
            return None
        return float(result[0]["value"][1])
    except Exception:
        return None


def _query_vector(query: str) -> list[dict[str, Any]]:
    try:
        with httpx.Client(timeout=2.0) as client:
            res = client.get(f"{settings.PROMETHEUS_API_URL.rstrip('/')}/api/v1/query", params={"query": query})
        res.raise_for_status()
        payload = res.json()
        return list(payload.get("data", {}).get("result") or [])
    except Exception:
        return []


def _query_range(query: str, *, start_ts: int, end_ts: int, step_seconds: int) -> list[dict[str, Any]]:
    try:
        with httpx.Client(timeout=3.0) as client:
            res = client.get(
                f"{settings.PROMETHEUS_API_URL.rstrip('/')}/api/v1/query_range",
                params={"query": query, "start": start_ts, "end": end_ts, "step": step_seconds},
            )
        res.raise_for_status()
        payload = res.json()
        return list(payload.get("data", {}).get("result") or [])
    except Exception:
        return []


def _node_status(up: float | None, req: float | None, err: float | None) -> str:
    if up is not None and up < 0.5:
        return "down"
    if req is not None and req > 0 and err is not None and (err / max(req, 1e-9)) >= 0.05:
        return "degraded"
    if up is None and req is None and err is None:
        return "unknown"
    return "healthy"


def _edge_status(req: float | None, err: float | None) -> str:
    if req is None and err is None:
        return "unknown"
    if req is not None and req > 0 and err is not None and (err / max(req, 1e-9)) >= 0.05:
        return "degraded"
    return "healthy"


def _node_links(node_id: str) -> list[ServiceFlowLinkPublic]:
    links = [
        ServiceFlowLinkPublic(
            label="Jaeger traces",
            url=f"{settings.JAEGER_UI_URL.rstrip('/')}/search?service={node_id}",
        )
    ]
    if node_id in {"backend", "polling-service", "discovery-service", "network-control-service", "ml-service", "worker"}:
        links.append(
            ServiceFlowLinkPublic(
                label="Prometheus metrics",
                url=f"{settings.PROMETHEUS_API_URL.rstrip('/')}/graph",
            )
        )
    if node_id == "kafka":
        links.append(
            ServiceFlowLinkPublic(
                label="Kafka UI",
                url=f"{settings.KAFKA_UI_URL.rstrip('/')}/ui/clusters/infrascope/all-topics/infrascope.events/messages",
            )
        )
    return links


def _build_nodes() -> list[ServiceFlowNodePublic]:
    nodes: list[ServiceFlowNodePublic] = []
    now = datetime.now(UTC)
    for node in _NODE_DEFS:
        job = node["job"]
        req_rate: float | None = None
        err_rate: float | None = None
        p95_latency_ms: float | None = None
        up: float | None = None
        if job:
            if job == "worker":
                req_rate = _query_scalar("sum(rate(infrascope_worker_task_executions_total[5m]))")
                err_rate = _query_scalar('sum(rate(infrascope_worker_task_executions_total{result="error"}[5m]))')
                p95 = _query_scalar(
                    "histogram_quantile(0.95, sum(rate(infrascope_worker_task_duration_seconds_bucket[5m])) by (le))"
                )
                p95_latency_ms = None if p95 is None else p95 * 1000
                up = _query_scalar('avg(up{job="worker"})')
            else:
                req_rate = _query_scalar(f'sum(rate(http_requests_total{{job="{job}"}}[5m]))')
                err_rate = _query_scalar(f'sum(rate(http_requests_total{{job="{job}",status=~"5.."}}[5m]))')
                p95 = _query_scalar(
                    f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{job="{job}"}}[5m])) by (le))'
                )
                p95_latency_ms = None if p95 is None else p95 * 1000
                up = _query_scalar(f'avg(up{{job="{job}"}})')
        status = _node_status(up, req_rate, err_rate)
        nodes.append(
            ServiceFlowNodePublic(
                id=node["id"],
                label=node["label"],
                kind=node["kind"],
                status=status,
                req_rate=req_rate,
                error_rate=err_rate,
                p95_latency_ms=p95_latency_ms,
                last_seen=now if status in {"healthy", "degraded"} else None,
                links=_node_links(node["id"]),
            )
        )
    return nodes


def _build_edges() -> list[ServiceFlowEdgePublic]:
    vector = _query_vector(
        "sum(rate(infrascope_service_edge_requests_total[5m])) by (source_service,target_service,transport,operation,result)"
    )
    latency_vector = _query_vector(
        "histogram_quantile(0.95, sum(rate(infrascope_service_edge_request_duration_seconds_bucket[5m])) "
        "by (le,source_service,target_service,transport,operation))"
    )
    edge_map: dict[tuple[str, str, str, str], dict[str, float]] = {}
    for row in vector:
        metric = row.get("metric", {})
        key = (
            metric.get("source_service", "unknown"),
            metric.get("target_service", "unknown"),
            metric.get("transport", "http"),
            metric.get("operation", "unknown"),
        )
        edge_map.setdefault(key, {"req_rate": 0.0, "error_rate": 0.0})
        value = float(row.get("value", [0, 0])[1])
        edge_map[key]["req_rate"] += value
        if metric.get("result") == "error":
            edge_map[key]["error_rate"] += value

    p95_map: dict[tuple[str, str, str, str], float] = {}
    for row in latency_vector:
        metric = row.get("metric", {})
        key = (
            metric.get("source_service", "unknown"),
            metric.get("target_service", "unknown"),
            metric.get("transport", "http"),
            metric.get("operation", "unknown"),
        )
        p95_map[key] = float(row.get("value", [0, 0])[1]) * 1000

    for source, target, transport, operation in _DEFAULT_EDGES:
        edge_map.setdefault((source, target, transport, operation), {"req_rate": 0.0, "error_rate": 0.0})

    edges: list[ServiceFlowEdgePublic] = []
    for (source, target, transport, operation), values in edge_map.items():
        req = values.get("req_rate")
        err = values.get("error_rate")
        edges.append(
            ServiceFlowEdgePublic(
                source=source,
                target=target,
                transport=transport,
                operation=operation,
                status=_edge_status(req, err),
                req_rate=req,
                error_rate=err,
                p95_latency_ms=p95_map.get((source, target, transport, operation)),
            )
        )
    return edges


def build_service_flow_map(session: Session) -> ServiceFlowMapPublic:
    events = session.exec(select(EventLog).order_by(EventLog.created_at.desc()).limit(30)).all()
    return ServiceFlowMapPublic(
        generated_at=datetime.now(UTC),
        nodes=_build_nodes(),
        edges=_build_edges(),
        recent_events=[
            ServiceFlowRecentEventPublic(
                id=e.id,
                created_at=e.created_at,
                severity=e.severity,
                category=e.category,
                event_type=e.event_type,
                message=e.message,
                device_kind=e.device_kind,
                device_name=e.device_name,
                ip_address=e.ip_address,
                trace_id=None,
            )
            for e in events
        ],
    )


def _extract_timeseries_points(
    req_series: list[dict[str, Any]],
    err_series: list[dict[str, Any]],
    p95_series: list[dict[str, Any]],
) -> list[ServiceFlowTimeseriesPointPublic]:
    req_values = req_series[0].get("values", []) if req_series else []
    err_values = err_series[0].get("values", []) if err_series else []
    p95_values = p95_series[0].get("values", []) if p95_series else []
    points: list[ServiceFlowTimeseriesPointPublic] = []
    for idx, value in enumerate(req_values):
        ts = datetime.fromtimestamp(float(value[0]), tz=UTC)
        req = float(value[1])
        err = float(err_values[idx][1]) if idx < len(err_values) else None
        p95 = float(p95_values[idx][1]) * 1000 if idx < len(p95_values) else None
        points.append(ServiceFlowTimeseriesPointPublic(timestamp=ts, req_rate=req, error_rate=err, p95_latency_ms=p95))
    if points:
        return points
    for idx, value in enumerate(err_values):
        ts = datetime.fromtimestamp(float(value[0]), tz=UTC)
        err = float(value[1])
        p95 = float(p95_values[idx][1]) * 1000 if idx < len(p95_values) else None
        points.append(ServiceFlowTimeseriesPointPublic(timestamp=ts, req_rate=None, error_rate=err, p95_latency_ms=p95))
    return points


def build_service_flow_timeseries(
    *,
    service: str | None,
    source: str | None,
    target: str | None,
    minutes: int,
    step_seconds: int,
) -> ServiceFlowTimeseriesPublic:
    now_ts = int(datetime.now(UTC).timestamp())
    start_ts = now_ts - max(minutes, 1) * 60

    if source and target:
        selector = f'source_service="{source}",target_service="{target}"'
        req_query = (
            "sum(rate(infrascope_service_edge_requests_total"
            f"{{{selector}}}[2m]))"
        )
        err_query = (
            "sum(rate(infrascope_service_edge_requests_total"
            f"{{{selector},result=\"error\"}}[2m]))"
        )
        p95_query = (
            "histogram_quantile(0.95, sum(rate(infrascope_service_edge_request_duration_seconds_bucket"
            f"{{{selector}}}[2m])) by (le))"
        )
        entity = f"edge:{source}->{target}"
    else:
        job = service or "backend"
        if job == "worker":
            req_query = "sum(rate(infrascope_worker_task_executions_total[2m]))"
            err_query = 'sum(rate(infrascope_worker_task_executions_total{result="error"}[2m]))'
            p95_query = "histogram_quantile(0.95, sum(rate(infrascope_worker_task_duration_seconds_bucket[2m])) by (le))"
        else:
            req_query = f'sum(rate(http_requests_total{{job="{job}"}}[2m]))'
            err_query = f'sum(rate(http_requests_total{{job="{job}",status=~"5.."}}[2m]))'
            p95_query = (
                "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket"
                f'{{job="{job}"}}[2m])) by (le))'
            )
        entity = f"service:{job}"

    req_series = _query_range(req_query, start_ts=start_ts, end_ts=now_ts, step_seconds=max(step_seconds, 5))
    err_series = _query_range(err_query, start_ts=start_ts, end_ts=now_ts, step_seconds=max(step_seconds, 5))
    p95_series = _query_range(p95_query, start_ts=start_ts, end_ts=now_ts, step_seconds=max(step_seconds, 5))
    return ServiceFlowTimeseriesPublic(entity=entity, points=_extract_timeseries_points(req_series, err_series, p95_series))
