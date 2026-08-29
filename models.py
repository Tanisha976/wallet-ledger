from sqlalchemy import Column, Integer, String, Numeric, TIMESTAMP, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    owner_name = Column(String(100), nullable=False)
    balance = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("balance >= 0", name="balance_non_negative"),
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    transaction_id = Column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    entry_type = Column(String(6), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("entry_type IN ('debit', 'credit')", name="entry_type_valid"),
        CheckConstraint("amount > 0", name="amount_positive"),
    )