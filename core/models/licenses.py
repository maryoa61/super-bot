"""
License key / ready-account store (SaaS keys, game accounts, ...) — a
stock-based store: each LicenseStockItem can be sold exactly once. Fully
separate from PaymentIntent/WalletLedger and from the other stores.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class LicenseIntentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class LicenseProduct(Base):
    __tablename__ = "license_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64))  # e.g. "SaaS", "Game"
    price: Mapped[int] = mapped_column(Integer)  # Stars amount, whole number
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class LicenseStockItem(Base):
    """One sellable unit (a key or account). Claimed atomically by an
    UPDATE ... WHERE id = (SELECT ... LIMIT 1) RETURNING statement — see
    handlers/licenses.py — so two simultaneous buyers can never get the
    same item."""

    __tablename__ = "license_stock_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("license_products.id"), index=True)
    secret_data: Mapped[str] = mapped_column(Text)
    is_sold: Mapped[bool] = mapped_column(default=False, index=True)
    sold_to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class LicensePaymentIntent(Base):
    """Payload sent to Telegram is 'licenseintent:<id>' — never 'intent:<id>'."""

    __tablename__ = "license_payment_intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("license_products.id"))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[LicenseIntentStatus] = mapped_column(
        Enum(LicenseIntentStatus), default=LicenseIntentStatus.PENDING
    )
    gateway_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stock_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("license_stock_items.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
