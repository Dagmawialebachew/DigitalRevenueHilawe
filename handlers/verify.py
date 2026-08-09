# verify.py — Veritas V2
# Goal: robust Ethiopian payment receipt verification without breaking existing imports.
#
# Public compatibility kept:
#   - router
#   - PaymentStates
#   - get_verifier_menu()
#   - extract_local_data(img_stream)
#   - verify_external(reference, provider, max_attempts=...)
#   - is_hilawe_receiver(raw, bank_data)
#   - format_audit_report(...)
#
# Architecture:
# 1. OCR.space extracts provider/reference/secondary clues.
# 2. Veritas /verify is the primary authority.
# 3. Dedicated provider endpoint is used only as a controlled fallback.
# 4. Provider/API outages are "manual review", NOT fraud.
# 5. Veritas provider responses are normalized to one internal shape.
# 6. Existing callers can still read success/data/amount/receiver/date.

from __future__ import annotations

import asyncio
import html
import io
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from PIL import Image, ImageEnhance
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings


# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

VERIFY_API_KEY = settings.VERIFY_API_KEY
VERIFY_BASE_URL = getattr(
    settings,
    "VERIFY_API_BASE_URL",
    "https://verifyapi.leulzenebe.pro",
).rstrip("/")

VERIFY_URL = f"{VERIFY_BASE_URL}/verify"

DEDICATED_ENDPOINTS = {
    "CBE": f"{VERIFY_BASE_URL}/verify-cbe",
    "Telebirr": f"{VERIFY_BASE_URL}/verify-telebirr",
    "Dashen": f"{VERIFY_BASE_URL}/verify-dashen",
    "Abyssinia": f"{VERIFY_BASE_URL}/verify-abyssinia",
    "CBE Birr": f"{VERIFY_BASE_URL}/verify-cbebirr",
    "M-Pesa": f"{VERIFY_BASE_URL}/verify-mpesa",
}

# Existing CBE receiver account suffix.
CBE_SUFFIX = str(getattr(settings, "CBE_SUFFIX", "99533641")).strip()

# Bank of Abyssinia requires a 5-digit suffix.
# Prefer an env/config value. Screenshot fallback retained only for compatibility.
ABYSSINIA_SUFFIX = str(
    getattr(settings, "ABYSSINIA_SUFFIX", "99555")
).strip()[-5:]

# Optional, only needed for CBE Birr verification.
CBEBIRR_PHONE_NUMBER = str(
    getattr(settings, "CBEBIRR_PHONE_NUMBER", "")
).strip()

OCR_SPACE_API_KEY = getattr(
    settings,
    "OCR_SPACE_API_KEY",
    "helloworld",
)
OCR_SPACE_URL = "https://api.ocr.space/parse/image"

router = Router(name="verify")


# ─────────────────────────────────────────────
# PERSISTENT HTTP CLIENTS
# ─────────────────────────────────────────────

_verify_client: httpx.AsyncClient | None = None
_ocr_client: httpx.AsyncClient | None = None


def get_verify_client() -> httpx.AsyncClient:
    """Persistent Veritas client."""
    global _verify_client

    if _verify_client is None or _verify_client.is_closed:
        _verify_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=4.0,
                read=12.0,
                write=5.0,
                pool=2.0,
            ),
            limits=httpx.Limits(
                max_connections=50,
                max_keepalive_connections=20,
            ),
            headers={
                "x-api-key": VERIFY_API_KEY,
                "Content-Type": "application/json",
            },
            follow_redirects=False,
        )

    return _verify_client


def get_ocr_client() -> httpx.AsyncClient:
    """Persistent OCR.space client."""
    global _ocr_client

    if _ocr_client is None or _ocr_client.is_closed:
        _ocr_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=5.0,
                read=25.0,
                write=10.0,
                pool=5.0,
            ),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
        )

    return _ocr_client


# ─────────────────────────────────────────────
# FSM STATES
# ─────────────────────────────────────────────

class PaymentStates(StatesGroup):
    waiting_for_screenshot = State()


# ─────────────────────────────────────────────
# IMAGE PREPROCESSING
# ─────────────────────────────────────────────

def _preprocess_for_ocr(img_stream: io.BytesIO) -> bytes:
    """
    Prepare screenshots for OCR.space.

    - Downscale very large images.
    - Upscale small screenshots.
    - Mild contrast enhancement.
    - High quality JPEG output.
    """
    img_stream.seek(0)
    img = Image.open(img_stream).convert("RGB")
    w, h = img.size

    max_width = 1600
    min_width = 700

    if w > max_width:
        ratio = max_width / w
        img = img.resize(
            (int(w * ratio), int(h * ratio)),
            Image.Resampling.LANCZOS,
        )
    elif w < min_width:
        ratio = min_width / w
        img = img.resize(
            (int(w * ratio), int(h * ratio)),
            Image.Resampling.BICUBIC,
        )

    img = ImageEnhance.Contrast(img).enhance(1.25)

    out = io.BytesIO()
    img.save(
        out,
        format="JPEG",
        quality=94,
        optimize=True,
    )
    return out.getvalue()


# ─────────────────────────────────────────────
# OCR.SPACE
# ─────────────────────────────────────────────

