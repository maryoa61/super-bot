import enum
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus), default=UserStatus.ACTIVE, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    wallet_entries: Mapped[list["WalletLedger"]] = relationship(back_populates="user")
    payment_intents: Mapped[list["PaymentIntent"]] = relationship(back_populates="user")
