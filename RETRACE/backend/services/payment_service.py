# Payment Service
# Simulates payment processing for RETRACE.


def process_payment(amount, payment_method="card"):
    """
    Simulate a payment.
    """

    if amount <= 0:
        return {
            "success": False,
            "amount": amount,
            "payment_method": payment_method,
            "status": "FAILED",
            "message": "Invalid payment amount"
        }

    return {
        "success": True,
        "amount": amount,
        "payment_method": payment_method,
        "status": "SUCCESS",
        "message": "Payment processed successfully"
    }