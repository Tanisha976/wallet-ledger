from fastapi import FastAPI
from sqlalchemy import text
from database import engine, redis_client

from fastapi import Header
from fastapi.encoders import jsonable_encoder
import json

RATE_LIMIT = 10
RATE_WINDOW_SECONDS = 60

def check_rate_limit(wallet_id: id):
    key = f"ratelimit:{wallet_id}"
    current = redis_client.incr(key)
    if current == 1:
        redis_client.expire(key,RATE_WINDOW_SECONDS)
    if current > RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")

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
from schemas import WalletCreate, WalletResponse, DepositRequest, WithdrawRequest

@app.post("/wallets", response_model=WalletResponse)
def create_wallet(wallet: WalletCreate, db: Session = Depends(get_db)):
    new_wallet = Wallet(owner_name=wallet.owner_name, balance=0)
    db.add(new_wallet)
    db.commit()
    db.refresh(new_wallet)
    return new_wallet


@app.post("/wallets/{wallet_id}/deposit", response_model=WalletResponse)
def deposit(wallet_id: int, 
            request: DepositRequest, 
            db: Session = Depends(get_db),
            idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1)
            ):

    cache_key = f"idempotency:{idempotency_key}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    check_rate_limit(wallet_id)
    
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    wallet = db.query(Wallet).filter(Wallet.id == wallet_id).with_for_update().first()
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

    response_data = jsonable_encoder(WalletResponse.model_validate(wallet))

    if cache_key:
        redis_client.set(cache_key, json.dumps(response_data), ex=86400)

    return response_data

@app.post("/wallets/{wallet_id}/withdraw", response_model=WalletResponse)
def withdraw(wallet_id: int, 
             request: WithdrawRequest, 
             db: Session = Depends(get_db),
             idempotency_key: str = Header(..., alias="Idempotency-Key",min_length=1)
            ):

    cache_key = f"idempotency:{idempotency_key}"

    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    check_rate_limit(wallet_id)
    
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    wallet = db.query(Wallet).filter(Wallet.id == wallet_id).with_for_update().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    if wallet.balance < request.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    wallet.balance -= request.amount

    entry = LedgerEntry(
        wallet_id=wallet.id,
        transaction_id=uuid.uuid4(),
        entry_type="debit",
        amount=request.amount
    )
    db.add(entry)
    db.commit()
    db.refresh(wallet)

    response_data = jsonable_encoder(WalletResponse.model_validate(wallet))

    if cache_key:
        redis_client.set(cache_key, json.dumps(response_data), ex=86400)

    return response_data

from schemas import TransferRequest, TransferResponse

@app.post("/transfer", response_model=TransferResponse)
def transfer(request: TransferRequest, 
             db: Session = Depends(get_db),
             idempotency_key: str = Header(..., alias="Idempotency-Key",min_length=1)
            ):

    cache_key = f"idempotency:{idempotency_key}"

    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    check_rate_limit(request.from_wallet_id)
    
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    if request.from_wallet_id == request.to_wallet_id:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same wallet")

    lower_id, higher_id = sorted([request.from_wallet_id, request.to_wallet_id])

    wallet_lower = db.query(Wallet).filter(Wallet.id == lower_id).with_for_update().first()
    wallet_higher = db.query(Wallet).filter(Wallet.id == higher_id).with_for_update().first()

    if request.from_wallet_id == lower_id:
        from_wallet, to_wallet = wallet_lower, wallet_higher
    else:
        from_wallet, to_wallet = wallet_higher, wallet_lower

    if not from_wallet:
        raise HTTPException(status_code=404, detail="Source wallet not found")
    if not to_wallet:
        raise HTTPException(status_code=404, detail="Destination wallet not found")

    if from_wallet.balance < request.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    txn_id = uuid.uuid4()
    from_wallet.balance -= request.amount
    to_wallet.balance += request.amount

    db.add(LedgerEntry(wallet_id=from_wallet.id, transaction_id=txn_id, entry_type="debit", amount=request.amount))
    db.add(LedgerEntry(wallet_id=to_wallet.id, transaction_id=txn_id, entry_type="credit", amount=request.amount))

    db.commit()
    db.refresh(from_wallet)
    db.refresh(to_wallet)

    response_data = jsonable_encoder(TransferResponse(
        transaction_id=str(txn_id),
        from_wallet_id=from_wallet.id,
        from_wallet_balance=from_wallet.balance,
        to_wallet_id=to_wallet.id,
        to_wallet_balance=to_wallet.balance
    ))

    if cache_key:
        redis_client.set(cache_key, json.dumps(response_data), ex=86400)

    return response_data

@app.get("/wallets/{wallet_id}", response_model=WalletResponse)
def get_wallet(wallet_id: int, db: Session = Depends(get_db)):
    wallet = db.query(Wallet).filter(Wallet.id == wallet_id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet

from fastapi import Query
from schemas import LedgerEntryResponse, TransactionHistoryResponse

@app.get("/wallets/{wallet_id}/transactions", response_model=TransactionHistoryResponse)
def get_transaction_history(
    wallet_id: int,
    limit: int = Query(default=10, gt=0, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db)
):
    wallet = db.query(Wallet).filter(Wallet.id == wallet_id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    total_count = db.query(LedgerEntry).filter(LedgerEntry.wallet_id == wallet_id).count()

    entries = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.wallet_id == wallet_id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return TransactionHistoryResponse(
        wallet_id=wallet_id,
        total_count=total_count,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total_count,
        transactions=entries
    )