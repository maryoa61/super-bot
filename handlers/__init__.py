from aiogram import Router

from config import settings
from handlers.content import router as content_router
from handlers.giftcards import router as giftcards_router
from handlers.licenses import router as licenses_router
from handlers.start import router as start_router
from handlers.vps import router as vps_router
from handlers.wallet import router as wallet_router


def get_root_router() -> Router:
    root = Router(name="root")
    root.include_router(start_router)
    root.include_router(wallet_router)
    if settings.VPS_STORE_ENABLED:
        root.include_router(vps_router)
    if settings.CONTENT_STORE_ENABLED:
        root.include_router(content_router)
    if settings.LICENSE_STORE_ENABLED:
        root.include_router(licenses_router)
    if settings.GIFTCARD_STORE_ENABLED:
        root.include_router(giftcards_router)
    return root
