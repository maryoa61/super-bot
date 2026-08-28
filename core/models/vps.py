"""
VPS / virtual-server store models — deliberately separate from
PaymentIntent/WalletLedger (transaction.py, wallet.py): those belong to the
existing VPN test-purchase flow and must not change behavior. A VPS purchase
tracks its own intent (VpsPaymentIntent) and, once paid, its own order
(VpsOrder) instead of crediting the wallet.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class VpsIntentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class VpsOrderStatus(str, enum.Enum):
    PENDING_PROVISION = "pending_provision"
    PROVISIONED = "provisioned"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class VpsPlan(Base):
    """Catalog entry — a ready-made VPS plan an admin can sell."""

    __tablename__ = "vps_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    cpu_cores: Mapped[int] = mapped_column(Integer)
    ram_gb: Mapped[int] = mapped_column(Integer)
    disk_gb: Mapped[int] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(String(64))
    duration_days: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)  # Stars amount, whole number (XTR has no decimals)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class VpsPaymentIntent(Base):
    """One row per attempted VPS purchase, created before the user pays.
    Payload sent to Telegram is 'vpsintent:<id>' — never 'intent:<id>',
    which is reserved for the existing PaymentIntent/wallet flow."""

    __tablename__ = "vps_payment_intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("vps_plans.id"))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[VpsIntentStatus] = mapped_column(
        Enum(VpsIntentStatus), default=VpsIntentStatus.PENDING
    )
    gateway_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class VpsOrder(Base):
    """Created once a VpsPaymentIntent succeeds. Provisioning is manual —
    no hypervisor/panel API integration — an admin fulfills it with
    /vps_fulfill, which fills credentials/expires_at and DMs the buyer."""

    __tablename__ = "vps_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("vps_plans.id"))
    payment_intent_id: Mapped[int] = mapped_column(ForeignKey("vps_payment_intents.id"))
    status: Mapped[VpsOrderStatus] = mapped_column(
        Enum(VpsOrderStatus), default=VpsOrderStatus.PENDING_PROVISION
    )
    credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
