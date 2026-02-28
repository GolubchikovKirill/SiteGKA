from __future__ import annotations

import json
import logging
from threading import Lock
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_PRODUCER = None
_LOCK = Lock()


def _get_producer():
    if not settings.KAFKA_ENABLED:
        return None
    global _PRODUCER
    if _PRODUCER is not None:
        return _PRODUCER
    with _LOCK:
        if _PRODUCER is not None:
            return _PRODUCER
        try:
            from kafka import KafkaProducer

            _PRODUCER = KafkaProducer(
                bootstrap_servers=[
                    server.strip()
                    for server in settings.KAFKA_BOOTSTRAP_SERVERS.split(",")
                    if server.strip()
                ],
                value_serializer=lambda v: json.dumps(v, ensure_ascii=True).encode("utf-8"),
                retries=0,
                acks=1,
                linger_ms=20,
                request_timeout_ms=1500,
                max_block_ms=1000,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Kafka producer init failed: %s", exc)
            _PRODUCER = None
    return _PRODUCER


def publish_event(payload: dict[str, Any]) -> None:
    producer = _get_producer()
    if producer is None:
        return
    try:
        producer.send(settings.KAFKA_EVENT_TOPIC, payload)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Kafka event publish failed: %s", exc)
