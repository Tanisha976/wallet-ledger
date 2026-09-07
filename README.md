# Wallet Ledger System

A backend wallet and ledger service — deposit, withdraw, and transfer money between wallets, with a full double-entry audit trail, safety under concurrent access, and protection against duplicate requests.

Built to practice the exact problems real payment systems deal with: race conditions on concurrent balance updates, and duplicate charges from network retries — not just another CRUD app.

**Live demo:** [wallet-ledger-deployment.onrender.com/docs](https://wallet-ledger-deployment.onrender.com/docs) *(free-tier hosting — first request after inactivity may take 30–60s to wake up)*

---

## Why This Project

Most student backend projects stop at CRUD + auth. This one goes further, into systems-level correctness:

- **Proven, not claimed, concurrency safety** — a load test fires 50 simultaneous withdrawal requests against a wallet that can only afford 5, and the system guarantees exactly 5 succeed, with the balance never going negative.
- **Real double-entry accounting**, the same modeling principle behind actual financial ledgers — balance is a derived, cached value; the ledger itself is the append-only source of truth.
- **Idempotency keys**, the same pattern Stripe and Razorpay use to guarantee a network retry never double-processes a request.

Full reasoning behind every decision — including alternatives considered and why they lost — is in [`wallet-ledger-documentation.md`](./wallet-ledger-documentation.md).

---

## Features

| Feature | What it proves |
|---|---|
| Wallet operations (deposit / withdraw / transfer) | Correct REST design |
| Double-entry ledger | Data modeling for auditability, not just storage |
| Row-level locking (`SELECT ... FOR UPDATE`) + a passing concurrency test | Real understanding of transactions and isolation, proven under load |
| Deadlock-safe lock ordering in transfer | Awareness of a subtle failure mode most naive implementations miss |
| Mandatory idempotency keys (Redis, 24h TTL) | Handling of real-world network failure, not just the happy path |
| Rate limiting (Redis, fixed window) | Abuse/DoS awareness |
| Paginated transaction history | Query efficiency awareness at scale |

---

## Tech Stack

- **API:** FastAPI (Python) — async-native, built-in request validation, auto-generated docs
- **Database:** PostgreSQL, hosted on [Neon](https://neon.tech) — chosen over SQLite specifically for real row-level locking
- **Cache / ephemeral store:** Redis, hosted on [Upstash](https://upstash.com) — idempotency keys and rate-limit counters
- **Hosting:** [Render](https://render.com)
- **ORM:** SQLAlchemy

---

## Architecture

```
Client request (+ Idempotency-Key header)
        │
        ▼
API layer validates input (FastAPI + Pydantic)
        │
        ▼
Idempotency check (Redis) ──seen before?──▶ return cached response
        │ (new request)
        ▼
Rate limit check (Redis) ──too many?──▶ 429
        │
        ▼
DB transaction: row lock (FOR UPDATE) + ledger write (Postgres)
        │
        ▼
Cache response in Redis (24h TTL) + return
```

**Schema:**
- `wallets` — `id`, `owner_name`, `balance` (`NUMERIC(12,2)`, `CHECK >= 0`), `created_at`
- `ledger_entries` — `id`, `wallet_id` (FK), `transaction_id` (UUID, shared across a transfer's debit/credit pair), `entry_type` (`debit`/`credit`), `amount` (`NUMERIC(12,2)`, `CHECK > 0`), `created_at`

---

## The Concurrency Test

The core proof of the whole project — 50 concurrent withdrawal requests fired via `ThreadPoolExecutor` against a wallet funded for exactly 5:

```
Successful withdrawals: 5
Failed (insufficient balance): 45
Final balance: 0.00
```

Reproducible on every run. Script: [`tests/concurrency_test.py`](./tests/concurrency_test.py).

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/wallets` | Create a wallet |
| `GET` | `/wallets/{id}` | Get wallet balance |
| `POST` | `/wallets/{id}/deposit` | Deposit funds *(requires `Idempotency-Key` header)* |
| `POST` | `/wallets/{id}/withdraw` | Withdraw funds *(requires `Idempotency-Key` header)* |
| `POST` | `/transfer` | Transfer between wallets *(requires `Idempotency-Key` header)* |
| `GET` | `/wallets/{id}/transactions` | Paginated transaction history (`limit`, `offset`) |
| `GET` | `/health/db` | Postgres connectivity check |
| `GET` | `/health/redis` | Redis connectivity check |

Full interactive docs with request/response schemas: [`/docs`](https://wallet-ledger-deployment.onrender.com/docs)

---

## Running Locally

```bash
git clone https://github.com/Tanisha976/wallet-ledger.git
cd wallet-ledger
python -m venv venv
venv\Scripts\Activate.ps1      # Windows
pip install -r requirements.txt
```

Create a `.env` file (see `.env.example`) with your own Postgres and Redis connection strings, then:

```bash
python create_tables.py        # one-time table creation
uvicorn main:app --reload
```

Visit `http://127.0.0.1:8000/docs`.

---

## Known Limitations / Next Steps

- Offset-based pagination — fine at this scale, would move to cursor-based for a large table
- No explicit `try/except` + rollback around the transfer logic (currently safe, but not defensive)
- Single shared database for local dev and production (a real team setup would separate these)
- No `users`/auth layer — wallets are the modeled entity, deliberately out of scope

