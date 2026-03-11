from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_worker_and_polling_service_do_not_import_api_routes_directly() -> None:
    worker_tasks = _read("app/worker/tasks.py")
    polling_main = _read("app/polling_service/main.py")

    assert "from app.api.routes import" not in worker_tasks
    assert "from app.api.routes import" not in polling_main


def test_discovery_does_not_import_private_scanner_helpers() -> None:
    discovery_service = _read("app/services/discovery.py")

    assert "_parse_arp_table" not in discovery_service
