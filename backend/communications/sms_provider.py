"""Semaphore transport. A timeout is ambiguous, so sends are never blindly retried."""

import json
import re
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


class SmsProviderError(Exception):
    def __init__(self, message, *, uncertain=False, retryable=False):
        super().__init__(message)
        self.uncertain = uncertain
        self.retryable = retryable


def ready():
    return settings.SMS_ENABLED and bool(settings.SEMAPHORE_API_KEY)


def normalize_phone(value):
    number = re.sub(r"[\s()+.-]", "", str(value or ""))
    if re.fullmatch(r"09\d{9}", number):
        number = "63" + number[1:]
    elif re.fullmatch(r"9\d{9}", number):
        number = "63" + number
    if not re.fullmatch(r"639\d{9}", number):
        raise ValueError("A valid Philippine mobile number is required (09XXXXXXXXX or +639XXXXXXXXX).")
    return number


def _request_json(path, values=None, *, account=False):
    data = {"apikey": settings.SEMAPHORE_API_KEY, **(values or {})}
    url = "https://api.semaphore.co/api/v4/" + path
    sending = values is not None
    if sending:
        req = Request(url, data=urlencode(data).encode(), method="POST")
    else:
        req = Request(url + "?" + urlencode(data))
    try:
        with urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        # Do not expose provider bodies or URLs: they may contain credentials.
        message = (
            f"Semaphore returned HTTP {error.code}. Check the API key and account status."
            if account
            else f"Semaphore returned HTTP {error.code}. Check your account, credits and sender name."
        )
        raise SmsProviderError(
            message,
            uncertain=sending and error.code >= 500,
            retryable=error.code == 429,
        ) from None
    except (URLError, TimeoutError, OSError, ValueError):
        message = (
            "Semaphore account information is temporarily unavailable."
            if account
            else "Semaphore response could not be confirmed. Check the provider message logs before resending."
        )
        raise SmsProviderError(message, uncertain=sending) from None
    return result


def request(path, values=None):
    result = _request_json(path, values)
    item = result[0] if isinstance(result, list) and result else result
    if not isinstance(item, dict) or not re.fullmatch(r"[0-9]+", str(item.get("message_id", ""))):
        raise SmsProviderError(
            "Semaphore did not return a message ID. Check the provider logs and configuration before resending.",
            uncertain=values is not None,
        )
    status = str(item.get("status", "")).lower()
    mapped = {"queued": "submitted", "pending": "pending", "sent": "sent", "failed": "failed", "refunded": "refunded"}
    return str(item["message_id"]), mapped.get(status, "submitted")


def send(phone, body):
    values = {"number": normalize_phone(phone), "message": body}
    if settings.SEMAPHORE_SENDER_NAME:
        values["sendername"] = settings.SEMAPHORE_SENDER_NAME
    return request("messages", values)


def status(message_id):
    return request("messages/" + str(int(message_id)))


def account():
    result = _request_json("account", account=True)
    item = result[0] if isinstance(result, list) and result else result
    if not isinstance(item, dict):
        raise SmsProviderError("Semaphore did not return valid account information.")
    try:
        credit_balance = Decimal(str(item["credit_balance"]))
    except (KeyError, InvalidOperation, TypeError, ValueError):
        raise SmsProviderError("Semaphore did not return a valid credit balance.") from None
    if not credit_balance.is_finite() or credit_balance < 0:
        raise SmsProviderError("Semaphore did not return a valid credit balance.")
    return {
        "credit_balance": credit_balance,
        "status": str(item.get("status", "")).strip(),
    }
