from fastapi.testclient import TestClient
import pytest

from main import app
from database import SessionLocal
from models.inventory import InventoryItem
from models.trace_event import TraceEvent
from models.order import Order
from services.order_service import create_order


INITIAL_INVENTORY = {
    "laptop": 5,
    "phone": 10,
    "headphones": 20,
    "keyboard": 15,
    "mouse": 25,
}


@pytest.fixture(autouse=True)
def reset_inventory():
    """
    Give each test predictable inventory quantities.

    Restore the original database quantities after the test.
    """
    db = SessionLocal()
    original_quantities = {}

    try:
        for product, default_quantity in INITIAL_INVENTORY.items():
            item = (
                db.query(InventoryItem)
                .filter(InventoryItem.product == product)
                .first()
            )

            if item is None:
                db.add(
                    InventoryItem(
                        product=product,
                        quantity=default_quantity,
                    )
                )
                original_quantities[product] = None
            else:
                original_quantities[product] = item.quantity
                item.quantity = default_quantity

        db.commit()

        yield

    finally:
        try:
            for product, original_quantity in original_quantities.items():
                item = (
                    db.query(InventoryItem)
                    .filter(InventoryItem.product == product)
                    .first()
                )

                if item is None:
                    continue

                if original_quantity is None:
                    db.delete(item)
                else:
                    item.quantity = original_quantity

            db.commit()

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()


client = TestClient(app)


def get_inventory_quantity(product):
    db = SessionLocal()

    try:
        item = (
            db.query(InventoryItem)
            .filter(InventoryItem.product == product)
            .first()
        )

        assert item is not None, f"Inventory item not found: {product}"
        return item.quantity

    finally:
        db.close()


def test_create_trace_success():
    response = client.post(
        "/trace/",
        json={"user_input": "Buy 2 laptops for Rs. 50000"},
    )

    assert response.status_code == 200
    data = response.json()

    assert "trace_id" in data
    assert data["status"] == "COMPLETED"
    assert data["proof"]["trace_saved"] is True


def test_retrieve_trace_evidence():
    create_response = client.post(
        "/trace/",
        json={"user_input": "Buy 2 laptops for Rs. 50000"},
    )

    assert create_response.status_code == 200
    trace_id = create_response.json()["trace_id"]

    detail_response = client.get(f"/trace/{trace_id}")

    assert detail_response.status_code == 200
    data = detail_response.json()

    assert data["trace_id"] == trace_id
    assert len(data["evidence"]) > 0

    for event in data["evidence"]:
        assert event["integrity_status"] == "VALID"
        assert len(event["event_hash"]) == 64


