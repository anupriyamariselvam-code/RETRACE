import json
import hashlib
from sqlalchemy import text
from database import engine


TRACE_ID = "TR-E2D92D"
EVENT_ID = 385


def calculate_event_hash(trace_id, stage, status, details_json):
    """Calculate the SHA-256 hash using the same logic as routes/trace.py."""

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


query = text("""
    SELECT
        id,
        trace_id,
        stage,
        status,
        details,
        event_hash
    FROM trace_events
    WHERE id = :event_id
      AND trace_id = :trace_id
""")


with engine.connect() as connection:
    event = connection.execute(
        query,
        {
            "event_id": EVENT_ID,
            "trace_id": TRACE_ID
        }
    ).mappings().first()


if event is None:
    print("Event not found.")

else:
    details = event["details"]

    print("=" * 60)
    print("TRACE EVENT HASH DIAGNOSTIC")
    print("=" * 60)

    print("Event ID:", event["id"])
    print("Trace ID repr:", repr(event["trace_id"]))
    print("Stage repr:", repr(event["stage"]))
    print("Status repr:", repr(event["status"]))
    print("Stored hash repr:", repr(event["event_hash"]))

    print("\n--- DETAILS ---")
    print("Details repr:", repr(details))

    if details is not None:
        print("Details length:", len(details))
        print("Details bytes:", details.encode("utf-8").hex())
    else:
        print("Details is NULL")

    print("\n--- HASH VERIFICATION ---")

    calculated_hash = calculate_event_hash(
        event["trace_id"],
        event["stage"],
        event["status"],
        details
    )

    stored_hash = event["event_hash"]

    print("Calculated hash:", calculated_hash)
    print("Stored hash:    ", stored_hash)
    print("Hash matches:   ", calculated_hash == stored_hash)

    print("\n--- RESULT ---")

    if calculated_hash == stored_hash:
        print("VALID: The stored hash matches the current event data.")
    else:
        print("MISMATCH: The stored hash does not match the current event data.")

    print("\nNo database changes were made.")
    print("=" * 60)