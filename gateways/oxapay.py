from decimal import Decimal

from gateways.base import InvoicePayload, PaymentGateway, PaymentStatus, VerificationResult


class OxaPayGateway(PaymentGateway):
    """
    NOT WIRED UP YET — placeholder so the adapter registry already has
    a second gateway slot. Real implementation needs:
      - POST to OxaPay's create-invoice endpoint with OXAPAY_MERCHANT_KEY
      - store the returned pay_link in InvoicePayload.extra["url"]
      - verify() should check OxaPay's webhook signature/callback, not
        just trust the payload blindly
    """

    name = "crypto"

    async def create_invoice(
        self,
        *,
        user_id: int,
        amount: Decimal,
        description: str,
        payment_intent_id: int,
    ) -> InvoicePayload:
        raise NotImplementedError("OxaPay integration not implemented yet")

    async def verify(self, payload: dict) -> VerificationResult:
        raise NotImplementedError("OxaPay integration not implemented yet")
