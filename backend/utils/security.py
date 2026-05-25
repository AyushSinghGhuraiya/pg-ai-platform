"""
Security utilities: HMAC verification, phone normalisation, rate limiting.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Optional


# ── Meta webhook signature ────────────────────────────────────────────────────

def verify_meta_signature(
    payload: bytes,
    signature_header: Optional[str],
    app_secret: str,
) -> bool:
    """
    Verify Meta's X-Hub-Signature-256 header.
    Header format: 'sha256=<hex-digest>'
    Returns False (not raises) on any anomaly so callers can log + 401.
    """
    if not signature_header or not app_secret:
        return False
    if not signature_header.startswith("sha256="):
        return False

    expected = signature_header[len("sha256="):]
    computed = hmac.new(
        app_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    # Constant-time compare prevents timing attacks
    return hmac.compare_digest(computed, expected)


# ── Phone number helpers ───────────────────────────────────────────────────────

# Matches Indian mobile numbers in various formats
_INDIAN_MOBILE_RE = re.compile(
    r"^(?:\+?91|0)?([6-9]\d{9})$"
)

def normalize_phone(raw: str) -> str:
    """
    Normalise any plausible Indian mobile to E.164 (+91XXXXXXXXXX).
    Falls back to +<digits> for non-Indian numbers.
    WhatsApp sends numbers without '+', e.g. '919876543210'.
    """
    if not raw:
        return raw

    digits = re.sub(r"[^\d]", "", raw)

    # Indian number: 10 digits starting 6-9
    m = _INDIAN_MOBILE_RE.match(raw.strip())
    if m:
        return "+91" + m.group(1)

    # Already has country code (12 digits starting 91)
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits

    # Generic: prefix + if not already there
    if raw.strip().startswith("+"):
        return "+" + digits
    return "+" + digits


def to_whatsapp_phone(e164: str) -> str:
    """
    Convert E.164 (+919876543210) → Meta format (919876543210, no plus).
    Meta's API rejects the leading '+'.
    """
    return e164.lstrip("+")


def validate_phone(phone: str) -> bool:
    """Return True if phone looks like a valid E.164 number."""
    return bool(re.match(r"^\+\d{7,15}$", phone))


# ── Twilio webhook signature ───────────────────────────────────────────────────

def verify_twilio_signature(
    signature: Optional[str],
    url: str,
    params: dict,
    auth_token: str,
) -> bool:
    """
    Verify Twilio's X-Twilio-Signature header using Twilio's RequestValidator.
    Returns False on any anomaly so callers can log + 403.
    """
    if not signature or not auth_token:
        return False
    try:
        from twilio.request_validator import RequestValidator
        return RequestValidator(auth_token).validate(url, params, signature)
    except Exception:
        return False


# ── Twilio phone format helpers ────────────────────────────────────────────────

def to_twilio_format(phone: str) -> str:
    """Convert E.164 (+91XXXXXXXXXX) → Twilio WhatsApp format (whatsapp:+91XXXXXXXXXX)."""
    e164 = phone if phone.startswith("+") else "+" + phone
    return f"whatsapp:{e164}"


def from_twilio_format(phone: str) -> str:
    """Convert whatsapp:+91XXXXXXXXXX → E.164 (+91XXXXXXXXXX)."""
    return phone.replace("whatsapp:", "")
