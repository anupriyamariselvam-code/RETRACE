# Inventory Service
# Handles database-backed product inventory.

from sqlalchemy import update

from database import SessionLocal
from models.inventory import InventoryItem


# Default inventory values.
# Existing product quantities are preserved when the app starts.
DEFAULT_INVENTORY = {
    "laptop": 5,
    "phone": 10,
    "headphones": 20,
    "keyboard": 15,
    "mouse": 25,
}


def initialize_inventory():
    """
    Insert default inventory products that do not already exist.
    Existing quantities are not overwritten.
    """

    db = SessionLocal()

    try:
        for product, quantity in DEFAULT_INVENTORY.items():
            existing_item = (
                db.query(InventoryItem)
                .filter(InventoryItem.product == product)
                .first()
            )

            if existing_item is None:
                new_item = InventoryItem(
                    product=product,
                    quantity=quantity,
                )
                db.add(new_item)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def check_stock(product, quantity):
    """
    Check whether a supported product has enough inventory.
    Does not change inventory.
    """

    db = SessionLocal()

    try:
        item = (
            db.query(InventoryItem)
            .filter(InventoryItem.product == product)
            .first()
        )

        if item is None:
            return {
                "available": False,
                "supported": False,
                "product": product,
                "requested_quantity": quantity,
                "available_quantity": 0,
                "message": f"Product '{product}' is not supported",
            }

        if quantity <= 0:
            return {
                "available": False,
                "supported": True,
                "product": product,
                "requested_quantity": quantity,
                "available_quantity": item.quantity,
                "message": "Quantity must be greater than zero",
            }

        if item.quantity < quantity:
            return {
                "available": False,
                "supported": True,
                "product": product,
                "requested_quantity": quantity,
                "available_quantity": item.quantity,
                "message": "Insufficient stock",
            }

        return {
            "available": True,
            "supported": True,
            "product": product,
            "requested_quantity": quantity,
            "available_quantity": item.quantity,
            "message": "Stock available",
        }

    finally:
        db.close()


def deduct_stock(product, quantity):
    """
    Deduct inventory using a conditional database update.
    The update only succeeds if sufficient stock is available.
    """

    db = SessionLocal()

    try:
        item = (
            db.query(InventoryItem)
            .filter(InventoryItem.product == product)
            .first()
        )

        if item is None:
            return {
                "available": False,
                "supported": False,
                "product": product,
                "requested_quantity": quantity,
                "available_quantity": 0,
                "message": f"Product '{product}' is not supported",
            }

        if quantity <= 0:
            return {
                "available": False,
                "supported": True,
                "product": product,
                "requested_quantity": quantity,
                "available_quantity": item.quantity,
                "message": "Quantity must be greater than zero",
            }

        result = db.execute(
            update(InventoryItem)
            .where(
                InventoryItem.product == product,
                InventoryItem.quantity >= quantity,
            )
            .values(
                quantity=InventoryItem.quantity - quantity
            )
        )

        if result.rowcount != 1:
            db.rollback()

            current_item = (
                db.query(InventoryItem)
                .filter(InventoryItem.product == product)
                .first()
            )

            current_quantity = (
                current_item.quantity if current_item else 0
            )

            return {
                "available": False,
                "supported": current_item is not None,
                "product": product,
                "requested_quantity": quantity,
                "available_quantity": current_quantity,
                "message": "Insufficient stock",
            }

        db.commit()

        updated_item = (
            db.query(InventoryItem)
            .filter(InventoryItem.product == product)
            .first()
        )

        return {
            "available": True,
            "supported": True,
            "product": product,
            "deducted_quantity": quantity,
            "remaining_quantity": updated_item.quantity,
            "message": "Inventory deducted successfully",
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def restore_stock(product, quantity):
    """
    Restore inventory after a failed payment.
    """

    db = SessionLocal()

    try:
        item = (
            db.query(InventoryItem)
            .filter(InventoryItem.product == product)
            .first()
        )

        if item is None:
            return {
                "available": False,
                "supported": False,
                "product": product,
                "message": f"Product '{product}' is not supported",
            }

        if quantity <= 0:
            return {
                "available": False,
                "supported": True,
                "product": product,
                "message": "Quantity must be greater than zero",
            }

        db.execute(
            update(InventoryItem)
            .where(InventoryItem.product == product)
            .values(
                quantity=InventoryItem.quantity + quantity
            )
        )

        db.commit()

        updated_item = (
            db.query(InventoryItem)
            .filter(InventoryItem.product == product)
            .first()
        )

        return {
            "available": True,
            "supported": True,
            "product": product,
            "restored_quantity": quantity,
            "remaining_quantity": updated_item.quantity,
            "message": "Inventory restored successfully",
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()