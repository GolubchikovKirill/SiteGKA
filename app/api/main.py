from fastapi import APIRouter

from app.api.routes import auth, media_players, printers, scanner, switches, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(users.router, prefix="/users")
api_router.include_router(printers.router, prefix="/printers")
api_router.include_router(scanner.router, prefix="/scanner")
api_router.include_router(media_players.router, prefix="/media-players")
api_router.include_router(switches.router, prefix="/switches")
