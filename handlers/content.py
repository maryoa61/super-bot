"""
Digital content store — fully self-contained module (see core/models/content.py).

Flow:
  /content                 -> list active products with inline "خرید" buttons
  callback contentbuy:<id>  -> create a ContentPaymentIntent, send a Stars
                              invoice with payload "contentintent:<id>"
  successful_payment        -> only for payload starting with "contentintent:"
                              — marks the intent successful, delivers the
                              file/link immediately, records a ContentOrder.

Admin catalog management:
  /content_add_link <price>|<title>|<description>|<url>
  /content_add_file <price>|<title>|<description>   (send as the CAPTION of
      an uploaded document/video/photo — the file_id is captured from it)
  /content_disable <product_id>
"""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.models import (
    ContentDeliveryType,
    ContentIntentStatus,
    ContentOrder,
    ContentPaymentIntent,
    ContentProduct,
    User,
)

router = Router(name="content")


def _product_caption(product: ContentProduct) -> str:
    return f"📚 <b>{product.title}</b>\n{product.description}\n\nقیمت: {product.price} استارز"


@router.message(Command("content"))
async def cmd_content_list(message: Message, session: AsyncSession) -> None:
    await send_product_list(message, session)


async def send_product_list(reply_to: Message, session: AsyncSession) -> None:
    result = await session.execute(
        select(ContentProduct)
        .where(ContentProduct.is_active.is_(True))
        .order_by(ContentProduct.price.asc())
    )
    products = result.scalars().all()
    if not products:
        await reply_to.answer("در حال حاضر محتوای فعالی برای فروش نیست.")
        return

    for product in products:
        kb = InlineKeyboardBuilder()
        kb.button(text=f"خرید — {product.price} ⭐️", callback_data=f"contentbuy:{product.id}")
        await reply_to.answer(_product_caption(product), reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("contentbuy:"))
async def cb_content_buy(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.removeprefix("contentbuy:"))
    product = await session.get(ContentProduct, product_id)
    if product is None or not product.is_active:
        await callback.answer("این محصول دیگه در دسترس نیست.", show_alert=True)
        return

    result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        await callback.answer("اول /start رو بزن.", show_alert=True)
        return

    intent = ContentPaymentIntent(
        user_id=user.id,
        product_id=product.id,
        amount=product.price,
        status=ContentIntentStatus.PENDING,
    )
    session.add(intent)
    await session.commit()
    await session.refresh(intent)

    await callback.message.answer_invoice(
        title=product.title,
        description=product.description[:255],  # Telegram invoice description limit
        payload=f"contentintent:{intent.id}",
        currency="XTR",
        prices=[LabeledPrice(label=product.title, amount=product.price)],
        provider_token="",  # Stars invoices don't use a provider token
    )
    await callback.answer()


@router.message(F.successful_payment.invoice_payload.startswith("contentintent:"))
async def process_content_successful_payment(message: Message, session: AsyncSession) -> None:
    payment = message.successful_payment
    intent_id = int(payment.invoice_payload.removeprefix("contentintent:"))

    intent = await session.get(ContentPaymentIntent, intent_id)
    if intent is None or intent.status == ContentIntentStatus.SUCCESS:
        return  # unknown or already-processed intent — never double-deliver

    intent.status = ContentIntentStatus.SUCCESS
    intent.gateway_reference = payment.telegram_payment_charge_id

    product = await session.get(ContentProduct, intent.product_id)

    order = ContentOrder(
        user_id=intent.user_id, product_id=intent.product_id, payment_intent_id=intent.id
    )
    session.add(order)
    await session.commit()

    if product is None:
        await message.answer("پرداخت با موفقیت انجام شد ✅ ولی محصول دیگه در دسترس نیست، با پشتیبانی تماس بگیر.")
        return

    await message.answer("پرداخت با موفقیت انجام شد ✅ در حال ارسال محتوا...")
    if product.delivery_type == ContentDeliveryType.FILE and product.file_id:
        await message.answer_document(product.file_id, caption=product.title)
    elif product.delivery_type == ContentDeliveryType.LINK and product.url:
        await message.answer(f"🔗 لینک دانلود:\n{product.url}")
    else:
        await message.answer("محتوا ثبت نشده، با پشتیبانی تماس بگیر.")


@router.message(Command("content_add_link"))
async def cmd_content_add_link(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    args = message.text.removeprefix("/content_add_link").strip()
    parts = args.split("|", 3)
    if len(parts) != 4:
        await message.answer("فرمت درست:\n/content_add_link <price>|<title>|<description>|<url>")
        return

    price_str, title, description, url = (p.strip() for p in parts)
    if not price_str.isdigit():
        await message.answer("price باید عدد باشه.")
        return

    product = ContentProduct(
        title=title,
        description=description,
        price=int(price_str),
        delivery_type=ContentDeliveryType.LINK,
        url=url,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)

    await message.answer(f"محصول ساخته شد ✅ (id={product.id})\n\n{_product_caption(product)}")


@router.message(
    F.caption.startswith("/content_add_file") | F.text.startswith("/content_add_file")
)
async def cmd_content_add_file(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    args = (message.caption or message.text or "").removeprefix("/content_add_file").strip()
    parts = args.split("|", 2)
    if len(parts) != 3:
        await message.answer(
            "این دستور رو به‌صورت caption یه فایل/ویدیو آپلودی بفرست:\n"
            "/content_add_file <price>|<title>|<description>"
        )
        return

    price_str, title, description = (p.strip() for p in parts)
    if not price_str.isdigit():
        await message.answer("price باید عدد باشه.")
        return

    file_id = None
    if message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.audio:
        file_id = message.audio.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id

    if file_id is None:
        await message.answer("باید این دستور رو caption یه فایل/ویدیو/عکس بفرستی، نه یه پیام متنی تنها.")
        return

    product = ContentProduct(
        title=title,
        description=description,
        price=int(price_str),
        delivery_type=ContentDeliveryType.FILE,
        file_id=file_id,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)

    await message.answer(f"محصول ساخته شد ✅ (id={product.id})\n\n{_product_caption(product)}")


@router.message(Command("content_disable"))
async def cmd_content_disable(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    arg = message.text.removeprefix("/content_disable").strip()
    if not arg.isdigit():
        await message.answer("فرمت: /content_disable <product_id>")
        return

    product = await session.get(ContentProduct, int(arg))
    if product is None:
        await message.answer("محصولی با این شناسه پیدا نشد.")
        return

    product.is_active = False
    await session.commit()
    await message.answer(f"محصول #{arg} غیرفعال شد.")
