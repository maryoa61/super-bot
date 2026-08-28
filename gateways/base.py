from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class InvoicePayload:
    """
    What a gateway hands back to the handler so it can show/send
    something to the user. Not every field is used by every gateway —
    e.g. Stars fills `prices`, OxaPay/ZarinPal would fill `extra['url']`
    with a redirect link, card-to-card fills `extra['card_number']`.
    """

    title: str
    description: str
    payload: str  # opaque string identifying the payment_intent, e.g. "intent:42"
    currency: str  # "XTR" for Stars, "IRT" for ZarinPal, "USDT" for crypto, etc.
    amount: int  # smallest unit the gateway expects (Stars/Rial have no decimals)
    prices: list | None = None  # aiogram LabeledPrice list, only used by Stars
    extra: dict = field(default_factory=dict)  # gateway-specific payload (url, qr, address...)


@dataclass
class VerificationResult:
    status: PaymentStatus
    gateway_reference: str | None = None
    raw: dict | None = None


class PaymentGateway(ABC):
    """
    Every gateway (Stars, OxaPay, ZarinPal, card-to-card) implements this
    same interface. Handlers never talk to a specific gateway's API
    directly — they go through this contract, so swapping/adding a
    gateway never touches handler or model code.
    """

    name: str

    @abstractmethod
    async def create_invoice(
        self,
        *,
        user_id: int,
        amount: Decimal,
        description: str,
        payment_intent_id: int,
    ) -> InvoicePayload:
        """Build whatever the bot needs to present to the user to start paying."""
        ...

    @abstractmethod
    async def verify(self, payload: dict) -> VerificationResult:
        """
        Confirm a payment given an incoming update/webhook payload.
        For Stars this normalizes aiogram's successful_payment update.
        For OxaPay/ZarinPal this will validate a webhook call against
        their API before returning SUCCESS.
        """
        ...