async def _ocr_space(image_bytes: bytes) -> str:
    """Send image to OCR.space and return extracted text."""
    payload = {
        "apikey": OCR_SPACE_API_KEY,
        "language": "eng",
        "isOverlayRequired": "false",
        "OCREngine": "2",
        "scale": "false",
    }

    files = {
        "file": (
            "receipt.jpg",
            image_bytes,
            "image/jpeg",
        )
    }

    try:
        client = get_ocr_client()
        resp = await client.post(
            OCR_SPACE_URL,
            data=payload,
            files=files,
        )

        if resp.status_code != 200:
            logger.warning(
                "OCR.space HTTP %s: %s",
                resp.status_code,
                resp.text[:500],
            )
            return ""

        data = resp.json()

        if data.get("IsErroredOnProcessing", False):
            logger.warning(
                "OCR.space processing error: %s",
                data.get("ErrorMessage"),
            )
            return ""

        parsed_results = data.get("ParsedResults") or []
        if not parsed_results:
            logger.warning("OCR.space returned no ParsedResults.")
            return ""

        return str(
            parsed_results[0].get("ParsedText") or ""
        )

    except httpx.ReadTimeout:
        logger.warning("OCR.space read timeout.")
        return ""

    except Exception:
        logger.exception("OCR.space request failed.")
        return ""


# ─────────────────────────────────────────────
# OCR TEXT HELPERS
# ─────────────────────────────────────────────

def _clean_for_matching(raw: str) -> str:
    return re.sub(
        r"[^A-Z0-9\n\s:\-_/().]",
        " ",
        (raw or "").upper(),
    )


def _detect_provider(up: str) -> str:
    """
    Detect provider conservatively.

    Detection order matters:
    Abyssinia must be checked before generic D-prefix Telebirr logic.
    """

    if any(
        key in up
        for key in (
            "BANK OF ABYSSINIA",
            "ABYSSINIA",
            "BOA",
        )
    ):
        return "Abyssinia"

    if any(
        key in up
        for key in (
            "COMMERCIAL BANK OF ETHIOPIA",
            "COMMERCIAL BANK",
            "CBE MOBILE",
            "CBE ",
            "CBE\n",
            "BRECIEPT",
        )
    ):
        return "CBE"

    # CBE SMS references commonly begin with FT2...
    if re.search(r"\bFT[A-Z0-9]{8,14}\b", up):
        return "CBE"

    if any(
        key in up
        for key in (
            "DASHEN",
            "AMOLE",
        )
    ):
        return "Dashen"

    if any(
        key in up
        for key in (
            "TELEBIRR",
            "ETHIO TELECOM",
            "TELE BIRR",
        )
    ):
        return "Telebirr"

    if any(
        key in up
        for key in (
            "CBE BIRR",
            "CBEBIRR",
        )
    ):
        return "CBE Birr"

    if any(
        key in up
        for key in (
            "M-PESA",
            "MPESA",
            "M PESA",
        )
    ):
        return "M-Pesa"

    if "AWASH" in up:
        return "Awash"

    return "Unknown"


# ─────────────────────────────────────────────
# REFERENCE EXTRACTION
# ─────────────────────────────────────────────

def _extract_cbe(up: str) -> str | None:
    patterns = (
        r"\b(FT[A-Z0-9]{8,14})\b",
        r"F\s*T\s*([A-Z0-9]{8,14})",
        r"(?:TRANSACTION\s*ID|TRANSACTION\s*REFERENCE|REFERENCE\s*ID)"
        r"[:\s#-]+(FT[A-Z0-9]{8,14})",
    )

    for pattern in patterns:
        match = re.search(pattern, up)
        if not match:
            continue

        value = match.group(1)
        if pattern.startswith("F\\s"):
            value = "FT" + value

        return value.replace(" ", "").strip().upper()

    return None


def _extract_abyssinia(up: str) -> str | None:
    patterns = (
        r"(?:TRANSACTION\s*NUMBER|TRANSACTION\s*NO|TRANSACTION\s*ID)"
        r"[:\s#-]+([A-Z0-9]{8,18})",
        r"\b(DH[A-Z0-9]{8,16})\b",
    )

    for pattern in patterns:
        match = re.search(pattern, up)
        if match:
            return match.group(1).strip().upper()

    return None


def _extract_dashen(up: str) -> str | None:
    patterns = (
        r"(?:TRANSACTION\s*(?:ID|NO|NUMBER)|REFERENCE\s*(?:ID|NO|NUMBER))"
        r"[:\s#-]+([A-Z0-9]{10,20})",
        r"\b([0-9]{14,20})\b",
    )

    for pattern in patterns:
        match = re.search(pattern, up)
        if match:
            return match.group(1).strip().upper()

    return None


def _extract_telebirr(up: str, raw: str) -> str | None:
    # Prefer Telebirr-specific labels first.
    labels = (
        "TRANSACTION NUMBER",
        "TRANSACTION NO",
        "TRANSACTION ID",
        "INVOICE NO",
        "INVOICE NUMBER",
        "REF NO",
        "REFERENCE NO",
    )

    for label in labels:
        match = re.search(
            rf"{label}[:\s#-]+([A-Z0-9]{{8,16}})",
            up,
        )
        if match:
            return match.group(1).strip().upper()

    # Amharic label.
    match = re.search(
        r"የግብይት\s*ቁጥር[:\s]+([A-Z0-9a-z]{8,16})",
        raw or "",
        re.UNICODE,
    )
    if match:
        return match.group(1).strip().upper()

    # Telebirr D-prefix fallback.
    match = re.search(r"\b(D[A-Z0-9]{9})\b", up)
    if match:
        return match.group(1).strip().upper()

    return None


