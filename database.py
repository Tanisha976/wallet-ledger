import os
from sqlalchemy import create_engine
import redis
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"),pool_pre_ping=True)
redis_client = redis.from_url(os.getenv("REDIS_URL"))

from sqlalchemy.orm import Session

def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()