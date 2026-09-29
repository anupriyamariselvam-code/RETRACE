from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.sql import func

from database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)

    order_id = Column(String(50), unique=True, nullable=False, index=True)
    product = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50), nullable=False, default="card")

    status = Column(String(50), nullable=False)
    stage = Column(String(100), nullable=False)
    message = Column(Text, nullable=True)

    details = Column(Text, nullable=True)

    timestamp = Column(
        DateTime,
        server_default=func.current_timestamp()
    )