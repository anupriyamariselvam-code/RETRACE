from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import uuid
import json
import hashlib

from database import get_db
from models.trace import Trace
from models.trace_event import TraceEvent

from services.intent_parser import extract_intent
from services.policy_engine import check_policy
from services.order_service import create_order


router = APIRouter(
    prefix="/trace",
    tags=["RETRACE"]
)


class TraceRequest(BaseModel):
    user_input: str


DEFAULT_POLICY = {
    "max_amount": 100000,
    "max_quantity": 10,
    "allowed_actions": ["purchase"]
}


# --------------------------------------------------
# SHA-256 EVENT HASH
# --------------------------------------------------

def calculate_event_hash(trace_id, stage, status, details_json):
    """
    Create a SHA-256 hash using the event's identifying
    information and serialized details.
    """

    payload = json.dumps(
        [
            trace_id,
            stage,
            status,
            details_json
        ],
        ensure_ascii=False,
        separators=(",", ":")
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


# --------------------------------------------------
# SAVE TRACE EVENT
# --------------------------------------------------

def save_event(db, trace_id, stage, status, details):

    details_json = json.dumps(
        details,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str
    )

    event_hash = calculate_event_hash(
        trace_id,
        stage,
        status,
        details_json
    )

    event = TraceEvent(
        trace_id=trace_id,
        stage=stage,
        status=status,
        details=details_json,
        event_hash=event_hash
    )

    db.add(event)


# --------------------------------------------------
# GET ALL TRACES
# --------------------------------------------------

@router.get("/")
def get_traces(db: Session = Depends(get_db)):

    traces = db.query(Trace).order_by(
        Trace.id.desc()
    ).all()

    return [
        {
            "id": trace.id,
            "trace_id": trace.trace_id,
            "request": trace.user_input,
            "status": trace.status,
            "timestamp": trace.timestamp
        }
        for trace in traces
    ]


# --------------------------------------------------
# GET TRACE DETAILS AND VERIFY EVENT HASHES
# --------------------------------------------------

@router.get("/{trace_id}")
def get_trace_detail(
    trace_id: str,
    db: Session = Depends(get_db)
):

    trace = db.query(Trace).filter(
        Trace.trace_id == trace_id
    ).first()

    if not trace:
        raise HTTPException(
            status_code=404,
            detail="Trace not found"
        )

    events = db.query(TraceEvent).filter(
        TraceEvent.trace_id == trace_id
    ).order_by(
        TraceEvent.id.asc()
    ).all()

    evidence = []

    for event in events:

        # Decode stored JSON details
        try:
            details = (
                json.loads(event.details)
                if event.details
                else None
            )
        except json.JSONDecodeError:
            details = event.details

        # Verify integrity if a hash exists
        if event.event_hash:

            calculated_hash = calculate_event_hash(
                event.trace_id,
                event.stage,
                event.status,
                event.details
            )

            integrity_status = (
                "VALID"
                if calculated_hash == event.event_hash
                else "TAMPERED"
            )

        else:
            # Existing records may not have hashes
            integrity_status = "NOT_CHECKED"

        evidence.append({
            "stage": event.stage,
            "status": event.status,
            "details": details,
            "timestamp": event.timestamp,
            "event_hash": event.event_hash,
            "integrity_status": integrity_status
        })

    return {
        "trace_id": trace.trace_id,
        "request": trace.user_input,
        "status": trace.status,
        "timestamp": trace.timestamp,
        "evidence": evidence
    }


# --------------------------------------------------
# EXECUTE RETRACE PIPELINE
# --------------------------------------------------

@router.post("/")
def create_trace(
    request: TraceRequest,
    db: Session = Depends(get_db)
):

    trace_id = "TR-" + uuid.uuid4().hex[:6].upper()

    # Track which stages were reached
    inventory_checked = False
    payment_processed = False
    order_attempted = False
    order_succeeded = False

    # Stage 1: Receive request
    new_trace = Trace(
        trace_id=trace_id,
        user_input=request.user_input,
        status="Received"
    )

    db.add(new_trace)
    db.commit()
    db.refresh(new_trace)

    save_event(
        db,
        trace_id,
        "request_received",
        "SUCCESS",
        {
            "user_input": request.user_input
        }
    )

    # Stage 2: Parse intent
    intent = extract_intent(
        request.user_input
    )

    save_event(
        db,
        trace_id,
        "intent_parser",
        "SUCCESS",
        intent
    )

    # Stage 3: Evaluate policy
    policy_result = check_policy(
        intent,
        DEFAULT_POLICY
    )

    policy_status = (
        "ALLOWED"
        if policy_result["allowed"]
        else "BLOCKED"
    )

    save_event(
        db,
        trace_id,
        "policy_engine",
        policy_status,
        policy_result
    )

    # Stop if policy blocks the request
    if not policy_result["allowed"]:

        new_trace.status = "Blocked"

        db.commit()

        return {
            "trace_id": trace_id,
            "status": "BLOCKED",
            "intent": intent,
            "policy": policy_result,
            "order": None,
            "message": "Request blocked by policy",
            "proof": {
                "request_received": True,
                "intent_parsed": True,
                "policy_checked": True,
                "inventory_checked": False,
                "payment_processed": False,
                "order_attempted": False,
                "order_succeeded": False,
                "order_executed": False,
                "trace_saved": True
            }
        }

    # Stage 4: Validate required information
    product = intent.get("target")
    quantity = intent.get("quantity")
    amount = intent.get("amount")

    # Missing fields are different from invalid values.
    if not product or quantity is None or amount is None:

        new_trace.status = "Needs Information"

        save_event(
            db,
            trace_id,
            "input_validation",
            "NEEDS_INFORMATION",
            {
                "product": product,
                "quantity": quantity,
                "amount": amount
            }
        )

        db.commit()

        return {
            "trace_id": trace_id,
            "status": "NEEDS_INFORMATION",
            "intent": intent,
            "policy": policy_result,
            "order": None,
            "message": (
                "Please provide a product, quantity, "
                "and payment amount."
            ),
            "proof": {
                "request_received": True,
                "intent_parsed": True,
                "policy_checked": True,
                "inventory_checked": False,
                "payment_processed": False,
                "order_attempted": False,
                "order_succeeded": False,
                "order_executed": False,
                "trace_saved": True
            }
        }

    # Stage 4B: Validate quantity
    if quantity <= 0:

        new_trace.status = "Invalid Input"

        save_event(
            db,
            trace_id,
            "input_validation",
            "INVALID_INPUT",
            {
                "product": product,
                "quantity": quantity,
                "amount": amount,
                "reason": "Quantity must be greater than zero"
            }
        )

        db.commit()

        return {
            "trace_id": trace_id,
            "status": "INVALID_INPUT",
            "intent": intent,
            "policy": policy_result,
            "order": None,
            "message": "Quantity must be greater than zero.",
            "proof": {
                "request_received": True,
                "intent_parsed": True,
                "policy_checked": True,
                "inventory_checked": False,
                "payment_processed": False,
                "order_attempted": False,
                "order_succeeded": False,
                "order_executed": False,
                "trace_saved": True
            }
        }

    # Stage 5: Execute existing Order Service
    order_attempted = True

    order_result = create_order(
        product,
        quantity,
        amount
    )

    order_succeeded = bool(
        order_result.get("success", False)
    )

    # Record inventory evidence
    inventory_result = order_result.get(
        "inventory"
    )

    if inventory_result is not None:

        inventory_checked = True

        inventory_status = (
            "AVAILABLE"
            if inventory_result.get("available")
            else "UNAVAILABLE"
        )

        save_event(
            db,
            trace_id,
            "inventory",
            inventory_status,
            inventory_result
        )

    # Record payment evidence
    payment_result = order_result.get(
        "payment"
    )

    if payment_result is not None:

        payment_processed = True

        save_event(
            db,
            trace_id,
            "payment",
            payment_result.get("status", "UNKNOWN"),
            payment_result
        )

    # Record order evidence
    order_status = (
        "COMPLETED"
        if order_succeeded
        else "FAILED"
    )

    save_event(
        db,
        trace_id,
        "order",
        order_status,
        order_result
    )

    # Stage 6: Update final trace status
    if order_succeeded:
        new_trace.status = "Completed"
        final_status = "COMPLETED"
    else:
        new_trace.status = "Failed"
        final_status = "FAILED"

    db.commit()
    db.refresh(new_trace)

    return {
        "trace_id": trace_id,
        "status": final_status,
        "intent": intent,
        "policy": policy_result,
        "order": order_result,
        "message": order_result.get(
            "message",
            "Order processing finished"
        ),
        "proof": {
            "request_received": True,
            "intent_parsed": True,
            "policy_checked": True,
            "inventory_checked": inventory_checked,
            "payment_processed": payment_processed,
            "order_attempted": order_attempted,
            "order_succeeded": order_succeeded,
            "order_executed": order_succeeded,
            "trace_saved": True
        }
    }