def test_policy_blocks_high_amount_purchase():
    response = client.post(
        "/trace/",
        json={"user_input": "Buy 2 laptops for Rs. 150000"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "BLOCKED"
    assert data["policy"]["allowed"] is False
    assert data["proof"]["order_executed"] is False


def test_missing_information_request():
    response = client.post(
        "/trace/",
        json={"user_input": "Buy 2 laptops"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "NEEDS_INFORMATION"
    assert data["order"] is None
    assert data["proof"]["order_executed"] is False


def test_insufficient_inventory():
    response = client.post(
        "/trace/",
        json={"user_input": "Buy 6 laptops for Rs. 50000"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "FAILED"
    assert data["order"]["success"] is False
    assert data["order"]["stage"] == "inventory"

    inventory_result = data["order"]["inventory"]

    assert inventory_result["available"] is False
    assert inventory_result["requested_quantity"] == 6
    assert inventory_result["available_quantity"] == 5

    assert data["proof"]["payment_processed"] is False


def test_failed_order_proof_is_accurate():
    response = client.post(
        "/trace/",
        json={"user_input": "Buy 6 laptops for Rs. 50000"},
    )

    assert response.status_code == 200

    data = response.json()
    proof = data["proof"]

    assert data["status"] == "FAILED"
    assert proof["order_attempted"] is True
    assert proof["order_succeeded"] is False
    assert proof["order_executed"] is False
    assert proof["inventory_checked"] is True
    assert proof["payment_processed"] is False


def test_unsupported_product_does_not_process_payment():
    response = client.post(
        "/trace/",
        json={"user_input": "Buy 1 tablet for Rs. 50000"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "FAILED"
    assert data["order"]["success"] is False
    assert data["order"]["stage"] == "inventory"
    assert data["proof"]["payment_processed"] is False
    assert data["proof"]["order_succeeded"] is False


def test_zero_quantity_is_invalid():
    response = client.post(
        "/trace/",
        json={"user_input": "Buy 0 laptops for Rs. 50000"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "INVALID_INPUT"
    assert data["proof"]["order_attempted"] is False
    assert data["proof"]["payment_processed"] is False


def test_trace_detects_tampered_event_details():
    create_response = client.post(
        "/trace/",
        json={"user_input": "Buy 1 laptop for Rs. 50000"},
    )

    assert create_response.status_code == 200
    trace_id = create_response.json()["trace_id"]

    db = SessionLocal()
    event_id = None
    original_details = None
    original_event_hash = None

    try:
        event = (
            db.query(TraceEvent)
            .filter(TraceEvent.trace_id == trace_id)
            .order_by(TraceEvent.id)
            .first()
        )

        assert event is not None

        event_id = event.id
        original_details = event.details
        original_event_hash = event.event_hash

        event.details = (original_details or "") + " tampered"
        db.commit()

        detail_response = client.get(f"/trace/{trace_id}")

        assert detail_response.status_code == 200

        evidence = detail_response.json()["evidence"]

        tampered_events = [
            item
            for item in evidence
            if item["event_hash"] == original_event_hash
        ]

        assert len(tampered_events) == 1
        assert tampered_events[0]["integrity_status"] == "TAMPERED"

    finally:
        if event_id is not None:
            db.rollback()

            event_to_restore = (
                db.query(TraceEvent)
                .filter(TraceEvent.id == event_id)
                .first()
            )

            if event_to_restore is not None:
                event_to_restore.details = original_details
                event_to_restore.event_hash = original_event_hash
                db.commit()

        db.close()


def test_order_api_blocks_amount_above_policy():
    response = client.post(
        "/order/create",
        json={
            "product": "laptop",
            "quantity": 1,
            "amount": 150000,
            "payment_method": "card",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is False
    assert data["stage"] == "policy"
    assert data["policy"]["decision"] == "BLOCKED"
    assert data["inventory"] is None
    assert data["payment"] is None
    assert any(
        "exceeds the maximum" in violation
        for violation in data["policy"]["violations"]
    )


def test_order_api_blocks_quantity_above_policy():
    response = client.post(
        "/order/create",
        json={
            "product": "laptop",
            "quantity": 11,
            "amount": 50000,
            "payment_method": "card",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is False
    assert data["stage"] == "policy"
    assert data["policy"]["decision"] == "BLOCKED"
    assert data["inventory"] is None
    assert data["payment"] is None
    assert any(
        "exceeds the maximum allowed quantity" in violation
        for violation in data["policy"]["violations"]
    )


def test_successful_order_deducts_inventory():
    result = create_order(
        product="laptop",
        quantity=2,
        amount=50000,
        payment_method="card",
    )

    assert result["success"] is True
    assert result["stage"] == "completed"
    assert get_inventory_quantity("laptop") == 3
    assert result["inventory"]["remaining_quantity"] == 3


def test_failed_payment_does_not_deduct_inventory(monkeypatch):
    def fake_failed_payment(amount, payment_method):
        return {
            "success": False,
            "message": "Simulated payment failure",
        }

    monkeypatch.setattr(
        "services.order_service.process_payment",
        fake_failed_payment,
    )

    result = create_order(
        product="laptop",
        quantity=2,
        amount=50000,
        payment_method="card",
    )

    assert result["success"] is False
    assert result["stage"] == "payment"
    assert get_inventory_quantity("laptop") == 5


def test_insufficient_stock_does_not_deduct_inventory():
    result = create_order(
        product="laptop",
        quantity=6,
        amount=50000,
        payment_method="card",
    )

    assert result["success"] is False
    assert result["stage"] == "inventory"
    assert get_inventory_quantity("laptop") == 5


# ---------------------------------------------------------
# Order history and retrieval tests
# ---------------------------------------------------------

def delete_test_order(order_id):
    """Remove a test-created order from the database."""
    db = SessionLocal()

    try:
        order = (
            db.query(Order)
            .filter(Order.order_id == order_id)
            .first()
        )

        if order is not None:
            db.delete(order)
            db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def test_get_order_history():
    create_response = client.post(
        "/order/create",
        json={
            "product": "phone",
            "quantity": 1,
            "amount": 1000,
            "payment_method": "card",
        },
    )

    assert create_response.status_code == 200
    order_id = create_response.json()["order_id"]

    try:
        response = client.get("/order/history")

        assert response.status_code == 200

        data = response.json()

        assert "orders" in data
        assert data["count"] >= 1

        matching_orders = [
            order
            for order in data["orders"]
            if order["order_id"] == order_id
        ]

        assert len(matching_orders) == 1

        saved_order = matching_orders[0]

        assert saved_order["product"] == "phone"
        assert saved_order["quantity"] == 1
        assert saved_order["status"] == "Success"
        assert saved_order["stage"] == "completed"

    finally:
        delete_test_order(order_id)


def test_get_order_by_id():
    create_response = client.post(
        "/order/create",
        json={
            "product": "phone",
            "quantity": 1,
            "amount": 1000,
            "payment_method": "card",
        },
    )

    assert create_response.status_code == 200
    order_id = create_response.json()["order_id"]

    try:
        response = client.get(f"/order/{order_id}")

        assert response.status_code == 200

        data = response.json()

        assert data["order_id"] == order_id
        assert data["product"] == "phone"
        assert data["quantity"] == 1
        assert data["amount"] == 1000
        assert data["status"] == "Success"
        assert data["stage"] == "completed"

        assert data["details"] is not None
        assert data["details"]["success"] is True
        assert data["details"]["payment"]["success"] is True

    finally:
        delete_test_order(order_id)


def test_get_nonexistent_order_returns_404():
    response = client.get("/order/ORD-DOESNOTEXIST")

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"