"""
Gift card / digital voucher store — fully self-contained module (see
core/models/giftcards.py). Structurally identical to handlers/licenses.py
(stock-based, atomic claim on payment) but kept fully separate per the
project's rule that every store is independent.

Flow:
  /giftcards                  -> list active products (shows remaining stock)
                               with inline "خرید" buttons
  callback giftcardbuy:<id>    -> refuse if no stock left; otherwise create a
                               GiftCardPaymentIntent, send a Stars invoice
                               with payload "giftcardintent:<id>"
  successful_payment           -> only for payload starting with
                               "giftcardintent:" — atomically claims one
                               unsold GiftCardStockItem, delivers the code.

Admin catalog management:
  /giftcard_add_product <price>|<title>|<description>|<value_label>
  /giftcard_add_stock <product_id>|<code>   (one code per call)
  /giftcard_disable <product_id>
  /giftcard_stock_count <product_id>
"""

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.models import (
    GiftCardIntentStatus,
    GiftCardPaymentIntent,
    GiftCardProduct,
    GiftCardStockItem,
    User,
)

router = Router(name="giftcards")


async def _stock_count(session: AsyncSession, product_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(GiftCardStockItem)
        .where(GiftCardStockItem.product_id == product_id, GiftCardStockItem.is_sold.is_(False))
    )
    return result.scalar_one()


def _product_caption(product: GiftCardProduct, stock: int) -> str:
    return (
        f"🎁 <b>{product.title}</b> ({product.value_label})\n"
        f"{product.description}\n\n"
        f"موجودی: {stock} عدد\n"
        f"قیمت: {product.price} استارز"
    )


@router.message(Command("giftcards"))
async def cmd_giftcards_list(message: Message, session: AsyncSession) -> None:
    await send_product_list(message, session)


async def send_product_list(reply_to: Message, session: AsyncSession) -> None:
    result = await session.execute(
        select(GiftCardProduct)
        .where(GiftCardProduct.is_active.is_(True))
        .order_by(GiftCardProduct.price.asc())
    )
    products = result.scalars().all()
    if not products:
        await reply_to.answer("در حال حاضر کارت هدیه‌ی فعالی برای فروش نیست.")
        return

    for product in products:
        stock = await _stock_count(session, product.id)
        kb = InlineKeyboardBuilder()
        if stock > 0:
            kb.button(
                text=f"خرید — {product.price} ⭐️", callback_data=f"giftcardbuy:{product.id}"
            )
        else:
            kb.button(text="ناموجود", callback_data="giftcardbuy:soldout")
        await reply_to.answer(_product_caption(product, stock), reply_markup=kb.as_markup())


@router.callback_query(F.data == "giftcardbuy:soldout")
async def cb_giftcard_soldout(callback: CallbackQuery) -> None:
    await callback.answer("این کارت هدیه در حال حاضر ناموجوده.", show_alert=True)


@router.callback_query(F.data.startswith("giftcardbuy:"))
async def cb_giftcard_buy(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.removeprefix("giftcardbuy:"))
    product = await session.get(GiftCardProduct, product_id)
    if product is None or not product.is_active:
        await callback.answer("این کارت هدیه دیگه در دسترس نیست.", show_alert=True)
        return

    stock = await _stock_count(session, product.id)
    if stock <= 0:
        await callback.answer("این کارت هدیه در حال حاضر ناموجوده.", show_alert=True)
        return

    result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        await callback.answer("اول /start رو بزن.", show_alert=True)
        return

    intent = GiftCardPaymentIntent(
        user_id=user.id,
        product_id=product.id,
        amount=product.price,
        status=GiftCardIntentStatus.PENDING,
    )
    session.add(intent)
    await session.commit()
    await session.refresh(intent)

    await callback.message.answer_invoice(
        title=product.title,
        description=product.description[:255],
        payload=f"giftcardintent:{intent.id}",
        currency="XTR",
        prices=[LabeledPrice(label=product.title, amount=product.price)],
        provider_token="",  # Stars invoices don't use a provider token
    )
    await callback.answer()


