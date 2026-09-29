from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from database import Base


class TraceEvent(Base):
    __tablename__ = "trace_events"

    id = Column(Integer, primary_key=True, index=True)

    trace_id = Column(
        String(50),
        nullable=False,
        index=True
    )

    stage = Column(
        String(100),
        nullable=False
    )

    status = Column(
        String(50),
        nullable=False
    )

    details = Column(
        Text,
        nullable=True
    )

    event_hash = Column(
        String(64),
        nullable=True
    )

    timestamp = Column(
        DateTime,
        server_default=func.current_timestamp()
    )