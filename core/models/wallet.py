import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from db import Base


class LedgerType(str, enum.Enum):
    DEPOSIT = "deposit"    # money coming in (successful payment)
    WITHDRAW = "withdraw"  # money going out (refund, cash-out)
    PURCHASE = "purchase"  # spent from wallet balance on a VPN plan


class WalletLedger(Base):
    """
    Append-only ledger. NEVER update or delete rows here, and never store
    a standalone 'balance' column anywhere — balance is always the sum
    of this table for a given user. This keeps the wallet auditable.
    """

    __tablename__ = "wallet_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))  # positive=in, negative=out
    type: Mapped[LedgerType] = mapped_column(Enum(LedgerType))
    reference_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="wallet_entries")


async def get_balance(session: AsyncSession, user_id: int) -> Decimal:
    result = await session.execute(
        select(func.coalesce(func.sum(WalletLedger.amount), 0)).where(
            WalletLedger.user_id == user_id
        )
    )
    return result.scalar_one()
