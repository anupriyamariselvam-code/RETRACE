from sqlalchemy import Column, Integer, String

from database import Base


class InventoryItem(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    product = Column(String(100), unique=True, nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=0)