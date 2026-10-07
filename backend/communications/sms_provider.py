"""PhilSMS transport used by the existing SMS queue and dashboard."""

import json
import re
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


API_BASE = "https://dashboard.philsms.com/api/v3/"
REQUEST_TIMEOUT_SECONDS = 15
USER_AGENT = "BORJA-Dental-System/1.0"
ID_PREFIX = "philsms:"
_UID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,72}\Z")
_DELIVERY_STATES = {
    "queued": "submitted",
    "submitted": "submitted",
    "pending": "pending",
    "processing": "pending",
    "sent": "sent",
    "delivered": "delivered",
    "failed": "failed",
    "rejected": "failed",
    "undelivered": "failed",
    "refunded": "refunded",
}


class SmsProviderError(Exception):
    def __init__(self, message, *, uncertain=False, retryable=False):
        super().__init__(message)
        self.uncertain = uncertain
        self.retryable = retryable


def name():
    return "PhilSMS"


def key_configured():
    return bool(settings.PHILSMS_API_TOKEN)


def sender_name():
    return settings.PHILSMS_SENDER_ID or "Not configured"


def ready():
    return settings.SMS_ENABLED and key_configured() and bool(settings.PHILSMS_SENDER_ID)


def normalize_phone(value):
    raw = str(value or "").strip()
    if not re.fullmatch(r"\+?[0-9\s().-]+", raw):
        raise ValueError("A valid Philippine mobile number is required (09XXXXXXXXX or +639XXXXXXXXX).")
    number = re.sub(r"[\s().-]", "", raw).removeprefix("+")
    if re.fullmatch(r"09\d{9}", number):
        number = "63" + number[1:]
    elif re.fullmatch(r"9\d{9}", number):
        number = "63" + number
    if not re.fullmatch(r"639\d{9}", number):
        raise ValueError("A valid Philippine mobile number is required (09XXXXXXXXX or +639XXXXXXXXX).")
    return number


def _rejection_kind(result):
    """Classify provider errors without copying their untrusted text into our logs."""
    if not isinstance(result, dict):
        return None
    message = result.get("message")
    description = message.casefold() if isinstance(message, str) else ""
    if any(term in description for term in ("unauthenticated", "invalid api token", "invalid api key", "invalid token")):
        return "credentials"
    if any(term in description for term in ("rate limit", "too many requests", "throttl")):
        return "rate_limit"
    if any(term in description for term in ("insufficient", "balance", "credit", "fund")):
        return "balance"
    if any(term in description for term in ("sender", "sender_id")):
        return "sender"
    if any(term in description for term in ("recipient", "phone number", "mobile number")):
        return "recipient"

    errors = result.get("errors")
    if isinstance(errors, dict):
        if "recipient" in errors:
            return "recipient"
        if "sender_id" in errors:
            return "sender"
    return None