def _extract_generic_reference(up: str) -> str | None:
    patterns = (
        r"(?:TRANSACTION\s*(?:ID|NO|NUMBER)|REFERENCE\s*(?:ID|NO|NUMBER)|REF\s*NO)"
        r"[:\s#-]+([A-Z0-9]{8,20})",
        r"\b(FT[A-Z0-9]{8,14})\b",
        r"\b(DH[A-Z0-9]{8,16})\b",
    )

    for pattern in patterns:
        match = re.search(pattern, up)
        if match:
            return match.group(1).strip().upper()

    return None


def _extract_account_suffix(
    raw: str,
    provider: str,
) -> str | None:
    """
    Extract secondary account suffix when visible.

    Abyssinia uses 5 digits.
    CBE uses configured receiver suffix for compatibility.
    """
    if provider == "Abyssinia":
        match = re.search(
            r"(?:BANK\s*ACCOUNT\s*NUMBER|ACCOUNT\s*NUMBER|ACCOUNT\s*NO)"
            r"[:\s#-]+([0-9]{5,20})",
            raw.upper(),
        )
        if match:
            return match.group(1)[-5:]

        return ABYSSINIA_SUFFIX or None

    if provider == "CBE":
        return CBE_SUFFIX or None

    return None


def _extract_phone_number(raw: str) -> str | None:
    compact = re.sub(r"[\s\-()]", "", raw or "")

    match = re.search(r"\b(2519\d{8})\b", compact)
    if match:
        return match.group(1)

    match = re.search(r"\b(09\d{8})\b", compact)
    if match:
        return "251" + match.group(1)[1:]

    return CBEBIRR_PHONE_NUMBER or None


