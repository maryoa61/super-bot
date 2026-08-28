"""
VPS / virtual-server store — fully self-contained module.

Deliberately does NOT reuse gateways/stars.py's title/description building or
core/models/transaction.py's PaymentIntent: those belong to the existing VPN
test-purchase flow and this module must not change their behavior. Instead
it builds its own Stars invoice inline and tracks its own payment intents in
VpsPaymentIntent (see core/models/vps.py).

Flow:
  /vps                 -> list active plans with inline "خرید" buttons
  callback vpsbuy:<id>  -> create a VpsPaymentIntent, send a Stars invoice
                           with payload "vpsintent:<intent_id>"
  successful_payment    -> only for payload starting with "vpsintent:" (see
                           the narrowed filter on handlers/wallet.py's
                           handler) — marks the intent successful, creates a
                           VpsOrder with status=pending_provision, and
                           notifies admins.

Provisioning itself is manual (no hypervisor/panel API integration here): an
admin runs /vps_fulfill <order_id> <credentials...> once the server is
ready, which DMs the buyer and marks the order 'provisioned'.

Admin catalog management:
  /vps_add_plan <price>|<title>|<cpu_cores>|<ram_gb>|<disk_gb>|<location>|<duration_days>
  /vps_disable_plan <plan_id>
  /vps_orders          -> list orders still waiting to be fulfilled
"""

from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.models import (
    User,
    VpsIntentStatus,
    VpsOrder,
    VpsOrderStatus,
    VpsPaymentIntent,
    VpsPlan,
)

router = Router(name="vps")


def _plan_caption(plan: VpsPlan) -> str:
    return (
        f"🖥 <b>{plan.title}</b>\n"
        f"CPU: {plan.cpu_cores} هسته | RAM: {plan.ram_gb}GB | دیسک: {plan.disk_gb}GB\n"
        f"لوکیشن: {plan.location} | مدت: {plan.duration_days} روز\n"
        f"قیمت: {plan.price} استارز"
    )


@router.message(Command("vps"))
async def cmd_vps_list(message: Message, session: AsyncSession) -> None:
    result = await session.execute(
        select(VpsPlan).where(VpsPlan.is_active.is_(True)).order_by(VpsPlan.price.asc())
    )
    plans = result.scalars().all()
    if not plans:
        await message.answer("در حال حاضر پلن فعالی برای فروش نیست.")
        return

    for plan in plans:
        kb = InlineKeyboardBuilder()
        kb.button(text=f"خرید — {plan.price} ⭐️", callback_data=f"vpsbuy:{plan.id}")
        await message.answer(_plan_caption(plan), reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("vpsbuy:"))
async def cb_vps_buy(callback: CallbackQuery, session: AsyncSession) -> None:
    plan_id = int(callback.data.removeprefix("vpsbuy:"))
    plan = await session.get(VpsPlan, plan_id)
    if plan is None or not plan.is_active:
        await callback.answer("این پلن دیگه در دسترس نیست.", show_alert=True)
        return

    result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        await callback.answer("اول /start رو بزن.", show_alert=True)
        return

    intent = VpsPaymentIntent(
        user_id=user.id, plan_id=plan.id, amount=plan.price, status=VpsIntentStatus.PENDING
    )
    session.add(intent)
    await session.commit()
    await session.refresh(intent)

    await callback.message.answer_invoice(
        title=f"خرید VPS — {plan.title}",
        description=(
            f"{plan.cpu_cores} هسته / {plan.ram_gb}GB RAM / {plan.disk_gb}GB دیسک "
            f"/ {plan.location} / {plan.duration_days} روز"
        ),
        payload=f"vpsintent:{intent.id}",
        currency="XTR",
        prices=[LabeledPrice(label=plan.title, amount=plan.price)],
        provider_token="",  # Stars invoices don't use a provider token
    )
    await callback.answer()


