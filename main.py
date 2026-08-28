import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from db import init_db
from handlers import get_root_router
from middlewares import DbSessionMiddleware


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.update.middleware(DbSessionMiddleware())
    dp.include_router(get_root_router())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
