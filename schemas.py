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