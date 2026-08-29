from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.models import User

router = Router(name="start")

BTN_WALLET = "💳 کیف پول"
BTN_BUY = "🎫 خرید تست VPN"
BTN_VPS = "🖥 فروشگاه VPS"
BTN_CONTENT = "📚 فروشگاه محتوا"
BTN_LICENSES = "🔑 فروشگاه لایسنس"
BTN_GIFTCARDS = "🎁 فروشگاه گیفت‌کارت"


def _main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard: list[list[KeyboardButton]] = [
        [KeyboardButton(text=BTN_WALLET), KeyboardButton(text=BTN_BUY)]
    ]

    store_buttons: list[KeyboardButton] = []
    if settings.VPS_STORE_ENABLED:
        store_buttons.append(KeyboardButton(text=BTN_VPS))
    if settings.CONTENT_STORE_ENABLED:
        store_buttons.append(KeyboardButton(text=BTN_CONTENT))
    if settings.LICENSE_STORE_ENABLED:
        store_buttons.append(KeyboardButton(text=BTN_LICENSES))
    if settings.GIFTCARD_STORE_ENABLED:
        store_buttons.append(KeyboardButton(text=BTN_GIFTCARDS))

    # two buttons per row, in the order the stores are enabled
    for i in range(0, len(store_buttons), 2):
        keyboard.append(store_buttons[i : i + 2])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


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
        "از منوی پایین صفحه استفاده کن.",
        reply_markup=_main_menu_keyboard(),
    )


@router.message(F.text == BTN_WALLET)
async def on_wallet_button(message: Message, session: AsyncSession) -> None:
    from handlers.wallet import send_wallet_balance

    await send_wallet_balance(message, session, message.from_user.id)


@router.message(F.text == BTN_BUY)
async def on_buy_button(message: Message, session: AsyncSession) -> None:
    from handlers.wallet import send_test_invoice

    await send_test_invoice(message, session, message.from_user.id)


@router.message(F.text == BTN_VPS)
async def on_vps_button(message: Message, session: AsyncSession) -> None:
    from handlers.vps import send_plan_list

    await send_plan_list(message, session)


@router.message(F.text == BTN_CONTENT)
async def on_content_button(message: Message, session: AsyncSession) -> None:
    from handlers.content import send_product_list

    await send_product_list(message, session)


@router.message(F.text == BTN_LICENSES)
async def on_licenses_button(message: Message, session: AsyncSession) -> None:
    from handlers.licenses import send_product_list

    await send_product_list(message, session)


@router.message(F.text == BTN_GIFTCARDS)
async def on_giftcards_button(message: Message, session: AsyncSession) -> None:
    from handlers.giftcards import send_product_list

    await send_product_list(message, session)
