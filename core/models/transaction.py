import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class GatewayName(str, enum.Enum):
    STARS = "stars"
    CRYPTO = "crypto"      # OxaPay
    ZARINPAL = "zarinpal"
    CARD = "card"           # manual card-to-card


class IntentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class PaymentIntent(Base):
    """One row per attempted payment, created *before* the user pays.
    On success, exactly one WalletLedger row (type=deposit) should be
    created with reference_id = str(payment_intent.id)."""

    __tablename__ = "payment_intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    gateway: Mapped[GatewayName] = mapped_column(Enum(GatewayName))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[IntentStatus] = mapped_column(Enum(IntentStatus), default=IntentStatus.PENDING)
    gateway_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="payment_intents")
