def check_policy(intent, policy):
    """
    Check whether an extracted intent follows
    the user's defined policy.
    """

    violations = []

    # -----------------------------------------
    # 1. Check maximum amount
    # -----------------------------------------

    amount = intent.get("amount")
    max_amount = policy.get("max_amount")

    if amount is not None and max_amount is not None:

        if amount > max_amount:
            violations.append(
                f"Amount {amount} exceeds the maximum "
                f"allowed amount of {max_amount}"
            )

    # -----------------------------------------
    # 2. Check allowed actions
    # -----------------------------------------

    action = intent.get("action")
    allowed_actions = policy.get("allowed_actions")

    if allowed_actions:

        if action not in allowed_actions:

            violations.append(
                f"Action '{action}' is not allowed"
            )

    # -----------------------------------------
    # 3. Check quantity
    # -----------------------------------------

    quantity = intent.get("quantity")
    max_quantity = policy.get("max_quantity")

    if quantity is not None and max_quantity is not None:

        if quantity > max_quantity:

            violations.append(
                f"Quantity {quantity} exceeds the "
                f"maximum allowed quantity of {max_quantity}"
            )

    # -----------------------------------------
    # 4. Final decision
    # -----------------------------------------

    if violations:

        return {
            "allowed": False,
            "decision": "BLOCKED",
            "violations": violations
        }

    return {
        "allowed": True,
        "decision": "ALLOWED",
        "violations": []
    }