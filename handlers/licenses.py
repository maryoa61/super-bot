"""
License key / ready-account store — fully self-contained module (see
core/models/licenses.py).

Flow:
  /licenses                  -> list active products (shows remaining stock
                               count) with inline "خرید" buttons
  callback licensebuy:<id>    -> refuse if no stock left; otherwise create a
                               LicensePaymentIntent, send a Stars invoice with
                               payload "licenseintent:<id>"
  successful_payment          -> only for payload starting with
                               "licenseintent:" — atomically claims one
                               unsold LicenseStockItem via a single
                               UPDATE ... WHERE id = (SELECT ... LIMIT 1)
                               statement (so two simultaneous buyers can
                               never get the same key), delivers it.

Admin catalog management:
  /license_add_product <price>|<title>|<description>|<category>
  /license_add_stock <product_id>|<secret_data>   (one item per call)
  /license_disable <product_id>
  /license_stock_count <product_id>
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
    LicenseIntentStatus,
    LicensePaymentIntent,
    LicenseProduct,
    LicenseStockItem,
    User,
)

router = Router(name="licenses")


async def _stock_count(session: AsyncSession, product_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(LicenseStockItem)
        .where(LicenseStockItem.product_id == product_id, LicenseStockItem.is_sold.is_(False))
    )
    return result.scalar_one()


def _product_caption(product: LicenseProduct, stock: int) -> str:
    return (
        f"🔑 <b>{product.title}</b> ({product.category})\n"
        f"{product.description}\n\n"
        f"موجودی: {stock} عدد\n"
        f"قیمت: {product.price} استارز"
    )


@router.message(Command("licenses"))
async def cmd_licenses_list(message: Message, session: AsyncSession) -> None:
    await send_product_list(message, session)


async def send_product_list(reply_to: Message, session: AsyncSession) -> None:
    result = await session.execute(
        select(LicenseProduct)
        .where(LicenseProduct.is_active.is_(True))
        .order_by(LicenseProduct.price.asc())
    )
    products = result.scalars().all()
    if not products:
        await reply_to.answer("در حال حاضر محصول فعالی برای فروش نیست.")
        return

    for product in products:
        stock = await _stock_count(session, product.id)
        kb = InlineKeyboardBuilder()
        if stock > 0:
            kb.button(text=f"خرید — {product.price} ⭐️", callback_data=f"licensebuy:{product.id}")
        else:
            kb.button(text="ناموجود", callback_data="licensebuy:soldout")
        await reply_to.answer(_product_caption(product, stock), reply_markup=kb.as_markup())


@router.callback_query(F.data == "licensebuy:soldout")
async def cb_license_soldout(callback: CallbackQuery) -> None:
    await callback.answer("این محصول در حال حاضر ناموجوده.", show_alert=True)


@router.callback_query(F.data.startswith("licensebuy:"))
async def cb_license_buy(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.removeprefix("licensebuy:"))
    product = await session.get(LicenseProduct, product_id)
    if product is None or not product.is_active:
        await callback.answer("این محصول دیگه در دسترس نیست.", show_alert=True)
        return

    stock = await _stock_count(session, product.id)
    if stock <= 0:
        await callback.answer("این محصول در حال حاضر ناموجوده.", show_alert=True)
        return

    result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        await callback.answer("اول /start رو بزن.", show_alert=True)
        return

    intent = LicensePaymentIntent(
        user_id=user.id,
        product_id=product.id,
        amount=product.price,
        status=LicenseIntentStatus.PENDING,
    )
    session.add(intent)
    await session.commit()
    await session.refresh(intent)

    await callback.message.answer_invoice(
        title=product.title,
        description=product.description[:255],
        payload=f"licenseintent:{intent.id}",
        currency="XTR",
        prices=[LabeledPrice(label=product.title, amount=product.price)],
        provider_token="",  # Stars invoices don't use a provider token
    )
    await callback.answer()


@router.message(F.successful_payment.invoice_payload.startswith("licenseintent:"))
async def process_license_successful_payment(message: Message, session: AsyncSession) -> None:
    payment = message.successful_payment
    intent_id = int(payment.invoice_payload.removeprefix("licenseintent:"))

    intent = await session.get(LicensePaymentIntent, intent_id)
    if intent is None or intent.status == LicenseIntentStatus.SUCCESS:
        return  # unknown or already-processed intent — never double-deliver

    # Atomic claim: one statement, so a concurrent buyer can never grab the
    # same row — whichever request's UPDATE finds the row first "wins" it.
    claim = await session.execute(
        update(LicenseStockItem)
        .where(
            LicenseStockItem.id
            == select(LicenseStockItem.id)
            .where(
                LicenseStockItem.product_id == intent.product_id,
                LicenseStockItem.is_sold.is_(False),
            )
            .order_by(LicenseStockItem.id)
            .limit(1)
            .scalar_subquery()
        )
        .values(
            is_sold=True,
            sold_to_user_id=intent.user_id,
            sold_at=datetime.now(timezone.utc),
        )
        .returning(LicenseStockItem)
    )
    stock_item = claim.scalar_one_or_none()

    intent.status = LicenseIntentStatus.SUCCESS
    intent.gateway_reference = payment.telegram_payment_charge_id
    if stock_item is not None:
        intent.stock_item_id = stock_item.id
    await session.commit()

    if stock_item is None:
        # Sold out between the buy-button check and payment completing —
        # extremely rare, but must never be silently lost.
        await message.answer(
            "پرداخت با موفقیت انجام شد ✅ ولی این کالا همزمان به فروش رفته بود؛ "
            "با پشتیبانی تماس بگیر تا مبلغت برگردونده یا کالای جایگزین بدیم."
        )
        for admin_id in settings.admin_id_list:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"⚠️ license intent #{intent.id} پرداخت شد ولی موجودی تموم شده بود "
                    f"(product_id={intent.product_id}, user={message.from_user.id}).",
                )
            except Exception:
                pass
        return

    await message.answer(
        "پرداخت با موفقیت انجام شد ✅\n\n" f"{stock_item.secret_data}"
    )


@router.message(Command("license_add_product"))
async def cmd_license_add_product(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    args = message.text.removeprefix("/license_add_product").strip()
    parts = args.split("|", 3)
    if len(parts) != 4:
        await message.answer(
            "فرمت درست:\n/license_add_product <price>|<title>|<description>|<category>"
        )
        return

    price_str, title, description, category = (p.strip() for p in parts)
    if not price_str.isdigit():
        await message.answer("price باید عدد باشه.")
        return

    product = LicenseProduct(
        title=title, description=description, category=category, price=int(price_str)
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)

    await message.answer(f"محصول ساخته شد ✅ (id={product.id})\n\n{_product_caption(product, 0)}")


@router.message(Command("license_add_stock"))
async def cmd_license_add_stock(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    args = message.text.removeprefix("/license_add_stock").strip()
    product_id_str, sep, secret_data = args.partition("|")
    if not sep or not product_id_str.strip().isdigit() or not secret_data.strip():
        await message.answer("فرمت: /license_add_stock <product_id>|<secret_data>")
        return

    product_id = int(product_id_str.strip())
    product = await session.get(LicenseProduct, product_id)
    if product is None:
        await message.answer("محصولی با این شناسه پیدا نشد.")
        return

    session.add(LicenseStockItem(product_id=product_id, secret_data=secret_data.strip()))
    await session.commit()

    stock = await _stock_count(session, product_id)
    await message.answer(f"یه آیتم اضافه شد ✅ موجودی فعلی #{product_id}: {stock}")


@router.message(Command("license_disable"))
async def cmd_license_disable(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    arg = message.text.removeprefix("/license_disable").strip()
    if not arg.isdigit():
        await message.answer("فرمت: /license_disable <product_id>")
        return

    product = await session.get(LicenseProduct, int(arg))
    if product is None:
        await message.answer("محصولی با این شناسه پیدا نشد.")
        return

    product.is_active = False
    await session.commit()
    await message.answer(f"محصول #{arg} غیرفعال شد.")


@router.message(Command("license_stock_count"))
async def cmd_license_stock_count(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    arg = message.text.removeprefix("/license_stock_count").strip()
    if not arg.isdigit():
        await message.answer("فرمت: /license_stock_count <product_id>")
        return

    stock = await _stock_count(session, int(arg))
    await message.answer(f"موجودی فعلی #{arg}: {stock}")
