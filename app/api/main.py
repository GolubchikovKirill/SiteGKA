from fastapi import APIRouter

from app.api.routes import (
    auth,
    cash_registers,
    logs,
    media_players,
    ml,
    printers,
    scanner,
    support_tools,
    switches,
    tasks,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(users.router, prefix="/users")
api_router.include_router(printers.router, prefix="/printers")
api_router.include_router(scanner.router, prefix="/scanner")
api_router.include_router(media_players.router, prefix="/media-players")
api_router.include_router(switches.router, prefix="/switches")
api_router.include_router(cash_registers.router, prefix="/cash-registers")
api_router.include_router(ml.router, prefix="/ml")
api_router.include_router(logs.router, prefix="/logs")
api_router.include_router(support_tools.router, prefix="/support-tools")
api_router.include_router(tasks.router, prefix="/tasks")
