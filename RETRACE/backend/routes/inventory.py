from fastapi import APIRouter
from pydantic import BaseModel

from services.inventory_service import check_stock


router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"]
)


class InventoryRequest(BaseModel):
    product: str
    quantity: int


@router.post("/check")
def check_inventory(request: InventoryRequest):

    result = check_stock(
        request.product,
        request.quantity
    )

    return result