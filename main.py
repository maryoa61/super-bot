import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import settings
from db import init_db
from handlers import get_root_router
from middlewares import DbSessionMiddleware


async def _set_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="شروع / منوی اصلی"),
        BotCommand(command="buy", description="خرید تست اشتراک VPN"),
        BotCommand(command="wallet", description="مشاهده موجودی کیف پول"),
    ]
    if settings.VPS_STORE_ENABLED:
        commands.append(BotCommand(command="vps", description="فروشگاه VPS"))
    if settings.CONTENT_STORE_ENABLED:
        commands.append(BotCommand(command="content", description="فروشگاه محتوا"))
    if settings.LICENSE_STORE_ENABLED:
        commands.append(BotCommand(command="licenses", description="فروشگاه لایسنس"))
    if settings.GIFTCARD_STORE_ENABLED:
        commands.append(BotCommand(command="giftcards", description="فروشگاه گیفت‌کارت"))
    await bot.set_my_commands(commands)


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
    await _set_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
