from pydantic import BaseModel
from decimal import Decimal

class WalletCreate(BaseModel):
    owner_name: str

class WalletResponse(BaseModel):
    id: int
    owner_name: str
    balance: Decimal

    class Config:
        from_attributes = True

class DepositRequest(BaseModel):
    amount: Decimal

class WithdrawRequest(BaseModel):
    amount: Decimal

class TransferRequest(BaseModel):
    from_wallet_id: int
    to_wallet_id: int
    amount: Decimal

class TransferResponse(BaseModel):
    transaction_id: str
    from_wallet_id: int
    from_wallet_balance: Decimal
    to_wallet_id: int
    to_wallet_balance: Decimal

from datetime import datetime
import uuid

class LedgerEntryResponse(BaseModel):
    id: int
    transaction_id: uuid.UUID
    entry_type: str
    amount: Decimal
    created_at: datetime

    class Config:
        from_attributes = True

class TransactionHistoryResponse(BaseModel):
    wallet_id: int
    total_count: int
    limit: int
    offset: int
    has_more: bool
    transactions: list[LedgerEntryResponse]