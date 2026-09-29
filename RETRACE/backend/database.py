import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


load_dotenv()

DB_PASSWORD = os.getenv("RETRACE_DB_PASSWORD")

if not DB_PASSWORD:
    raise RuntimeError(
        "RETRACE_DB_PASSWORD is not set. "
        "Check your .env file."
    )

DATABASE_URL = (
    "postgresql+psycopg://postgres:"
    + quote_plus(DB_PASSWORD)
    + "@localhost:5432/retrace_db"
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()