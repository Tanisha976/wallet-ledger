from fastapi import FastAPI
from sqlalchemy import text
from database import engine, redis_client

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"database": "connected"}

@app.get("/health/redis")
def health_redis():
    redis_client.set("ping", "pong")
    value = redis_client.get("ping")
    return {"redis": value.decode()}

import uuid
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Wallet, LedgerEntry
from schemas import WalletCreate, WalletResponse, DepositRequest

@app.post("/wallets", response_model=WalletResponse)
def create_wallet(wallet: WalletCreate, db: Session = Depends(get_db)):
    new_wallet = Wallet(owner_name=wallet.owner_name, balance=0)
    db.add(new_wallet)
    db.commit()
    db.refresh(new_wallet)
    return new_wallet


@app.post("/wallets/{wallet_id}/deposit", response_model=WalletResponse)
def deposit(wallet_id: int, request: DepositRequest, db: Session = Depends(get_db)):
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    wallet = db.query(Wallet).filter(Wallet.id == wallet_id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    wallet.balance += request.amount

    entry = LedgerEntry(
        wallet_id=wallet.id,
        transaction_id=uuid.uuid4(),
        entry_type="credit",
        amount=request.amount
    )
    db.add(entry)
    db.commit()
    db.refresh(wallet)
    return wallet