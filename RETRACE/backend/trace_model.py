from sqlalchemy import Column, BigInteger, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from database import Base


class TraceAnalysis(Base):
    __tablename__ = "trace_analyses"

    id = Column(BigInteger, primary_key=True, index=True)
    trace_id = Column(String(50), unique=True, nullable=False, index=True)
    user_input = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="pending")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    result_json = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)