def _error_response_kind(error):
    try:
        body = error.read(8192)
        result = json.loads(body.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return None
    return _rejection_kind(result)


def _rejection_message(kind, *, code=None, sending=True, account=False):
    suffix = f" (HTTP {code})" if code is not None else ""
    if kind == "credentials":
        return "PhilSMS rejected the API token. Check PHILSMS_API_TOKEN and account access" + suffix + "."
    if kind == "rate_limit":
        return "PhilSMS rate limit reached" + suffix + "."
    if kind == "balance":
        return "PhilSMS rejected the SMS because the account balance or credits are insufficient" + suffix + "."
    if kind == "sender":
        return "PhilSMS rejected the sender ID. Check that PHILSMS_SENDER_ID is approved for this account" + suffix + "."
    if kind == "recipient":
        return "PhilSMS rejected the recipient phone number" + suffix + "."
    if account:
        return f"PhilSMS account request returned HTTP {code}." if code is not None else "PhilSMS could not return account information."
    if code in {400, 422}:
        return f"PhilSMS rejected the SMS request (HTTP {code}). Check recipient, sender ID and message."
    if code == 403:
        return "PhilSMS rejected the SMS request (HTTP 403). Check the account and sender restrictions."
    if code is not None:
        return f"PhilSMS returned HTTP {code}. Check its message log before resending."
    return (
        "PhilSMS rejected the request. Check recipient, sender ID, account balance and message."
        if sending else "PhilSMS could not return account or message information."
    )


def _request_json(path, payload=None, *, account=False):
    token = settings.PHILSMS_API_TOKEN
    if not token:
        raise SmsProviderError("PHILSMS_API_TOKEN is not configured.")
    if not re.fullmatch(r"[\x21-\x7e]+", token):
        raise SmsProviderError("PHILSMS_API_TOKEN has an invalid format.")

    sending = payload is not None
    req = Request(
        API_BASE + path,
        data=json.dumps(payload).encode("utf-8") if sending else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST" if sending else "GET",
    )
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read()
    except HTTPError as error:
        kind = _error_response_kind(error)
        if error.code == 401:
            kind = "credentials"
        elif error.code == 429:
            kind = "rate_limit"
        raise SmsProviderError(
            _rejection_message(kind, code=error.code, sending=sending, account=account),
            uncertain=sending and error.code >= 500,
            retryable=sending and (error.code == 429 or kind == "rate_limit"),
        ) from None
    except (URLError, TimeoutError, OSError):
        message = (
            "PhilSMS account information is temporarily unavailable."
            if account else
            "PhilSMS response could not be confirmed. Check its message log before resending."
        )
        raise SmsProviderError(message, uncertain=sending) from None

    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise SmsProviderError(
            "PhilSMS returned an invalid API response. Check its message log before resending.",
            uncertain=sending,
        ) from None
    if not isinstance(result, dict) or result.get("status") not in ("success", "error"):
        raise SmsProviderError(
            "PhilSMS returned an invalid API response. Check its message log before resending.",
            uncertain=sending,
        )
    if result["status"] == "error":
        kind = _rejection_kind(result)
        raise SmsProviderError(
            _rejection_message(kind, sending=sending, account=account),
            retryable=sending and kind == "rate_limit",
        )
    return result


def _message_data(result):
    data = result.get("data")
    if isinstance(data, list):
        data = data[0] if len(data) == 1 else None
    return data if isinstance(data, dict) else {}


def _message_uid(result):
    for item in (_message_data(result), result):
        for key in ("uid", "message_id", "reference_id", "id"):
            value = item.get(key)
            if value is not None and _UID_PATTERN.fullmatch(str(value)):
                return str(value)
    return None


def _delivery_status(result, *, require_known=False):
    status = str(_message_data(result).get("status", "")).strip().lower()
    if require_known and status not in _DELIVERY_STATES:
        raise SmsProviderError("PhilSMS returned an invalid message status.")
    return _DELIVERY_STATES.get(status, "submitted")


def send(phone, body):
    if not settings.SMS_ENABLED:
        raise SmsProviderError("SMS sending is disabled.")
    recipient = normalize_phone(phone)
    if not settings.PHILSMS_API_TOKEN:
        raise SmsProviderError("PHILSMS_API_TOKEN is not configured.")
    if not settings.PHILSMS_SENDER_ID:
        raise SmsProviderError("PHILSMS_SENDER_ID is not configured.")
    result = _request_json("sms/send", {
        "recipient": recipient,
        "sender_id": settings.PHILSMS_SENDER_ID,
        "type": "plain",
        "message": body,
    })
    uid = _message_uid(result)
    delivery_status = _delivery_status(result)
    if not uid and delivery_status not in {"failed", "refunded"}:
        raise SmsProviderError(
            "PhilSMS accepted the request without a usable message ID. Check its message log before resending.",
            uncertain=True,
        )
    return (ID_PREFIX + uid if uid else None), delivery_status


def status(message_id):
    if not isinstance(message_id, str) or not message_id.startswith(ID_PREFIX):
        raise SmsProviderError("The PhilSMS message ID is invalid.")
    uid = message_id[len(ID_PREFIX):]
    if not _UID_PATTERN.fullmatch(uid):
        raise SmsProviderError("The PhilSMS message ID is invalid.")
    result = _request_json("sms/" + uid)
    return message_id, _delivery_status(result, require_known=True)


def account():
    result = _request_json("balance", account=True)
    data = result.get("data")
    if isinstance(data, dict):
        value = next((data[key] for key in (
            "remaining_balance", "balance", "sms_unit", "sms_units", "remaining_sms_unit",
            "remaining_sms_units", "remaining_sms", "credit_balance",
        ) if key in data), None)
        status_value = str(data.get("status", "")).strip()
    else:
        value = data
        status_value = ""
    balance_text = re.sub(r"^(?:PHP|₱)\s*", "", str(value).strip(), flags=re.IGNORECASE)
    if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", balance_text):
        raise SmsProviderError("PhilSMS did not return a valid SMS balance.")
    try:
        credit_balance = Decimal(balance_text.replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        raise SmsProviderError("PhilSMS did not return a valid SMS balance.") from None
    if not credit_balance.is_finite() or credit_balance < 0:
        raise SmsProviderError("PhilSMS did not return a valid SMS balance.")
    return {"credit_balance": credit_balance, "status": status_value or "available"}
