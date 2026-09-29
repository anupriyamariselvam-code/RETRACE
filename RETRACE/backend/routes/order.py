import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.order import Order
from services.order_service import create_order, cancel_order


router = APIRouter(prefix="/order", tags=["Order"])


class OrderRequest(BaseModel):
    product: str
    quantity: int
    amount: float
    payment_method: str = "card"


@router.post("/create")
def create_order_api(request: OrderRequest):
    return create_order(
        request.product,
        request.quantity,
        request.amount,
        request.payment_method,
    )


@router.get("/history")
def get_order_history(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Order)
        .order_by(Order.id.desc())
        .limit(limit)
        .all()
    )

    return {
        "count": len(orders),
        "orders": [
            {
                "order_id": order.order_id,
                "product": order.product,
                "quantity": order.quantity,
                "amount": order.amount,
                "payment_method": order.payment_method,
                "status": order.status,
                "stage": order.stage,
                "message": order.message,
                "timestamp": order.timestamp,
            }
            for order in orders
        ],
    }


@router.post("/{order_id}/cancel")
def cancel_order_api(order_id: str):
    result = cancel_order(order_id)

    if not result.get("success"):
        status_code = result.get("status_code", 409)

        raise HTTPException(
            status_code=status_code,
            detail=result.get("message", "Unable to cancel order"),
        )

    return result


@router.get("/{order_id}")
def get_order_by_id(
    order_id: str,
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.order_id == order_id)
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    try:
        details = json.loads(order.details) if order.details else None
    except json.JSONDecodeError:
        details = order.details

    return {
        "order_id": order.order_id,
        "product": order.product,
        "quantity": order.quantity,
        "amount": order.amount,
        "payment_method": order.payment_method,
        "status": order.status,
        "stage": order.stage,
        "message": order.message,
        "details": details,
        "timestamp": order.timestamp,
    }