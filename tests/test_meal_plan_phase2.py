import hashlib
import hmac
import json
import os
import time
import unittest
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

from meal_plan.auth import TelegramInitDataError, validate_telegram_init_data
from meal_plan.countries import country_label, normalize_region, validate_other_country_name
from meal_plan.runtime import (
    frontend_url_is_valid,
    init_data_max_age_seconds,
    meal_plan_access_allowed,
    meal_plan_enabled,
    meal_plan_public_access_enabled,
)


TOKEN = "123456:TEST_TOKEN"


def signed_init_data(*, user_id=12345, auth_date=1_700_000_000, token=TOKEN, extra=None):
    fields = {
        "auth_date": str(auth_date),
        "query_id": "AAE-test-query",
        "user": json.dumps(
            {
                "id": user_id,
                "first_name": "Dagmawi",
                "username": "demo_user",
                "language_code": "en",
            },
            separators=(",", ":"),
        ),
    }
    if extra:
        fields.update(extra)
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class TelegramInitDataTests(unittest.TestCase):
    def test_valid_signature_authenticates_telegram_user(self):
        payload = signed_init_data()
        identity = validate_telegram_init_data(payload, TOKEN, now=1_700_000_100, max_age_seconds=3600)
        self.assertEqual(identity.telegram_id, 12345)
        self.assertEqual(identity.first_name, "Dagmawi")
        self.assertEqual(identity.username, "demo_user")

    def test_tampered_user_is_rejected(self):
        payload = signed_init_data().replace("12345", "99999")
        with self.assertRaises(TelegramInitDataError) as ctx:
            validate_telegram_init_data(payload, TOKEN, now=1_700_000_100)
        self.assertEqual(ctx.exception.code, "HASH_INVALID")

    def test_wrong_bot_token_is_rejected(self):
        with self.assertRaises(TelegramInitDataError) as ctx:
            validate_telegram_init_data(signed_init_data(), "different-token", now=1_700_000_100)
        self.assertEqual(ctx.exception.code, "HASH_INVALID")

    def test_expired_payload_is_rejected(self):
        with self.assertRaises(TelegramInitDataError) as ctx:
            validate_telegram_init_data(signed_init_data(), TOKEN, now=1_700_010_000, max_age_seconds=3600)
        self.assertEqual(ctx.exception.code, "INIT_DATA_EXPIRED")

    def test_future_auth_date_is_rejected(self):
        with self.assertRaises(TelegramInitDataError) as ctx:
            validate_telegram_init_data(signed_init_data(auth_date=1_700_000_100), TOKEN, now=1_700_000_000)
        self.assertEqual(ctx.exception.code, "AUTH_DATE_INVALID")

    def test_duplicate_field_is_rejected(self):
        payload = signed_init_data() + "&auth_date=1700000000"
        with self.assertRaises(TelegramInitDataError) as ctx:
            validate_telegram_init_data(payload, TOKEN, now=1_700_000_100)
        self.assertEqual(ctx.exception.code, "INIT_DATA_INVALID")


class CountryTests(unittest.TestCase):
    def test_supported_region_normalizes(self):
        self.assertEqual(normalize_region(" ethiopia "), "ETHIOPIA")
        self.assertEqual(normalize_region("uae"), "UAE")

    def test_unknown_region_rejected(self):
        with self.assertRaises(ValueError):
            normalize_region("KENYA")

    def test_other_country_name_is_cleaned(self):
        self.assertEqual(validate_other_country_name("  South   Africa  "), "South Africa")

    def test_other_country_name_bounds(self):
        with self.assertRaises(ValueError):
            validate_other_country_name("K")
        with self.assertRaises(ValueError):
            validate_other_country_name("X" * 81)

    def test_other_label_uses_typed_country(self):
        self.assertEqual(country_label("OTHER", "EN", "Kenya"), "🌍 Kenya")


class RuntimeTests(unittest.TestCase):
    def test_feature_flag_defaults_off(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(meal_plan_enabled())

    def test_feature_flag_can_enable_demo(self):
        with patch.dict(os.environ, {"MEAL_PLAN_ENABLED": "true"}, clear=True):
            self.assertTrue(meal_plan_enabled())

    def test_meal_plan_public_access_defaults_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(meal_plan_public_access_enabled())
            self.assertFalse(meal_plan_access_allowed(999999))

    def test_explicit_public_access_allows_every_authenticated_user(self):
        with patch.dict(os.environ, {"MEAL_PLAN_PUBLIC_ACCESS": "true"}, clear=True):
            self.assertTrue(meal_plan_access_allowed(999999))

    def test_closed_public_access_allows_existing_admin_ids(self):
        env = {"MEAL_PLAN_PUBLIC_ACCESS": "false", "ADMIN_IDS": "101, 202"}
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(meal_plan_access_allowed(202))
            self.assertFalse(meal_plan_access_allowed(303))

    def test_closed_public_access_without_admins_fails_closed(self):
        with patch.dict(os.environ, {"MEAL_PLAN_PUBLIC_ACCESS": "false"}, clear=True):
            self.assertFalse(meal_plan_access_allowed(101))

    def test_frontend_url_requires_https(self):
        self.assertTrue(frontend_url_is_valid("https://meal.example.com"))
        self.assertFalse(frontend_url_is_valid("http://meal.example.com"))
        self.assertFalse(frontend_url_is_valid(""))

    def test_init_data_age_is_bounded(self):
        with patch.dict(os.environ, {"MEAL_PLAN_INIT_DATA_MAX_AGE_SECONDS": "10"}, clear=True):
            self.assertEqual(init_data_max_age_seconds(), 60)
        with patch.dict(os.environ, {"MEAL_PLAN_INIT_DATA_MAX_AGE_SECONDS": "9999999"}, clear=True):
            self.assertEqual(init_data_max_age_seconds(), 86400)


class MenuFeatureFlagTests(unittest.TestCase):
    def test_main_menu_is_guarded_by_runtime_feature_flag(self):
        source = (Path(__file__).resolve().parents[1] / "keyboards" / "reply.py").read_text(encoding="utf-8")
        self.assertIn("meal_plan_enabled()", source)
        self.assertIn("🥗 Meal Plan", source)
        self.assertIn("🥗 የምግብ ፕላን", source)
