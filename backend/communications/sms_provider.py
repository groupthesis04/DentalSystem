"""SMS transports. Ambiguous sends are never blindly retried."""

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


def name():
    return {"semaphore": "Semaphore", "philsms": "PhilSMS"}.get(
        settings.SMS_PROVIDER, "Unknown SMS provider"
    )


def key_configured():
    if settings.SMS_PROVIDER == "semaphore":
        return bool(settings.SEMAPHORE_API_KEY)
    if settings.SMS_PROVIDER == "philsms":
        return bool(settings.PHILSMS_API_TOKEN)
    return False


def sender_name():
    if settings.SMS_PROVIDER == "semaphore":
        return settings.SEMAPHORE_SENDER_NAME or "Account default"
    if settings.SMS_PROVIDER == "philsms":
        return settings.PHILSMS_SENDER_ID or "Not configured"
    return "Not configured"


def _valid_philsms_sender():
    sender = settings.PHILSMS_SENDER_ID
    # Approved alphanumeric sender IDs may contain interior spaces (e.g. a
    # clinic name); PHILSMS limits those IDs to 11 characters.
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ]{0,10}|\+?[1-9][0-9]{5,14}", sender))


def ready():
    if not settings.SMS_ENABLED or not key_configured():
        return False
    if settings.SMS_PROVIDER == "philsms":
        return _valid_philsms_sender()
    return settings.SMS_PROVIDER == "semaphore"


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


def _semaphore_send(phone, body):
    values = {"number": normalize_phone(phone), "message": body}
    if settings.SEMAPHORE_SENDER_NAME:
        values["sendername"] = settings.SEMAPHORE_SENDER_NAME
    return request("messages", values)


def _semaphore_status(message_id):
    if not settings.SEMAPHORE_API_KEY:
        raise SmsProviderError("Semaphore status is unavailable without its API key.")
    if not re.fullmatch(r"[0-9]+", str(message_id)):
        raise SmsProviderError("The Semaphore message ID is invalid.")
    return request("messages/" + str(message_id))


def _semaphore_account():
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


_PHILSMS_API_ROOT = "https://app.philsms.com/api/v3/"
_PHILSMS_UID = re.compile(r"[A-Za-z0-9_-]{1,72}\Z")
_PHILSMS_STATUSES = {
    "queued": "submitted", "scheduled": "submitted", "submitted": "submitted",
    "pending": "pending", "processing": "pending", "sending": "pending",
    "sent": "sent", "delivered": "delivered",
    "failed": "failed", "rejected": "failed", "undelivered": "failed",
    "refunded": "refunded",
}


def _philsms_request_json(path, values=None):
    if not settings.PHILSMS_API_TOKEN:
        raise SmsProviderError("PhilSMS is not configured.")
    headers = {
        "Authorization": "Bearer " + settings.PHILSMS_API_TOKEN,
        "Accept": "application/json",
    }
    sending = values is not None
    if sending:
        headers["Content-Type"] = "application/json"
        req = Request(
            _PHILSMS_API_ROOT + path,
            data=json.dumps(values, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
    else:
        req = Request(_PHILSMS_API_ROOT + path, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        # The URL, response body and request headers may contain private data.
        raise SmsProviderError(
            f"PhilSMS returned HTTP {error.code}. Check the account and sender ID.",
            uncertain=sending and error.code >= 500,
            retryable=error.code == 429,
        ) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise SmsProviderError(
            "PhilSMS response could not be confirmed. Check its message logs before resending."
            if sending else "PhilSMS information is temporarily unavailable.",
            uncertain=sending,
        ) from None
    if not isinstance(result, dict):
        raise SmsProviderError(
            "PhilSMS returned an unrecognized response.", uncertain=sending
        )
    api_status = str(result.get("status", "")).lower()
    if api_status == "error":
        raise SmsProviderError("PhilSMS rejected the request. Check the account and sender ID.")
    if api_status != "success":
        raise SmsProviderError(
            "PhilSMS response could not be confirmed.", uncertain=sending
        )
    return result


def _philsms_record(result, *, sending):
    data = result.get("data")
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, dict):
        raise SmsProviderError(
            "PhilSMS did not return message details. Check its message logs before resending."
            if sending else "PhilSMS did not return message details.",
            uncertain=sending,
        )
    uid = data.get("uid")
    if not isinstance(uid, str) or not _PHILSMS_UID.fullmatch(uid):
        raise SmsProviderError(
            "PhilSMS did not return a valid message ID. Check its message logs before resending."
            if sending else "PhilSMS did not return a valid message ID.",
            uncertain=sending,
        )
    return uid, data


def _philsms_message_status(data, *, sending):
    raw = data.get("delivery_status", data.get("status"))
    state = _PHILSMS_STATUSES.get(str(raw or "").strip().lower())
    if state:
        return state
    if sending:
        # The success envelope confirms creation, not handset delivery.
        return "submitted"
    raise SmsProviderError("PhilSMS did not return a recognizable delivery status.")


def _philsms_send(phone, body):
    if not _valid_philsms_sender():
        raise SmsProviderError("PhilSMS sender ID is not configured or is invalid.")
    result = _philsms_request_json("sms/send", {
        "recipient": normalize_phone(phone),
        "sender_id": settings.PHILSMS_SENDER_ID,
        "type": "plain" if body.isascii() else "unicode",
        "message": body,
    })
    uid, data = _philsms_record(result, sending=True)
    return "philsms:" + uid, _philsms_message_status(data, sending=True)


def _philsms_status(message_id):
    uid = str(message_id).removeprefix("philsms:")
    if not _PHILSMS_UID.fullmatch(uid):
        raise SmsProviderError("The PhilSMS message ID is invalid.")
    result = _philsms_request_json("sms/" + uid)
    returned_uid, data = _philsms_record(result, sending=False)
    if returned_uid != uid:
        raise SmsProviderError("PhilSMS returned details for a different message.")
    return "philsms:" + uid, _philsms_message_status(data, sending=False)


def _philsms_account():
    result = _philsms_request_json("balance")
    data = result.get("data")
    # The public API documents the endpoint but not its exact response fields.
    # Only use an unambiguous numeric balance; otherwise show unavailable.
    if not isinstance(data, dict):
        raise SmsProviderError("PhilSMS balance format is not recognized.")
    values = [data[key] for key in ("remaining_sms_units", "credit_balance", "balance") if key in data]
    if len(values) != 1:
        raise SmsProviderError("PhilSMS balance format is not recognized.")
    try:
        credit_balance = Decimal(str(values[0]))
    except (InvalidOperation, TypeError, ValueError):
        raise SmsProviderError("PhilSMS balance format is not recognized.") from None
    if not credit_balance.is_finite() or credit_balance < 0:
        raise SmsProviderError("PhilSMS balance format is not recognized.")
    return {"credit_balance": credit_balance, "status": "available"}


def send(phone, body):
    if settings.SMS_PROVIDER == "philsms":
        return _philsms_send(phone, body)
    if settings.SMS_PROVIDER == "semaphore":
        return _semaphore_send(phone, body)
    raise SmsProviderError("The configured SMS provider is not supported.")


def status(message_id):
    if str(message_id).startswith("philsms:"):
        return _philsms_status(message_id)
    # Semaphore's historical IDs are bare decimal strings. Keep polling them
    # through Semaphore after a temporary provider switch.
    return _semaphore_status(message_id)


def account():
    if settings.SMS_PROVIDER == "philsms":
        return _philsms_account()
    if settings.SMS_PROVIDER == "semaphore":
        return _semaphore_account()
    raise SmsProviderError("The configured SMS provider is not supported.")
