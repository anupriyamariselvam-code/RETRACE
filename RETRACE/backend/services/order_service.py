import json
import uuid

from database import SessionLocal
from models.order import Order

from services.policy_engine import check_policy
from services.inventory_service import (
    check_stock,
    deduct_stock,
    restore_stock,
)
from services.payment_service import process_payment
from sqlalchemy import update


DEFAULT_POLICY = {
    "max_amount": 100000,
    "max_quantity": 10,
    "allowed_actions": ["purchase"],
}


def _inventory_deduction_succeeded(result):
    """
    Support inventory services that indicate successful deduction
    with either a success flag or a positive deducted_quantity.
    """
    if result.get("success") is True:
        return True

    deducted_quantity = result.get("deducted_quantity", 0)

    try:
        return int(deducted_quantity) > 0
    except (TypeError, ValueError):
        return False


def _inventory_restoration_succeeded(result):
    """
    Support inventory services that indicate successful restoration
    with either a success flag or a positive restored_quantity.
    """
    if result.get("success") is True:
        return True

    restored_quantity = result.get("restored_quantity", 0)

    try:
        return int(restored_quantity) > 0
    except (TypeError, ValueError):
        return False


def save_order(order_result, product, quantity, amount, payment_method):
    """
    Save the final order result to PostgreSQL.
    Both successful and failed orders are recorded.
    """
    db = SessionLocal()

    try:
        order = Order(
            order_id=order_result["order_id"],
            product=product,
            quantity=quantity,
            amount=amount,
            payment_method=payment_method,
            status="Success" if order_result["success"] else "Failed",
            stage=order_result["stage"],
            message=order_result["message"],
            details=json.dumps(order_result, default=str),
        )

        db.add(order)
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def create_order(product, quantity, amount, payment_method="card"):
    order_id = "ORD-" + uuid.uuid4().hex[:8].upper()

    intent = {
        "action": "purchase",
        "amount": amount,
        "quantity": quantity,
        "target": product,
    }

    policy_result = check_policy(intent, DEFAULT_POLICY)

    # 1. Policy check
    if not policy_result.get("allowed", False):
        result = {
            "order_id": order_id,
            "success": False,
            "stage": "policy",
            "message": "Order blocked by policy",
            "policy": policy_result,
            "inventory": None,
            "payment": None,
        }

        save_order(result, product, quantity, amount, payment_method)
        return result

    # 2. Check available inventory
    inventory_result = check_stock(product, quantity)

    if not inventory_result.get("available", False):
        result = {
            "order_id": order_id,
            "success": False,
            "stage": "inventory",
            "message": inventory_result.get(
                "message",
                "Inventory check failed",
            ),
            "policy": policy_result,
            "inventory": inventory_result,
            "payment": None,
        }

        save_order(result, product, quantity, amount, payment_method)
        return result

    # 3. Deduct/reserve inventory
    deduction_result = deduct_stock(product, quantity)

    if not _inventory_deduction_succeeded(deduction_result):
        result = {
            "order_id": order_id,
            "success": False,
            "stage": "inventory",
            "message": deduction_result.get(
                "message",
                "Unable to reserve inventory",
            ),
            "policy": policy_result,
            "inventory": deduction_result,
            "payment": None,
        }

        save_order(result, product, quantity, amount, payment_method)
        return result

    # 4. Process payment
    payment_result = process_payment(amount, payment_method)

    if not payment_result.get("success", False):

        # 5. Payment failed: restore the reserved inventory
        restoration_result = restore_stock(product, quantity)

        inventory_result = {
            **deduction_result,
            "restoration": restoration_result,
        }

        if not _inventory_restoration_succeeded(restoration_result):
            result = {
                "order_id": order_id,
                "success": False,
                "stage": "inventory_restoration",
                "message": (
                    "Payment failed and inventory restoration "
                    "requires attention"
                ),
                "policy": policy_result,
                "inventory": inventory_result,
                "payment": payment_result,
            }

        else:
            result = {
                "order_id": order_id,
                "success": False,
                "stage": "payment",
                "message": "Order failed because payment failed",
                "policy": policy_result,
                "inventory": inventory_result,
                "payment": payment_result,
            }

        save_order(result, product, quantity, amount, payment_method)
        return result

    # 6. Payment succeeded: complete the order
    result = {
        "order_id": order_id,
        "success": True,
        "stage": "completed",
        "message": "Order completed successfully",
        "policy": policy_result,
        "inventory": deduction_result,
        "payment": payment_result,
    }

    save_order(result, product, quantity, amount, payment_method)
    return result

def cancel_order(order_id):
    """
    Cancel a completed order and restore its inventory.

    The order is first moved to Cancellation Pending using a conditional
    database update. This prevents a repeated cancellation request from
    restoring the same inventory again.
    """
    db = SessionLocal()

    try:
        order = (
            db.query(Order)
            .filter(Order.order_id == order_id)
            .first()
        )

        if order is None:
            return {
                "success": False,
                "status_code": 404,
                "message": "Order not found",
            }

        if order.status != "Success" or order.stage != "completed":
            return {
                "success": False,
                "status_code": 409,
                "message": (
                    "Only successful completed orders can be cancelled. "
                    f"Current status: {order.status}, stage: {order.stage}"
                ),
            }

        # Atomically claim cancellation before restoring inventory.
        claim_result = (
            db.query(Order)
            .filter(
                Order.order_id == order_id,
                Order.status == "Success",
                Order.stage == "completed",
            )
            .update(
                {
                    Order.status: "Cancellation Pending",
                    Order.stage: "cancellation_pending",
                    Order.message: "Cancellation is being processed",
                },
                synchronize_session=False,
            )
        )

        if claim_result != 1:
            db.rollback()
            return {
                "success": False,
                "status_code": 409,
                "message": "Order is already being cancelled or is no longer eligible",
            }

        db.commit()

        # Restore inventory only after the order is claimed.
        try:
            restoration_result = restore_stock(
                order.product,
                order.quantity,
            )
        except Exception as exc:
            restoration_result = {
                "success": False,
                "message": str(exc),
            }

        restoration_succeeded = _inventory_restoration_succeeded(
            restoration_result
        )

        # Reload order after the separate inventory-service session.
        order = (
            db.query(Order)
            .filter(Order.order_id == order_id)
            .first()
        )

        try:
            existing_details = (
                json.loads(order.details)
                if order.details
                else {}
            )
        except (json.JSONDecodeError, TypeError):
            existing_details = {
                "previous_details": order.details
            }

        if not isinstance(existing_details, dict):
            existing_details = {
                "previous_details": existing_details
            }

        existing_details["cancellation"] = {
            "requested": True,
            "restoration": restoration_result,
        }

        if restoration_succeeded:
            order.status = "Cancelled"
            order.stage = "cancelled"
            order.message = "Order cancelled and inventory restored"
            existing_details["cancellation"]["success"] = True
        else:
            order.status = "Cancellation Attention"
            order.stage = "cancellation_restore_failed"
            order.message = (
                "Cancellation was claimed, but inventory restoration "
                "requires attention. Do not retry automatically."
            )
            existing_details["cancellation"]["success"] = False

        order.details = json.dumps(existing_details, default=str)
        db.commit()

        return {
            "success": restoration_succeeded,
            "order_id": order.order_id,
            "status": order.status,
            "stage": order.stage,
            "message": order.message,
            "inventory": restoration_result,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()