@router.message(F.successful_payment.invoice_payload.startswith("giftcardintent:"))
async def process_giftcard_successful_payment(message: Message, session: AsyncSession) -> None:
    payment = message.successful_payment
    intent_id = int(payment.invoice_payload.removeprefix("giftcardintent:"))

    intent = await session.get(GiftCardPaymentIntent, intent_id)
    if intent is None or intent.status == GiftCardIntentStatus.SUCCESS:
        return  # unknown or already-processed intent — never double-deliver

    claim = await session.execute(
        update(GiftCardStockItem)
        .where(
            GiftCardStockItem.id
            == select(GiftCardStockItem.id)
            .where(
                GiftCardStockItem.product_id == intent.product_id,
                GiftCardStockItem.is_sold.is_(False),
            )
            .order_by(GiftCardStockItem.id)
            .limit(1)
            .scalar_subquery()
        )
        .values(
            is_sold=True,
            sold_to_user_id=intent.user_id,
            sold_at=datetime.now(timezone.utc),
        )
        .returning(GiftCardStockItem)
    )
    stock_item = claim.scalar_one_or_none()

    intent.status = GiftCardIntentStatus.SUCCESS
    intent.gateway_reference = payment.telegram_payment_charge_id
    if stock_item is not None:
        intent.stock_item_id = stock_item.id
    await session.commit()

    if stock_item is None:
        await message.answer(
            "پرداخت با موفقیت انجام شد ✅ ولی این کارت همزمان به فروش رفته بود؛ "
            "با پشتیبانی تماس بگیر تا مبلغت برگردونده یا کارت جایگزین بدیم."
        )
        for admin_id in settings.admin_id_list:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"⚠️ giftcard intent #{intent.id} پرداخت شد ولی موجودی تموم شده بود "
                    f"(product_id={intent.product_id}, user={message.from_user.id}).",
                )
            except Exception:
                pass
        return

    await message.answer(f"پرداخت با موفقیت انجام شد ✅\n\n🎁 کد کارت هدیه:\n{stock_item.code}")


@router.message(Command("giftcard_add_product"))
async def cmd_giftcard_add_product(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    args = message.text.removeprefix("/giftcard_add_product").strip()
    parts = args.split("|", 3)
    if len(parts) != 4:
        await message.answer(
            "فرمت درست:\n/giftcard_add_product <price>|<title>|<description>|<value_label>"
        )
        return

    price_str, title, description, value_label = (p.strip() for p in parts)
    if not price_str.isdigit():
        await message.answer("price باید عدد باشه.")
        return

    product = GiftCardProduct(
        title=title, description=description, value_label=value_label, price=int(price_str)
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)

    await message.answer(f"محصول ساخته شد ✅ (id={product.id})\n\n{_product_caption(product, 0)}")


@router.message(Command("giftcard_add_stock"))
async def cmd_giftcard_add_stock(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    args = message.text.removeprefix("/giftcard_add_stock").strip()
    product_id_str, sep, code = args.partition("|")
    if not sep or not product_id_str.strip().isdigit() or not code.strip():
        await message.answer("فرمت: /giftcard_add_stock <product_id>|<code>")
        return

    product_id = int(product_id_str.strip())
    product = await session.get(GiftCardProduct, product_id)
    if product is None:
        await message.answer("محصولی با این شناسه پیدا نشد.")
        return

    session.add(GiftCardStockItem(product_id=product_id, code=code.strip()))
    await session.commit()

    stock = await _stock_count(session, product_id)
    await message.answer(f"یه کد اضافه شد ✅ موجودی فعلی #{product_id}: {stock}")


@router.message(Command("giftcard_disable"))
async def cmd_giftcard_disable(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    arg = message.text.removeprefix("/giftcard_disable").strip()
    if not arg.isdigit():
        await message.answer("فرمت: /giftcard_disable <product_id>")
        return

    product = await session.get(GiftCardProduct, int(arg))
    if product is None:
        await message.answer("محصولی با این شناسه پیدا نشد.")
        return

    product.is_active = False
    await session.commit()
    await message.answer(f"محصول #{arg} غیرفعال شد.")


@router.message(Command("giftcard_stock_count"))
async def cmd_giftcard_stock_count(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    arg = message.text.removeprefix("/giftcard_stock_count").strip()
    if not arg.isdigit():
        await message.answer("فرمت: /giftcard_stock_count <product_id>")
        return

    stock = await _stock_count(session, int(arg))
    await message.answer(f"موجودی فعلی #{arg}: {stock}")