@router.message(F.successful_payment.invoice_payload.startswith("vpsintent:"))
async def process_vps_successful_payment(message: Message, session: AsyncSession) -> None:
    payment = message.successful_payment
    intent_id = int(payment.invoice_payload.removeprefix("vpsintent:"))

    intent = await session.get(VpsPaymentIntent, intent_id)
    if intent is None or intent.status == VpsIntentStatus.SUCCESS:
        return  # unknown or already-processed intent — never double-fulfill

    intent.status = VpsIntentStatus.SUCCESS
    intent.gateway_reference = payment.telegram_payment_charge_id

    order = VpsOrder(
        user_id=intent.user_id,
        plan_id=intent.plan_id,
        payment_intent_id=intent.id,
        status=VpsOrderStatus.PENDING_PROVISION,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)

    await message.answer(
        "پرداخت با موفقیت انجام شد ✅\n"
        f"شماره سفارش: #{order.id}\n"
        "سرورت به‌زودی راه‌اندازی و مشخصاتش برات ارسال می‌شه."
    )

    plan = await session.get(VpsPlan, intent.plan_id)
    plan_title = plan.title if plan else f"plan#{intent.plan_id}"
    for admin_id in settings.admin_id_list:
        try:
            await message.bot.send_message(
                admin_id,
                f"🆕 سفارش VPS جدید #{order.id}\n"
                f"پلن: {plan_title}\n"
                f"کاربر تلگرام: {message.from_user.id}\n"
                f"برای تحویل: /vps_fulfill {order.id} <مشخصات سرور>",
            )
        except Exception:
            pass  # admin may have blocked the bot / not started a DM with it


@router.message(Command("vps_add_plan"))
async def cmd_vps_add_plan(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    args = message.text.removeprefix("/vps_add_plan").strip()
    parts = [p.strip() for p in args.split("|")]
    if len(parts) != 7:
        await message.answer(
            "فرمت درست:\n"
            "/vps_add_plan <price>|<title>|<cpu_cores>|<ram_gb>|<disk_gb>|<location>|<duration_days>"
        )
        return

    try:
        price, title, cpu_cores, ram_gb, disk_gb, location, duration_days = parts
        plan = VpsPlan(
            title=title,
            cpu_cores=int(cpu_cores),
            ram_gb=int(ram_gb),
            disk_gb=int(disk_gb),
            location=location,
            duration_days=int(duration_days),
            price=int(price),
        )
    except ValueError:
        await message.answer("price, cpu_cores, ram_gb, disk_gb, duration_days باید عدد باشن.")
        return

    session.add(plan)
    await session.commit()
    await session.refresh(plan)

    await message.answer(f"پلن ساخته شد ✅ (id={plan.id})\n\n{_plan_caption(plan)}")


@router.message(Command("vps_disable_plan"))
async def cmd_vps_disable_plan(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    arg = message.text.removeprefix("/vps_disable_plan").strip()
    if not arg.isdigit():
        await message.answer("فرمت: /vps_disable_plan <plan_id>")
        return

    plan = await session.get(VpsPlan, int(arg))
    if plan is None:
        await message.answer("پلنی با این شناسه پیدا نشد.")
        return

    plan.is_active = False
    await session.commit()
    await message.answer(f"پلن #{arg} غیرفعال شد.")


@router.message(Command("vps_fulfill"))
async def cmd_vps_fulfill(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    args = message.text.removeprefix("/vps_fulfill").strip()
    order_id_str, _, credentials = args.partition(" ")
    if not order_id_str.isdigit() or not credentials.strip():
        await message.answer("فرمت: /vps_fulfill <order_id> <مشخصات سرور>")
        return

    order = await session.get(VpsOrder, int(order_id_str))
    if order is None:
        await message.answer("سفارشی با این شماره پیدا نشد.")
        return
    if order.status != VpsOrderStatus.PENDING_PROVISION:
        await message.answer(f"سفارش #{order.id} قبلاً پردازش شده (status={order.status.value}).")
        return

    plan = await session.get(VpsPlan, order.plan_id)
    duration_days = plan.duration_days if plan else 30
    expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)

    order.status = VpsOrderStatus.PROVISIONED
    order.credentials = credentials.strip()
    order.expires_at = expires_at
    await session.commit()

    user = await session.get(User, order.user_id)
    if user is not None:
        try:
            await message.bot.send_message(
                user.telegram_id,
                f"🖥 سرورت آماده شد! (سفارش #{order.id})\n\n"
                f"{credentials.strip()}\n\n"
                f"تاریخ انقضا: {expires_at:%Y-%m-%d %H:%M} UTC",
            )
        except Exception:
            await message.answer(
                "مشخصات ثبت شد ولی پیام به کاربر نرسید (شاید بات رو بلاک کرده)."
            )

    await message.answer(f"سفارش #{order.id} تحویل داده شد ✅")


@router.message(Command("vps_orders"))
async def cmd_vps_orders(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admin_id_list:
        return

    result = await session.execute(
        select(VpsOrder).where(VpsOrder.status == VpsOrderStatus.PENDING_PROVISION).order_by(VpsOrder.id)
    )
    pending = result.scalars().all()
    if not pending:
        await message.answer("سفارش در انتظار تحویلی نیست.")
        return

    lines = [f"#{o.id} — plan_id={o.plan_id} — user_id={o.user_id}" for o in pending]
    await message.answer("سفارش‌های در انتظار تحویل:\n" + "\n".join(lines))
