from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from time import perf_counter

from celery import shared_task
from sqlmodel import Session, select

from app.api.routes import media_players as media_routes
from app.api.routes import printers as printer_routes
from app.api.routes import switches as switch_routes
from app.core.db import engine
from app.models import MediaPlayer, NetworkSwitch, Printer
from app.observability.metrics import (
    worker_task_duration_seconds,
    worker_task_executions_total,
    worker_tasks_in_progress,
)
from app.services.scanner import scan_subnet


def _task_started(operation: str) -> float:
    worker_tasks_in_progress.labels(operation=operation).inc()
    return perf_counter()


def _task_finished(operation: str, started_at: float, result: str) -> None:
    worker_tasks_in_progress.labels(operation=operation).dec()
    worker_task_executions_total.labels(operation=operation, result=result).inc()
    worker_task_duration_seconds.labels(operation=operation).observe(max(perf_counter() - started_at, 0))


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    name="tasks.scan_network",
)
def scan_network_task(self, subnet: str, ports: str) -> dict:
    operation = "scan_network"
    started_at = _task_started(operation)
    try:
        with Session(engine) as session:
            printers = session.exec(select(Printer)).all()
            known = [
                {
                    "id": str(p.id),
                    "ip_address": p.ip_address,
                    "mac_address": p.mac_address,
                    "store_name": p.store_name,
                }
                for p in printers
            ]
        devices = asyncio.run(scan_subnet(subnet, ports, known))
        payload = {
            "task_id": self.request.id,
            "operation": operation,
            "subnet": subnet,
            "ports": ports,
            "found_devices": len(devices),
        }
        _task_finished(operation, started_at, "success")
        return payload
    except Exception:
        _task_finished(operation, started_at, "error")
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    name="tasks.poll_all_printers",
)
def poll_all_printers_task(self, printer_type: str = "laser") -> dict:
    operation = "poll_all_printers"
    started_at = _task_started(operation)
    try:
        with Session(engine) as session:
            asyncio.run(printer_routes.poll_all_printers(session=session, current_user=None, printer_type=printer_type))
            all_printers = session.exec(select(Printer).where(Printer.printer_type == printer_type)).all()
        payload = {
            "task_id": self.request.id,
            "operation": operation,
            "printer_type": printer_type,
            "total": len(all_printers),
            "online": sum(1 for p in all_printers if p.is_online),
            "finished_at": datetime.now(UTC).isoformat(),
        }
        _task_finished(operation, started_at, "success")
        return payload
    except Exception:
        _task_finished(operation, started_at, "error")
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    name="tasks.poll_all_media_players",
)
def poll_all_media_players_task(self, device_type: str | None = None) -> dict:
    operation = "poll_all_media_players"
    started_at = _task_started(operation)
    try:
        with Session(engine) as session:
            asyncio.run(
                media_routes.poll_all_players(
                    session=session,
                    current_user=None,
                    device_type=device_type,
                )
            )
            statement = select(MediaPlayer)
            if device_type:
                statement = statement.where(MediaPlayer.device_type == device_type)
            players = session.exec(statement).all()
        payload = {
            "task_id": self.request.id,
            "operation": operation,
            "device_type": device_type,
            "total": len(players),
            "online": sum(1 for p in players if p.is_online),
            "finished_at": datetime.now(UTC).isoformat(),
        }
        _task_finished(operation, started_at, "success")
        return payload
    except Exception:
        _task_finished(operation, started_at, "error")
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    name="tasks.poll_switch",
)
def poll_switch_task(self, switch_id: str) -> dict:
    operation = "poll_switch"
    started_at = _task_started(operation)
    try:
        switch_uuid = uuid.UUID(switch_id)
        with Session(engine) as session:
            sw = asyncio.run(switch_routes.poll_switch(switch_id=switch_uuid, session=session, current_user=None))
        payload = {
            "task_id": self.request.id,
            "operation": operation,
            "switch_id": switch_id,
            "is_online": bool(sw.is_online),
            "hostname": sw.hostname,
            "finished_at": datetime.now(UTC).isoformat(),
        }
        _task_finished(operation, started_at, "success")
        return payload
    except Exception:
        _task_finished(operation, started_at, "error")
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    name="tasks.poll_all_switches",
)
def poll_all_switches_task(self) -> dict:
    operation = "poll_all_switches"
    started_at = _task_started(operation)
    try:
        results: list[dict] = []
        with Session(engine) as session:
            switches = session.exec(select(NetworkSwitch)).all()
            for sw in switches:
                updated = asyncio.run(switch_routes.poll_switch(switch_id=sw.id, session=session, current_user=None))
                results.append(
                    {
                        "switch_id": str(updated.id),
                        "name": updated.name,
                        "is_online": bool(updated.is_online),
                    }
                )
        payload = {
            "task_id": self.request.id,
            "operation": operation,
            "total": len(results),
            "online": sum(1 for r in results if r["is_online"]),
            "switches": results,
            "finished_at": datetime.now(UTC).isoformat(),
        }
        _task_finished(operation, started_at, "success")
        return payload
    except Exception:
        _task_finished(operation, started_at, "error")
        raise

