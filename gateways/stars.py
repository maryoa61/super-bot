from decimal import Decimal

from aiogram.types import LabeledPrice

from gateways.base import InvoicePayload, PaymentGateway, PaymentStatus, VerificationResult


class StarsGateway(PaymentGateway):
    """
    Telegram Stars. No external API/merchant account needed — the bot
    calls Bot API's sendInvoice with currency="XTR" directly, Telegram
    handles the whole payment UI, and confirms it back to the bot via
    a `successful_payment` message update. See handlers/wallet.py for
    where create_invoice()'s output actually gets sent.
    """

    name = "stars"

    async def create_invoice(
        self,
        *,
        user_id: int,
        amount: Decimal,
        description: str,
        payment_intent_id: int,
    ) -> InvoicePayload:
        stars_amount = int(amount)  # Stars are whole numbers, no decimals

        return InvoicePayload(
            title="خرید اشتراک VPN",
            description=description,
            payload=f"intent:{payment_intent_id}",
            currency="XTR",
            amount=stars_amount,
            prices=[LabeledPrice(label="اشتراک VPN", amount=stars_amount)],
        )

    async def verify(self, payload: dict) -> VerificationResult:
        # Stars payments arrive already-confirmed via the successful_payment
        # update (Telegram itself is the source of truth) — nothing to call
        # out to. This just normalizes that update into our common shape.
        return VerificationResult(
            status=PaymentStatus.SUCCESS,
            gateway_reference=payload.get("telegram_payment_charge_id"),
            raw=payload,
        )
