from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter

from prometheus_client import Counter, Gauge, Histogram

auth_events_total = Counter(
    "infrascope_auth_events_total",
    "Authentication and token-validation events.",
    ["result", "reason"],
)

scanner_runs_total = Counter(
    "infrascope_scanner_runs_total",
    "Network scanner run outcomes.",
    ["result"],
)

scanner_duration_seconds = Histogram(
    "infrascope_scanner_duration_seconds",
    "Duration of scanner runs.",
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300),
)

scanner_devices_found_total = Counter(
    "infrascope_scanner_devices_found_total",
    "Number of discovered devices from scanner runs.",
)

printer_polls_total = Counter(
    "infrascope_printer_polls_total",
    "Printer polling outcomes.",
    ["mode", "printer_type", "result"],
)

media_player_polls_total = Counter(
    "infrascope_media_player_polls_total",
    "Media player polling outcomes.",
    ["mode", "device_type", "result"],
)

media_player_ops_total = Counter(
    "infrascope_media_player_ops_total",
    "Media player operation outcomes.",
    ["operation", "result"],
)

switch_ops_total = Counter(
    "infrascope_switch_ops_total",
    "Network switch operation outcomes.",
    ["operation", "result"],
)

snmp_operations_total = Counter(
    "infrascope_snmp_operations_total",
    "SNMP operation outcomes.",
    ["operation", "result", "reason"],
)

ssh_operations_total = Counter(
    "infrascope_ssh_operations_total",
    "SSH operation outcomes.",
    ["operation", "result", "reason"],
)

worker_tasks_enqueued_total = Counter(
    "infrascope_worker_tasks_enqueued_total",
    "Number of tasks enqueued for worker execution.",
    ["operation"],
)

worker_task_executions_total = Counter(
    "infrascope_worker_task_executions_total",
    "Worker task execution outcomes.",
    ["operation", "result"],
)

worker_task_duration_seconds = Histogram(
    "infrascope_worker_task_duration_seconds",
    "Duration of worker task execution.",
    ["operation"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300),
)

worker_tasks_in_progress = Gauge(
    "infrascope_worker_tasks_in_progress",
    "Current number of worker tasks in progress.",
    ["operation"],
)

worker_task_status_checks_total = Counter(
    "infrascope_worker_task_status_checks_total",
    "Task status API checks by state.",
    ["state"],
)

devices_total = Gauge(
    "infrascope_devices_total",
    "Total number of configured devices by kind.",
    ["kind"],
)

devices_online = Gauge(
    "infrascope_devices_online",
    "Number of currently online devices by kind.",
    ["kind"],
)


def set_device_counts(kind: str, total: int, online: int) -> None:
    devices_total.labels(kind=kind).set(max(total, 0))
    devices_online.labels(kind=kind).set(max(online, 0))


@contextmanager
def observe_duration(metric: Histogram):
    start = perf_counter()
    try:
        yield
    finally:
        metric.observe(max(perf_counter() - start, 0))

