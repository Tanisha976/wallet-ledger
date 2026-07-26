from fastapi import FastAPI
from sqlalchemy import create_engine, text
import redis
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

engine = create_engine(os.getenv("DATABASE_URL"))
r = redis.from_url(os.getenv("REDIS_URL"))

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
    r.set("ping", "pong")
    value = r.get("ping")
    return {"redis": value.decode()}