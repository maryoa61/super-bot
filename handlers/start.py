from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import User

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        session.add(user)
        await session.commit()

    await message.answer(
        "سلام! به ربات فروش VPN خوش اومدی.\n"
        "برای خرید اشتراک از منو استفاده کن، یا /buy رو بزن برای تست پرداخت با استارز."
    )
