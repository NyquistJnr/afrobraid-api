"""Conservative, regex/keyword-based detector for chat content the platform
doesn't want flowing through in the clear: contact details (phone numbers,
emails, social/messaging handles) and payment/account details - both are
routes for a customer and braider to take a booking (and its protections,
and Afrobraid's fee) off-platform.

This is intentionally simple pattern matching, not an ML classifier - it
will have false positives (e.g. a long date written with dashes) and false
negatives (e.g. a phone number spelled out in words). Given the business
cost of a leaked message is low (the sender can rephrase) and the cost of a
missed violation is what we're actually trying to avoid, erring toward
over-flagging is the right tradeoff here.
"""

import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# A run of digits, loosely separated by spaces/dashes/dots/parens, long
# enough to plausibly be a phone number or account/routing/IBAN-style
# number. The digit *count* (not the span length) is what's checked below,
# so stray punctuation doesn't dodge the filter.
_DIGIT_RUN_RE = re.compile(r"(?:\d[\s\-.\(\)]*){7,}\d")

_URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s]+|\b[a-zA-Z0-9\-]+\.(?:com|net|org|io|me|link|co)\b[^\s]*",
    re.IGNORECASE,
)

# Case-insensitive keywords/phrases that strongly suggest an attempt to move
# communication or payment off-platform.
_KEYWORD_PATTERNS: dict[str, re.Pattern] = {
    "messaging_app": re.compile(
        r"\b(whats\s*app|telegram|instagram|\binsta\b|\big\b|snap\s*chat|\bsnap\b|we\s*chat|"
        r"\bkik\b|\bsignal\b|\bviber\b|\bmessenger\b|\bimessage\b)\b",
        re.IGNORECASE,
    ),
    "off_platform_payment": re.compile(
        r"\b(cash\s*app|\bvenmo\b|\bzelle\b|\bpaypal\b|bank\s*transfer|account\s*number|"
        r"routing\s*number|\biban\b|wire\s*transfer|pay\s*me\s*directly|pay\s*(you|me)\s*cash)\b",
        re.IGNORECASE,
    ),
    "off_platform_contact": re.compile(
        r"\b(text\s*me|call\s*me|my\s*number\s*is|reach\s*me\s*at|contact\s*me\s*(at|on)|"
        r"off\s*(the\s*)?(app|platform)|outside\s*(the\s*)?(app|platform))\b",
        re.IGNORECASE,
    ),
}


def detect_violations(text: str) -> list[str]:
    """Returns a list of violation-type tags found in `text` - empty if
    clean. A non-empty result means the caller should flag the message
    rather than store/display it (see chat.service.send_message)."""
    violations: list[str] = []

    if _EMAIL_RE.search(text):
        violations.append("email")

    digit_run = _DIGIT_RUN_RE.search(text)
    if digit_run and sum(c.isdigit() for c in digit_run.group()) >= 7:
        violations.append("phone_or_account_number")

    if _URL_RE.search(text):
        violations.append("url")

    for tag, pattern in _KEYWORD_PATTERNS.items():
        if pattern.search(text):
            violations.append(tag)

    return violations
