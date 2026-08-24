"""Telegram Mini App initData validation.

The browser is never trusted to tell us which Telegram user it represents.
Identity is derived only after validating Telegram's signed initData with the bot
token and checking auth_date freshness.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl


class TelegramInitDataError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TelegramMiniAppIdentity:
    telegram_id: int
    first_name: str
    last_name: str | None
    username: str | None
    language_code: str | None
    auth_date: int
    raw_user: dict[str, Any]


def _parse_pairs(init_data: str) -> dict[str, str]:
    if not init_data or not init_data.strip():
        raise TelegramInitDataError("INIT_DATA_MISSING", "Telegram initData is missing")

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    if not pairs:
        raise TelegramInitDataError("INIT_DATA_INVALID", "Telegram initData is malformed")

    data: dict[str, str] = {}
    for key, value in pairs:
        if key in data:
            raise TelegramInitDataError("INIT_DATA_INVALID", "Telegram initData contains duplicate fields")
        data[key] = value
    return data


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 3600,
    now: int | None = None,
) -> TelegramMiniAppIdentity:
    """Validate Telegram Mini App initData and return the authenticated user.

    Uses Telegram's HMAC-SHA256 WebAppData validation algorithm. ``auth_date`` is
    also bounded so a captured payload cannot be replayed indefinitely.
    """

    if not bot_token:
        raise TelegramInitDataError("SERVER_MISCONFIGURED", "Bot token is not configured")

    data = _parse_pairs(init_data)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise TelegramInitDataError("HASH_MISSING", "Telegram initData hash is missing")

    data_check_string = "\n".join(f"{key}={data[key]}" for key in sorted(data))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash.lower()):
        raise TelegramInitDataError("HASH_INVALID", "Telegram initData signature is invalid")

    raw_auth_date = data.get("auth_date")
    if raw_auth_date is None:
        raise TelegramInitDataError("AUTH_DATE_MISSING", "Telegram auth_date is missing")
    try:
        auth_date = int(raw_auth_date)
    except (TypeError, ValueError) as exc:
        raise TelegramInitDataError("AUTH_DATE_INVALID", "Telegram auth_date is invalid") from exc

    current_time = int(time.time() if now is None else now)
    if auth_date > current_time + 30:
        raise TelegramInitDataError("AUTH_DATE_INVALID", "Telegram auth_date is in the future")
    if current_time - auth_date > max_age_seconds:
        raise TelegramInitDataError("INIT_DATA_EXPIRED", "Telegram initData has expired")

    raw_user = data.get("user")
    if not raw_user:
        raise TelegramInitDataError("USER_MISSING", "Telegram user payload is missing")
    try:
        user = json.loads(raw_user)
    except json.JSONDecodeError as exc:
        raise TelegramInitDataError("USER_INVALID", "Telegram user payload is invalid") from exc
    if not isinstance(user, dict):
        raise TelegramInitDataError("USER_INVALID", "Telegram user payload is invalid")

    try:
        telegram_id = int(user["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TelegramInitDataError("USER_INVALID", "Telegram user id is invalid") from exc
    if telegram_id <= 0:
        raise TelegramInitDataError("USER_INVALID", "Telegram user id is invalid")

    first_name = str(user.get("first_name") or "").strip()
    if not first_name:
        first_name = "Member"

    return TelegramMiniAppIdentity(
        telegram_id=telegram_id,
        first_name=first_name,
        last_name=(str(user["last_name"]).strip() if user.get("last_name") else None),
        username=(str(user["username"]).strip() if user.get("username") else None),
        language_code=(str(user["language_code"]).strip() if user.get("language_code") else None),
        auth_date=auth_date,
        raw_user=user,
    )
