"""
Gift card / digital voucher store — a stock-based store: each
GiftCardStockItem (a code) can be sold exactly once. Structurally identical
to licenses.py but kept as a fully separate module/table set, per the
project's rule that every store is independent.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class GiftCardIntentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class GiftCardProduct(Base):
    __tablename__ = "giftcard_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    value_label: Mapped[str] = mapped_column(String(64))  # e.g. "$25", "500k Toman"
    price: Mapped[int] = mapped_column(Integer)  # Stars amount, whole number
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class GiftCardStockItem(Base):
    """One sellable code. Claimed atomically the same way as
    LicenseStockItem — see handlers/giftcards.py."""

    __tablename__ = "giftcard_stock_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("giftcard_products.id"), index=True)
    code: Mapped[str] = mapped_column(Text)
    is_sold: Mapped[bool] = mapped_column(default=False, index=True)
    sold_to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class GiftCardPaymentIntent(Base):
    """Payload sent to Telegram is 'giftcardintent:<id>' — never 'intent:<id>'."""

    __tablename__ = "giftcard_payment_intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("giftcard_products.id"))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[GiftCardIntentStatus] = mapped_column(
        Enum(GiftCardIntentStatus), default=GiftCardIntentStatus.PENDING
    )
    gateway_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stock_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("giftcard_stock_items.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
