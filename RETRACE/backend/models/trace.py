from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from database import Base


class Trace(Base):
    __tablename__ = "traces"

    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(50), unique=True, nullable=False)
    user_input = Column(Text, nullable=False)
    status = Column(String(50), nullable=False)
    timestamp = Column(
        DateTime,
        server_default=func.current_timestamp()
    )