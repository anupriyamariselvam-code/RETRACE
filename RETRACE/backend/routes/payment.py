from fastapi import APIRouter
from pydantic import BaseModel

from services.payment_service import process_payment


router = APIRouter(
    prefix="/payment",
    tags=["Payment"]
)


class PaymentRequest(BaseModel):
    amount: float
    payment_method: str = "card"


@router.post("/process")
def process_payment_api(request: PaymentRequest):

    result = process_payment(
        request.amount,
        request.payment_method
    )

    return result