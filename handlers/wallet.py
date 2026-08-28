from decimal import Decimal

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message, PreCheckoutQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import GatewayName, IntentStatus, LedgerType, PaymentIntent, User, WalletLedger, get_balance
from gateways import GATEWAYS

router = Router(name="wallet")

# Placeholder price for the demo /buy flow — replace with real plan pricing.
TEST_PLAN_STARS_PRICE = Decimal("50")


@router.message(Command("buy"))
async def cmd_buy(message: Message, session: AsyncSession) -> None:
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        await message.answer("اول /start رو بزن.")
        return

    intent = PaymentIntent(
        user_id=user.id,
        gateway=GatewayName.STARS,
        amount=TEST_PLAN_STARS_PRICE,
        status=IntentStatus.PENDING,
    )
    session.add(intent)
    await session.commit()
    await session.refresh(intent)

    gateway = GATEWAYS[GatewayName.STARS]
    invoice = await gateway.create_invoice(
        user_id=user.id,
        amount=TEST_PLAN_STARS_PRICE,
        description="اشتراک یک‌ماهه VPN",
        payment_intent_id=intent.id,
    )

    await message.answer_invoice(
        title=invoice.title,
        description=invoice.description,
        payload=invoice.payload,
        currency=invoice.currency,
        prices=invoice.prices,
        provider_token="",  # Stars invoices don't use a provider token
    )


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_q: PreCheckoutQuery) -> None:
    # TODO: once real plans exist, re-validate the intent (still pending,
    # amount matches, not expired) before approving.
    await pre_checkout_q.answer(ok=True)


@router.message(F.successful_payment.invoice_payload.startswith("intent:"))
async def process_successful_payment(message: Message, session: AsyncSession, bot: Bot) -> None:
    payment = message.successful_payment
    intent_id = int(payment.invoice_payload.removeprefix("intent:"))

    intent = await session.get(PaymentIntent, intent_id)
    if intent is None or intent.status == IntentStatus.SUCCESS:
        return  # unknown or already-processed intent — never double-credit

    gateway = GATEWAYS[intent.gateway]
    verification = await gateway.verify(
        {
            "telegram_payment_charge_id": payment.telegram_payment_charge_id,
            "total_amount": payment.total_amount,
            "currency": payment.currency,
        }
    )

    intent.status = IntentStatus.SUCCESS
    intent.gateway_reference = verification.gateway_reference

    session.add(
        WalletLedger(
            user_id=intent.user_id,
            amount=intent.amount,
            type=LedgerType.DEPOSIT,
            reference_id=str(intent.id),
        )
    )
    await session.commit()

    balance = await get_balance(session, intent.user_id)
    await message.answer(f"پرداخت با موفقیت انجام شد ✅\nموجودی فعلی: {balance} استارز")
