"""Backward-compatible ORM model exports.

Concrete model definitions live in `app.domains.*.models`. Keep this module as
the stable import surface for existing route, service, test, and Alembic code
while the codebase moves toward domain-local imports.
"""

from app.domains.identity.models import User
from app.domains.inventory.models import Computer, MediaPlayer, NetworkSwitch, Printer
from app.domains.ml.models import (
    MLFeatureSnapshot,
    MLModelRegistry,
    MLOfflineRiskPrediction,
    MLTonerPrediction,
)
from app.domains.operations.models import AppSetting, CashRegister, EventLog

__all__ = [
    "AppSetting",
    "CashRegister",
    "Computer",
    "EventLog",
    "MediaPlayer",
    "MLFeatureSnapshot",
    "MLModelRegistry",
    "MLOfflineRiskPrediction",
    "MLTonerPrediction",
    "NetworkSwitch",
    "Printer",
    "User",
]
