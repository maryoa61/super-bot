from aiogram import Router

from config import settings
from handlers.start import router as start_router
from handlers.vps import router as vps_router
from handlers.wallet import router as wallet_router


def get_root_router() -> Router:
    root = Router(name="root")
    root.include_router(start_router)
    root.include_router(wallet_router)
    if settings.VPS_STORE_ENABLED:
        root.include_router(vps_router)
    return root
