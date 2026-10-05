"""Unit tests for the 5-client meal plan pilot broadcast module."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from meal_plan.pilot_broadcast import (
    _authorized_admin,
    fetch_broadcast_targets,
    format_pilot_broadcast_message,
)


class PilotBroadcastFormattingTests(unittest.TestCase):
    def test_paid_male_formatting(self):
        text, kb = format_pilot_broadcast_message("ዳዊት ከበደ", "MALE", has_bought=True, mini_app_url="https://example.com/app")
        self.assertIn("ዳዊት", text)
        self.assertIn("እየሰራህ", text)
        self.assertIn("80%", text)
        self.assertIn("5 ሰዎችን ብቻ", text)
        self.assertNotIn("ጽጌ", text)
        self.assertIn("ዳዊት", kb.inline_keyboard[0][0].text)
        self.assertEqual(kb.inline_keyboard[0][0].web_app.url, "https://example.com/app")

    def test_paid_female_formatting(self):
        text, kb = format_pilot_broadcast_message("ሰላም አለሙ", "FEMALE", has_bought=True, mini_app_url="https://example.com/app")
        self.assertIn("ሰላም", text)
        self.assertIn("እየደከምሽ", text)
        self.assertIn("80%", text)
        self.assertIn("5 ሰዎችን ብቻ", text)
        self.assertNotIn("ጽጌ", text)
        self.assertIn("ሰላም", kb.inline_keyboard[0][0].text)

    def test_unpaid_male_formatting(self):
        text, kb = format_pilot_broadcast_message("ዮናስ", "MALE", has_bought=False)
        self.assertIn("ዮናስ", text)
        self.assertIn("ቆይተሃል", text)
        self.assertIn("5 ሰዎችን ብቻ", text)
        self.assertNotIn("ጽጌ", text)
        self.assertIn("ዮናስ", kb.inline_keyboard[0][0].text)

    def test_unpaid_female_formatting(self):
        text, kb = format_pilot_broadcast_message("ሄለን", "FEMALE", has_bought=False)
        self.assertIn("ሄለን", text)
        self.assertIn("ቆይተሻል", text)
        self.assertIn("5 ሰዎችን ብቻ", text)
        self.assertNotIn("ጽጌ", text)
        self.assertIn("ሄለን", kb.inline_keyboard[0][0].text)

    def test_empty_name_defaults_to_honorific(self):
        text_male, _ = format_pilot_broadcast_message("", "MALE", has_bought=False)
        self.assertIn("ወንድሜ", text_male)

        text_female, _ = format_pilot_broadcast_message(None, "FEMALE", has_bought=False)
        self.assertIn("እህቴ", text_female)


class PilotBroadcastDatabaseAndAuthTests(unittest.IsolatedAsyncioTestCase):
    def test_admin_authorization(self):
        with patch("meal_plan.pilot_broadcast.settings") as mock_settings, \
             patch("meal_plan.pilot_broadcast.admin_ids", return_value=[12345]), \
             patch("meal_plan.pilot_broadcast.reviewer_ids", return_value=[67890]):
            mock_settings.ADMIN_IDS = [999]

            self.assertTrue(_authorized_admin(999))
            self.assertTrue(_authorized_admin(12345))
            self.assertTrue(_authorized_admin(67890))
            self.assertFalse(_authorized_admin(11111))

    async def test_fetch_broadcast_targets(self):
        db = MagicMock()
        db._pool.fetch = AsyncMock(return_value=[
            {"telegram_id": 1, "full_name": "User 1", "gender": "MALE", "has_bought": True},
            {"telegram_id": 2, "full_name": "User 2", "gender": "FEMALE", "has_bought": False},
        ])

        targets = await fetch_broadcast_targets(db, segment="all")
        self.assertEqual(len(targets), 2)
        self.assertTrue(targets[0]["has_bought"])
        self.assertFalse(targets[1]["has_bought"])


if __name__ == "__main__":
    unittest.main()
