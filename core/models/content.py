"""
Digital content store — ebooks, templates, videos, or any file/link that can
be sold and re-delivered an unlimited number of times. Fully separate from
PaymentIntent/WalletLedger (transaction.py, wallet.py) and from the other
stores (vps.py, licenses.py, giftcards.py) — nothing here is referenced by
them, and vice versa.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class ContentIntentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class ContentDeliveryType(str, enum.Enum):
    FILE = "file"  # delivered via a stored Telegram file_id
    LINK = "link"  # delivered as a URL


class ContentProduct(Base):
    __tablename__ = "content_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[int] = mapped_column(Integer)  # Stars amount, whole number
    delivery_type: Mapped[ContentDeliveryType] = mapped_column(Enum(ContentDeliveryType))
    file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ContentPaymentIntent(Base):
    """Payload sent to Telegram is 'contentintent:<id>' — never 'intent:<id>'."""

    __tablename__ = "content_payment_intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("content_products.id"))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[ContentIntentStatus] = mapped_column(
        Enum(ContentIntentStatus), default=ContentIntentStatus.PENDING
    )
    gateway_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ContentOrder(Base):
    """One row per successful delivery — a record, not a fulfillment queue
    (unlike VpsOrder/license/giftcard stock, content delivery is instant)."""

    __tablename__ = "content_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("content_products.id"))
    payment_intent_id: Mapped[int] = mapped_column(ForeignKey("content_payment_intents.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