def _extract_amount_fallback(raw: str) -> str | None:
    """
    OCR-only fallback for display.

    Prefer amounts explicitly tied to ETB/Birr rather than the largest number,
    which could be an account number.
    """
    text = raw or ""

    patterns = (
        r"\bETB\s*([0-9][0-9,]*(?:\.\d{1,2})?)",
        r"\b([0-9][0-9,]*(?:\.\d{1,2})?)\s*ETB\b",
        r"\bAMOUNT(?:\s+DEBITED)?[:\s]+(?:ETB\s*)?([0-9][0-9,]*(?:\.\d{1,2})?)",
        r"\bTOTAL\s+AMOUNT\s+DEBITED[:\s]+(?:ETB\s*)?([0-9][0-9,]*(?:\.\d{1,2})?)",
    )

    candidates: list[str] = []

    for pattern in patterns:
        candidates.extend(
            re.findall(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
        )

    if not candidates:
        return None

    def to_float(value: str) -> float:
        try:
            return float(value.replace(",", ""))
        except Exception:
            return -1.0

    # The largest ETB-tagged amount is usually the total debit.
    best = max(candidates, key=to_float)
    return best


# ─────────────────────────────────────────────
# PUBLIC OCR HOOK
# ─────────────────────────────────────────────

async def extract_local_data(
    img_stream: io.BytesIO,
) -> dict:
    """
    preprocess -> OCR.space -> provider/ref/secondary extraction.

    Original keys preserved:
      provider
      ref
      amount_fallback
      raw_text

    New non-breaking keys:
      suffix
      phone_number
    """
    loop = asyncio.get_running_loop()

    image_bytes = await loop.run_in_executor(
        None,
        _preprocess_for_ocr,
        img_stream,
    )

    raw = await _ocr_space(image_bytes)
    up = _clean_for_matching(raw)

    provider = _detect_provider(up)
    ref: str | None = None

    if provider == "CBE":
        ref = _extract_cbe(up)

    elif provider == "Abyssinia":
        ref = _extract_abyssinia(up)

    elif provider == "Dashen":
        ref = _extract_dashen(up)

    elif provider == "Telebirr":
        ref = _extract_telebirr(up, raw)

    elif provider in ("CBE Birr", "M-Pesa"):
        ref = _extract_generic_reference(up)

    else:
        # Unknown receipts: extract a reference, but DO NOT automatically
        # misclassify generic D-prefix references as Telebirr.
        ref = _extract_generic_reference(up)

        if ref and ref.startswith("FT"):
            provider = "CBE"

    suffix = _extract_account_suffix(raw, provider)
    phone_number = _extract_phone_number(raw)

    return {
        "provider": provider,
        "ref": ref,
        "amount_fallback": _extract_amount_fallback(raw),
        "raw_text": raw,
        "suffix": suffix,
        "phone_number": phone_number,
    }


# ─────────────────────────────────────────────
# VERITAS RESPONSE NORMALIZATION
# ─────────────────────────────────────────────

def _walk_objects(value: Any):
    """Yield nested dictionaries recursively."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_objects(child)

    elif isinstance(value, list):
        for child in value:
            yield from _walk_objects(child)


def _deep_find(
    payload: Any,
    keys: tuple[str, ...],
) -> Any:
    wanted = {key.lower() for key in keys}

    for obj in _walk_objects(payload):
        for key, value in obj.items():
            if str(key).lower() in wanted and value not in (
                None,
                "",
                [],
                {},
            ):
                return value

    return None


def _to_amount(value: Any) -> float:
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value)
    match = re.search(
        r"-?[0-9][0-9,]*(?:\.\d+)?",
        text,
    )

    if not match:
        return 0.0

    try:
        return float(
            match.group(0).replace(",", "")
        )
    except Exception:
        return 0.0


def _raw_success(raw: dict) -> bool:
    value = raw.get("success")

    if value is True:
        return True

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "success",
            "verified",
            "valid",
        }

    status = _deep_find(
        raw,
        (
            "status",
            "verificationStatus",
            "verification_status",
        ),
    )

    if isinstance(status, str):
        return status.strip().lower() in {
            "success",
            "verified",
            "valid",
            "completed",
        }

    return False


def _extract_error_message(
    raw: Any,
    fallback: str = "",
) -> str:
    if isinstance(raw, dict):
        value = _deep_find(
            raw,
            (
                "error",
                "message",
                "detail",
                "reason",
                "errorMessage",
                "error_message",
            ),
        )
        if value:
            return str(value)

    return fallback


def _normalize_veritas_response(
    raw: dict,
    provider: str,
    reference: str,
) -> dict:
    """
    Normalize provider-specific Veritas response envelopes.

    Backward compatibility:
    - success stays available.
    - normalized fields exist top-level.
    - same normalized fields are mirrored under data.
    - original API body is retained as raw_response.
    """

    success = _raw_success(raw)

    payer = _deep_find(
        raw,
        (
            "payer",
            "payerName",
            "payer_name",
            "sender",
            "senderName",
            "sender_name",
            "debitedPartyName",
            "debited_party_name",
            "fromAccountName",
            "from_account_name",
            "customerName",
        ),
    )

    receiver = _deep_find(
        raw,
        (
            "receiver",
            "receiverName",
            "receiver_name",
            "creditedPartyName",
            "credited_party_name",
            "beneficiary",
            "beneficiaryName",
            "beneficiary_name",
            "toAccountName",
            "to_account_name",
            "merchantName",
            "merchant_name",
        ),
    )

    amount = _deep_find(
        raw,
        (
            "amount",
            "transactionAmount",
            "transaction_amount",
            "paidAmount",
            "paid_amount",
            "totalAmount",
            "total_amount",
        ),
    )

    date = _deep_find(
        raw,
        (
            "date",
            "transactionDate",
            "transaction_date",
            "transactionTime",
            "transaction_time",
            "timestamp",
            "createdAt",
            "created_at",
        ),
    )

    api_reference = _deep_find(
        raw,
        (
            "reference",
            "referenceId",
            "reference_id",
            "transactionId",
            "transaction_id",
            "transactionNumber",
            "transaction_number",
            "receiptNumber",
            "receipt_number",
        ),
    )

    normalized = {
        "success": success,
        "verification_state": (
            "verified" if success else "rejected"
        ),
        "provider": provider,
        "reference": str(
            api_reference or reference
        ).strip(),
        "payer": str(payer or "Unknown").strip(),
        "receiver": str(receiver or "N/A").strip(),
        "amount": _to_amount(amount),
        "date": str(date).strip() if date else None,
        "error": (
            None
            if success
            else _extract_error_message(raw)
        ),
        "raw_response": raw,
    }

    # Old code may expect bank_data["data"]["amount"].
    normalized["data"] = {
        "provider": normalized["provider"],
        "reference": normalized["reference"],
        "payer": normalized["payer"],
        "receiver": normalized["receiver"],
        "amount": normalized["amount"],
        "date": normalized["date"],
    }

    return normalized


# ─────────────────────────────────────────────
# ERROR CLASSIFICATION
# ─────────────────────────────────────────────

_TEMPORARY_ERROR_MARKERS = (
    "timeout",
    "timed out",
    "temporarily",
    "temporary",
    "unavailable",
    "upstream",
    "provider error",
    "provider failure",
    "service unavailable",
    "connection",
    "network",
    "try again",
    "failed to fetch",
    "gateway",
    "rate limit",
    "too many requests",
)

_CONCLUSIVE_REJECT_MARKERS = (
    "not found",
    "invalid reference",
    "invalid transaction",
    "transaction does not exist",
    "reference does not exist",
    "receipt does not exist",
    "no transaction",
    "unknown reference",
)


def _looks_temporary(message: str) -> bool:
    lower = (message or "").lower()
    return any(
        marker in lower
        for marker in _TEMPORARY_ERROR_MARKERS
    )


def _looks_conclusive_reject(message: str) -> bool:
    lower = (message or "").lower()
    return any(
        marker in lower
        for marker in _CONCLUSIVE_REJECT_MARKERS
    )


def _manual_review_response(
    *,
    provider: str,
    reference: str,
    error: str,
    http_status: int | None = None,
    raw_response: Any = None,
) -> dict:
    result = {
        "success": False,
        "verification_state": "unavailable",
        "provider": provider,
        "reference": reference,
        "payer": "Unknown",
        "receiver": "N/A",
        "amount": 0.0,
        "date": None,
        "error": error,
        "http_status": http_status,
        "raw_response": raw_response,
    }

    result["data"] = {
        "provider": provider,
        "reference": reference,
        "payer": "Unknown",
        "receiver": "N/A",
        "amount": 0.0,
        "date": None,
    }

    return result


# ─────────────────────────────────────────────
# VERITAS PAYLOADS
# ─────────────────────────────────────────────

def _build_universal_payload(
    reference: str,
    provider: str,
) -> dict:
    payload: dict[str, str] = {
        "reference": reference.strip(),
    }

    if provider == "CBE" and CBE_SUFFIX:
        payload["suffix"] = CBE_SUFFIX

    elif provider == "Abyssinia" and ABYSSINIA_SUFFIX:
        payload["suffix"] = ABYSSINIA_SUFFIX

    elif (
        provider == "CBE Birr"
        and CBEBIRR_PHONE_NUMBER
    ):
        payload["phoneNumber"] = CBEBIRR_PHONE_NUMBER

    return payload


def _build_dedicated_payload(
    reference: str,
    provider: str,
) -> dict | None:
    reference = reference.strip()

    if provider == "CBE":
        payload = {"reference": reference}
        if CBE_SUFFIX:
            payload["accountSuffix"] = CBE_SUFFIX
        return payload

    if provider == "Telebirr":
        return {"reference": reference}

    if provider == "Dashen":
        return {"reference": reference}

    if provider == "Abyssinia":
        if not ABYSSINIA_SUFFIX:
            return None
        return {
            "reference": reference,
            "suffix": ABYSSINIA_SUFFIX,
        }

    if provider == "CBE Birr":
        if not CBEBIRR_PHONE_NUMBER:
            return None
        return {
            "receiptNumber": reference,
            "phoneNumber": CBEBIRR_PHONE_NUMBER,
        }

    if provider == "M-Pesa":
        return {"reference": reference}

    return None


# ─────────────────────────────────────────────
# VERITAS HTTP CALL
# ─────────────────────────────────────────────

async def _call_veritas(
    url: str,
    payload: dict,
) -> tuple[int | None, dict | None, str | None]:
    """
    Return (status_code, json_body, transport_error).
    """
    client = get_verify_client()

    try:
        resp = await client.post(
            url,
            json=payload,
        )

    except httpx.ReadTimeout:
        return None, None, "Veritas request timed out."

    except httpx.ConnectTimeout:
        return None, None, "Could not connect to Veritas."

    except httpx.NetworkError as exc:
        return None, None, f"Network error: {exc}"

    except Exception as exc:
        logger.exception(
            "Unexpected Veritas request error."
        )
        return (
            None,
            None,
            f"{type(exc).__name__}: {exc}",
        )

    try:
        body = resp.json()
    except Exception:
        body = None

    logger.info(
        "Veritas response status=%s body=%s",
        resp.status_code,
        (
            body
            if body is not None
            else resp.text[:1000]
        ),
    )

    return resp.status_code, body, None


# ─────────────────────────────────────────────
# PUBLIC VERIFICATION HOOK
# ─────────────────────────────────────────────

async def verify_external(
    reference: str,
    provider: str,
    max_attempts: int = 2,
) -> dict:
    """
    Verify one payment reference against Veritas.

    Credit-safe behavior:
    - Universal /verify first.
    - Retry only transport/5xx/429 style failures.
    - Never retry 401/402/403.
    - Dedicated route is a single controlled fallback.
    - API/provider outages return verification_state='unavailable'.
    """

    reference = str(reference or "").strip().upper()
    provider = str(provider or "Unknown").strip()

    if not reference:
        return _manual_review_response(
            provider=provider,
            reference="",
            error="No payment reference was extracted.",
        )

    universal_payload = _build_universal_payload(
        reference,
        provider,
    )

    attempts = max(
        1,
        min(int(max_attempts or 1), 2),
    )

    last_status: int | None = None
    last_body: dict | None = None
    last_error = ""

    # ── Universal first ──────────────────────
    for attempt in range(1, attempts + 1):
        logger.info(
            "Veritas universal attempt %s/%s "
            "provider=%s ref=%s",
            attempt,
            attempts,
            provider,
            reference,
        )

        status, body, transport_error = await _call_veritas(
            VERIFY_URL,
            universal_payload,
        )

        last_status = status
        last_body = body

        if transport_error:
            last_error = transport_error

            if attempt < attempts:
                await asyncio.sleep(0.8)
                continue

            return _manual_review_response(
                provider=provider,
                reference=reference,
                error=transport_error,
                raw_response=body,
            )

        # Auth / billing / permission failures are NEVER receipt fraud.
        if status in (401, 402, 403):
            error = _extract_error_message(
                body,
                fallback=(
                    f"Veritas rejected the API request "
                    f"(HTTP {status})."
                ),
            )

            logger.error(
                "Veritas configuration/plan failure "
                "HTTP %s: %s",
                status,
                error,
            )

            return _manual_review_response(
                provider=provider,
                reference=reference,
                error=error,
                http_status=status,
                raw_response=body,
            )

        # Retry only rate-limit and server failures.
        if status == 429 or (
            status is not None
            and 500 <= status <= 599
        ):
            error = _extract_error_message(
                body,
                fallback=f"Veritas HTTP {status}",
            )
            last_error = error

            if attempt < attempts:
                await asyncio.sleep(0.8)
                continue

            return _manual_review_response(
                provider=provider,
                reference=reference,
                error=error,
                http_status=status,
                raw_response=body,
            )

        if status != 200:
            error = _extract_error_message(
                body,
                fallback=(
                    f"Unexpected Veritas HTTP {status}."
                ),
            )

            return _manual_review_response(
                provider=provider,
                reference=reference,
                error=error,
                http_status=status,
                raw_response=body,
            )

        if not isinstance(body, dict):
            return _manual_review_response(
                provider=provider,
                reference=reference,
                error=(
                    "Veritas returned an invalid JSON body."
                ),
                http_status=status,
                raw_response=body,
            )

        normalized = _normalize_veritas_response(
            body,
            provider,
            reference,
        )

        if normalized["success"]:
            logger.info(
                "Veritas verified ref=%s provider=%s",
                reference,
                provider,
            )
            return normalized

        error = normalized.get("error") or ""
        last_error = error

        # Provider can fail with HTTP 200. Treat temporary provider
        # failures as unavailable/manual review.
        if _looks_temporary(error):
            normalized["verification_state"] = "unavailable"
            return normalized

        # Explicit not-found / invalid-reference can be considered
        # a conclusive rejection.
        if _looks_conclusive_reject(error):
            normalized["verification_state"] = "rejected"
            return normalized

        # Otherwise: do not spam retries. Try one dedicated route
        # when provider is known and supported.
        break

    # ── Single dedicated fallback ─────────────
    dedicated_url = DEDICATED_ENDPOINTS.get(provider)
    dedicated_payload = _build_dedicated_payload(
        reference,
        provider,
    )

    if dedicated_url and dedicated_payload:
        logger.info(
            "Veritas dedicated fallback "
            "provider=%s ref=%s url=%s",
            provider,
            reference,
            dedicated_url,
        )

        status, body, transport_error = await _call_veritas(
            dedicated_url,
            dedicated_payload,
        )

        if transport_error:
            return _manual_review_response(
                provider=provider,
                reference=reference,
                error=transport_error,
                raw_response=body,
            )

        if status in (401, 402, 403):
            return _manual_review_response(
                provider=provider,
                reference=reference,
                error=_extract_error_message(
                    body,
                    fallback=(
                        f"Veritas API access failure "
                        f"(HTTP {status})."
                    ),
                ),
                http_status=status,
                raw_response=body,
            )

        if status == 429 or (
            status is not None
            and 500 <= status <= 599
        ):
            return _manual_review_response(
                provider=provider,
                reference=reference,
                error=_extract_error_message(
                    body,
                    fallback=(
                        f"Veritas provider unavailable "
                        f"(HTTP {status})."
                    ),
                ),
                http_status=status,
                raw_response=body,
            )

        if status == 200 and isinstance(body, dict):
            normalized = _normalize_veritas_response(
                body,
                provider,
                reference,
            )

            error = normalized.get("error") or ""

            if normalized["success"]:
                return normalized

            if _looks_conclusive_reject(error):
                normalized["verification_state"] = "rejected"
            else:
                # Unknown provider-side failure is safer as manual review.
                normalized["verification_state"] = "unavailable"

            return normalized

        return _manual_review_response(
            provider=provider,
            reference=reference,
            error=_extract_error_message(
                body,
                fallback=(
                    f"Dedicated provider verification "
                    f"failed with HTTP {status}."
                ),
            ),
            http_status=status,
            raw_response=body,
        )

    # Unknown provider / no dedicated payload.
    return _manual_review_response(
        provider=provider,
        reference=reference,
        error=(
            last_error
            or "Verification was inconclusive. Manual review required."
        ),
        http_status=last_status,
        raw_response=last_body,
    )


# ─────────────────────────────────────────────
# RECEIVER VALIDATION
# ─────────────────────────────────────────────

def _normalize_name(value: str) -> str:
    return re.sub(
        r"[^A-Z]",
        "",
        (value or "").upper(),
    )


def is_hilawe_receiver(
    raw: str,
    bank_data: dict,
) -> bool:
    """
    API receiver is authoritative when present.
    OCR is a fallback when Veritas does not expose receiver name.
    """

    data = bank_data.get("data") or {}

    api_name = str(
        bank_data.get("receiver")
        or data.get("receiver")
        or data.get("creditedPartyName")
        or data.get("credited_party_name")
        or ""
    )

    normalized_api = _normalize_name(api_name)

    if normalized_api:
        return "HILAWE" in normalized_api

    # OCR fallback only.
    normalized_ocr = _normalize_name(raw or "")
    return "HILAWE" in normalized_ocr


# ─────────────────────────────────────────────
# TIME FORMATTER
# ─────────────────────────────────────────────

def _format_time_ago(
    date_str: str | None,
) -> str:
    if not date_str:
        return "(Time unknown)"

    try:
        cleaned = str(date_str).strip()

        # Common ISO representation.
        pay_dt = datetime.fromisoformat(
            cleaned.replace("Z", "+00:00")
        )

        if pay_dt.tzinfo is None:
            pay_dt = pay_dt.replace(
                tzinfo=timezone.utc
            )

        total_seconds = int(
            (
                datetime.now(timezone.utc)
                - pay_dt.astimezone(timezone.utc)
            ).total_seconds()
        )

        if total_seconds <= 0:
            return "(just now)"

        days, rem = divmod(
            total_seconds,
            86400,
        )
        hours, rem = divmod(
            rem,
            3600,
        )
        minutes, _ = divmod(
            rem,
            60,
        )

        if days > 0:
            return f"({days}d {hours}h ago)"

        if hours > 0:
            return f"({hours}h {minutes}m ago)"

        return f"({minutes}m ago)"

    except Exception:
        return "(Time unknown)"


# ─────────────────────────────────────────────
# REPORT FORMATTER
# ─────────────────────────────────────────────

def format_audit_report(
    local: dict,
    bank_data: dict,
    elapsed: float,
    is_real: bool,
    is_hilawe: bool,
) -> str:
    payer = (
        bank_data.get("payer")
        or (bank_data.get("data") or {}).get("payer")
        or "Unknown"
    )

    receiver = (
        bank_data.get("receiver")
        or (bank_data.get("data") or {}).get("receiver")
        or "N/A"
    )

    amount = _to_amount(
        bank_data.get("amount")
        or (bank_data.get("data") or {}).get("amount")
    )

    date = (
        bank_data.get("date")
        or (bank_data.get("data") or {}).get("date")
    )

    time_display = _format_time_ago(date)
    state = bank_data.get(
        "verification_state",
        "verified" if is_real else "rejected",
    )

    provider = html.escape(
        str(local.get("provider") or "Unknown")
    )
    reference = html.escape(
        str(local.get("ref") or "N/A")
    )
    payer_safe = html.escape(str(payer))
    receiver_safe = html.escape(str(receiver))

    if is_real and is_hilawe:
        return (
            "✅ <b>TRANSACTION VERIFIED</b>\n"
            "────────────────────\n"
            f"👤 <b>Payer:</b> <code>{payer_safe}</code>\n"
            f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
            f"🏦 <b>Bank:</b> {provider} {time_display}\n"
            f"🆔 <b>Ref ID:</b> <code>{reference}</code>\n"
            f"🎯 <b>Receiver:</b> {receiver_safe}\n\n"
            "🟢 <b>Outcome:</b> Approved.\n"
            f"⏱️ <b>Audit duration:</b> {elapsed:.2f}s"
        )

    if state == "unavailable":
        error = html.escape(
            str(
                bank_data.get("error")
                or "Provider verification unavailable."
            )
        )

        return (
            "⚠️ <b>VERIFICATION INCONCLUSIVE</b>\n"
            "────────────────────\n"
            f"🏦 <b>Provider:</b> {provider}\n"
            f"🆔 <b>Ref ID:</b> <code>{reference}</code>\n"
            f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
            f"ℹ️ <b>Reason:</b> {error}\n\n"
            "🟡 <b>Outcome:</b> Manual review required.\n"
            "⚠️ <i>Do not label this payment as fraud solely "
            "because the verifier/provider is unavailable.</i>\n"
            f"⏱️ <b>Audit duration:</b> {elapsed:.2f}s"
        )

    if is_real and not is_hilawe:
        fail_reason = "Receiver name mismatch"
    else:
        fail_reason = (
            bank_data.get("error")
            or "Invalid / transaction not found"
        )

    return (
        "🚨 <b>TRANSACTION REJECTED</b>\n"
        "────────────────────\n"
        f"❌ <b>Result:</b> {html.escape(str(fail_reason))}\n"
        f"👤 <b>Payer:</b> {payer_safe} {time_display}\n"
        f"💰 <b>Amount:</b> {amount:,.2f} ETB\n"
        f"🆔 <b>Ref ID:</b> <code>{reference}</code>\n\n"
        "⚠️ <b>Protocol:</b> Do not release products automatically.\n"
        f"⏱️ <b>Audit duration:</b> {elapsed:.2f}s"
    )


# ─────────────────────────────────────────────
# TEST ROUTER
# ─────────────────────────────────────────────

def get_verifier_menu():
    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(
            text="📸 Upload Screenshot",
            callback_data="test_upload",
        )
    )

    builder.row(
        types.InlineKeyboardButton(
            text="📋 Test Batch (DB)",
            callback_data="test_db_random",
        )
    )

    return builder.as_markup()


@router.callback_query(
    F.data == "test_upload"
)
async def start_upload_test(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    await callback.message.answer(
        "📝 <b>Ready.</b> Send the receipt screenshot now.",
        parse_mode="HTML",
    )

    await state.set_state(
        PaymentStates.waiting_for_screenshot
    )

    await callback.answer()


@router.message(
    PaymentStates.waiting_for_screenshot,
    F.photo,
)
async def handle_screenshot_test(
    message: types.Message,
    state: FSMContext,
    bot: Bot,
):
    start_time = time.perf_counter()

    status_msg = await message.answer(
        "🔄 <b>Analyzing receipt...</b>",
        parse_mode="HTML",
    )

    # ── 1. Download highest-resolution Telegram photo ─────
    t0 = time.perf_counter()

    photo = message.photo[-1]

    file = await bot.get_file(
        photo.file_id
    )

    img_stream = io.BytesIO()

    await bot.download_file(
        file.file_path,
        destination=img_stream,
    )

    img_stream.seek(0)

    t_download = time.perf_counter() - t0

    # ── 2. OCR ────────────────────────────────────────────
    t1 = time.perf_counter()

    local = await extract_local_data(
        img_stream
    )

    t_ocr = time.perf_counter() - t1

    # ── 3. No ref = OCR/manual review, NOT fraud ─────────
    if (
        not local.get("ref")
        or len(str(local["ref"])) < 8
    ):
        raw_preview = html.escape(
            str(local.get("raw_text") or "")[:500]
        )

        await status_msg.edit_text(
            "⚠️ <b>VERIFICATION INCONCLUSIVE</b>\n"
            "────────────────────\n"
            "Could not extract a valid transaction ID.\n\n"
            f"🏦 <b>Detected provider:</b> "
            f"{html.escape(str(local.get('provider') or 'Unknown'))}\n\n"
            "<b>Raw OCR preview:</b>\n"
            f"<code>{raw_preview}</code>\n\n"
            "🟡 <b>Outcome:</b> Manual review required.\n"
            f"⏱️ <b>Elapsed:</b> "
            f"{time.perf_counter() - start_time:.2f}s",
            parse_mode="HTML",
        )

        await state.clear()
        return

    # ── 4. Verify ─────────────────────────────────────────
    await status_msg.edit_text(
        "📡 <b>Querying Veritas:</b> "
        f"<code>{html.escape(str(local['ref']))}</code>...\n"
        f"<i>Detected provider: "
        f"{html.escape(str(local['provider']))}</i>",
        parse_mode="HTML",
    )

    t2 = time.perf_counter()

    bank_data = await verify_external(
        local["ref"],
        local["provider"],
    )

    t_api = time.perf_counter() - t2
    is_real = bool(
        bank_data.get("success", False)
    )

    total = (
        time.perf_counter()
        - start_time
    )

    logger.info(
        "Verifier timings download=%.2fs OCR=%.2fs "
        "API=%.2fs total=%.2fs",
        t_download,
        t_ocr,
        t_api,
        total,
    )

    # ── 5. Report ─────────────────────────────────────────
    is_hilawe = is_hilawe_receiver(
        local.get("raw_text", ""),
        bank_data,
    )

    report = format_audit_report(
        local,
        bank_data,
        total,
        is_real,
        is_hilawe,
    )

    await status_msg.edit_text(
        report,
        parse_mode="HTML",
    )

    await state.clear()


# ─────────────────────────────────────────────
# DB BATCH TEST
# ─────────────────────────────────────────────

@router.callback_query(
    F.data == "test_db_random"
)
async def test_batch_from_db(
    callback: types.CallbackQuery,
    bot: Bot,
    db,
):
    status_msg = await callback.message.answer(
        "🔍 <b>Auditing recent payments...</b>",
        parse_mode="HTML",
    )

    recent = await db.get_recent_payment_proofs(
        5
    )

    if not recent:
        await callback.answer()
        return await status_msg.edit_text(
            "❌ No recent payments found."
        )

    async def process_one(rec):
        start_time = time.perf_counter()

        try:
            img_stream = io.BytesIO()

            file = await bot.get_file(
                rec["proof_file_id"]
            )

            await bot.download_file(
                file.file_path,
                destination=img_stream,
            )

            img_stream.seek(0)

            local = await extract_local_data(
                img_stream
            )

            bank_data: dict = {}

            if local.get("ref"):
                bank_data = await verify_external(
                    local["ref"],
                    local["provider"],
                )
            else:
                bank_data = _manual_review_response(
                    provider=local.get(
                        "provider",
                        "Unknown",
                    ),
                    reference="",
                    error=(
                        "OCR could not extract a "
                        "transaction reference."
                    ),
                )

            is_real = bool(
                bank_data.get("success", False)
            )

            is_hilawe = is_hilawe_receiver(
                local.get("raw_text", ""),
                bank_data,
            )

            api_amount = (
                bank_data.get("amount")
                or (bank_data.get("data") or {}).get("amount")
            )

            if api_amount:
                display_amount = (
                    f"{_to_amount(api_amount):,.2f}"
                )
            else:
                display_amount = (
                    local.get("amount_fallback")
                    or "?"
                )

            elapsed = (
                time.perf_counter()
                - start_time
            )

            state = bank_data.get(
                "verification_state",
                (
                    "verified"
                    if is_real
                    else "rejected"
                ),
            )

            provider_safe = html.escape(
                str(local.get("provider") or "Unknown")
            )
            ref_safe = html.escape(
                str(local.get("ref") or "N/A")
            )

            if is_real and is_hilawe:
                caption = (
                    "🤖 <b>API MATCH: SECURE & VALID ✅</b>\n"
                    "────────────────────\n"
                    f"🟢 <b>Audit #{rec['id']}</b> — "
                    "authentic ledger match.\n\n"
                    f"📊 <b>{provider_safe}</b> · "
                    f"🆔 <code>{ref_safe}</code> · "
                    f"💰 <b>{display_amount} ETB</b>\n"
                    f"⏱️ <b>Speed:</b> {elapsed:.2f}s"
                )

            elif state == "unavailable":
                error = html.escape(
                    str(
                        bank_data.get("error")
                        or "Provider verification unavailable."
                    )
                )

                caption = (
                    "⚠️ <b>VERIFICATION INCONCLUSIVE</b>\n"
                    "────────────────────\n"
                    f"🟡 <b>Audit #{rec['id']}</b> — "
                    "manual review required.\n\n"
                    f"📊 <b>{provider_safe}</b> · "
                    f"🆔 <code>{ref_safe}</code> · "
                    f"💰 <b>{display_amount} ETB</b>\n"
                    f"ℹ️ <b>Reason:</b> {error}\n"
                    f"⏱️ <b>Speed:</b> {elapsed:.2f}s"
                )

            else:
                reason = html.escape(
                    str(
                        bank_data.get("error")
                        or (
                            "Receiver mismatch"
                            if is_real and not is_hilawe
                            else "No verified bank match"
                        )
                    )
                )

                caption = (
                    "🤖 <b>API MATCH: REJECTED 🚨</b>\n"
                    "────────────────────\n"
                    f"🔴 <b>Audit #{rec['id']}</b> — "
                    f"{reason}.\n\n"
                    f"📊 <b>{provider_safe}</b> · "
                    f"🆔 <code>{ref_safe}</code> · "
                    f"💰 <b>{display_amount} ETB</b>\n"
                    f"⏱️ <b>Speed:</b> {elapsed:.2f}s"
                )

            await bot.send_photo(
                chat_id=callback.from_user.id,
                photo=rec["proof_file_id"],
                caption=caption,
                parse_mode="HTML",
            )

        except Exception as exc:
            logger.exception(
                "Batch verification failed for payment %s",
                rec.get("id"),
            )

            await callback.message.answer(
                f"⚠️ <b>Error on #{rec['id']}:</b> "
                f"<code>{html.escape(str(exc))}</code>",
                parse_mode="HTML",
            )

    await asyncio.gather(
        *[
            process_one(rec)
            for rec in recent
        ]
    )

    await status_msg.delete()
    await callback.answer()