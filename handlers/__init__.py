from aiogram import Router

from handlers.start import router as start_router
from handlers.wallet import router as wallet_router


def get_root_router() -> Router:
    root = Router(name="root")
    root.include_router(start_router)
    root.include_router(wallet_router)
    return root
