import re


def extract_intent(user_input: str):
    text = user_input.strip()

    if not text:
        return {
            "original_request": "",
            "action": None,
            "amount": None,
            "currency": None,
            "target": None,
            "quantity": None,
            "keywords": [],
            "confidence": 0.0
        }

    # -------------------------------------------------
    # 1. Extract amount and currency
    # -------------------------------------------------

    amount = None
    currency = None

    currency_patterns = [
        (r"₹\s*(\d+(?:\.\d+)?)", "INR"),
        (r"\bRs\.?\s*(\d+(?:\.\d+)?)", "INR"),
        (r"\brupees?\s*(\d+(?:\.\d+)?)", "INR"),
        (r"\$\s*(\d+(?:\.\d+)?)", "USD"),
        (r"\bUSD\s*(\d+(?:\.\d+)?)", "USD"),
        (r"€\s*(\d+(?:\.\d+)?)", "EUR"),
        (r"\bEUR\s*(\d+(?:\.\d+)?)", "EUR"),
    ]

    for pattern, detected_currency in currency_patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            amount = float(match.group(1))
            currency = detected_currency
            break

    # Accept a bare amount following "for", but do not mistake
    # a product quantity for a payment amount.
    if amount is None:
        match = re.search(
            r"\bfor\s+(\d+(?:\.\d+)?)\b",
            text,
            re.IGNORECASE
        )

        if match:
            amount = float(match.group(1))
            currency = "UNKNOWN"

    # -------------------------------------------------
    # 2. Detect action
    # -------------------------------------------------

    action = "unknown"

    action_patterns = {
        "payment": r"\b(pay|payment|paying|settle)\b",
        "transfer": r"\b(transfer|send|sending)\b",
        "purchase": r"\b(buy|purchase|order|buying|purchasing)\b",
        "booking": r"\b(book|booking|reserve|reservation)\b",
        "withdrawal": r"\b(withdraw|withdrawal|cash)\b",
        "refund": r"\b(refund|return|returning)\b",
        "subscription": r"\b(subscription|subscribe|renew)\b",
        "delivery": r"\b(deliver|delivery|shipping)\b",
    }

    for action_name, pattern in action_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            action = action_name
            break

    # -------------------------------------------------
    # 3. Extract quantity
    # -------------------------------------------------

    quantity = None

    # Capture an explicit quantity immediately after a purchase verb.
    quantity_match = re.search(
        r"\b(?:buy|purchase|order|buying|purchasing)\s+"
        r"(\d+)\s+",
        text,
        re.IGNORECASE
    )

    if quantity_match:
        quantity = int(quantity_match.group(1))

    # Also recognize quantities expressed with common units.
    if quantity is None:
        quantity_match = re.search(
            r"\b(\d+)\s+(?:items?|pieces?|units?|tickets?|"
            r"products?|rooms?|nights?|days?)\b",
            text,
            re.IGNORECASE
        )

        if quantity_match:
            quantity = int(quantity_match.group(1))

    # -------------------------------------------------
    # 4. Extract target product
    # -------------------------------------------------

    target = None

    # Extract the product phrase after a purchase verb.
    # Stop before payment details or common request qualifiers.
    product_match = re.search(
        r"\b(?:buy|purchase|order|buying|purchasing)\s+"
        r"(?:\d+\s+)?"
        r"(?:a\s+|an\s+|the\s+)?"
        r"([a-zA-Z][a-zA-Z-]*(?:\s+[a-zA-Z][a-zA-Z-]*){0,2})"
        r"(?=\s+(?:for|at|with|using|please)\b|$)",
        text,
        re.IGNORECASE
    )

    if product_match:
        target = product_match.group(1).strip().lower()

        product_aliases = {
            "laptops": "laptop",
            "phones": "phone",
            "headphones": "headphones",
            "keyboards": "keyboard",
            "mice": "mouse"
        }

        target = product_aliases.get(target, target)

    # -------------------------------------------------
    # 5. Extract useful keywords
    # -------------------------------------------------

    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

    stop_words = {
        "the", "and", "for", "from", "with", "that", "this",
        "want", "need", "please", "make", "can", "you",
        "my", "your", "to"
    }

    keywords = [
        word for word in words
        if word not in stop_words
    ]

    keywords = list(dict.fromkeys(keywords))

    # -------------------------------------------------
    # 6. Calculate simple confidence
    # -------------------------------------------------

    confidence = 0.4

    if action != "unknown":
        confidence += 0.3

    if amount is not None:
        confidence += 0.2

    if target:
        confidence += 0.1

    confidence = min(confidence, 1.0)

    # -------------------------------------------------
    # 7. Return structured intent
    # -------------------------------------------------

    return {
        "original_request": text,
        "action": action,
        "amount": amount,
        "currency": currency,
        "target": target,
        "quantity": quantity,
        "keywords": keywords,
        "confidence": confidence
    }