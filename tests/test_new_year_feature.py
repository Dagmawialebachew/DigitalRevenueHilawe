"""Unit tests for the 2019 Ethiopian New Year Free Gift and Growth Funnel."""

from __future__ import annotations

import re
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.new_year import (
    get_bridge_text,
    get_new_year_caption,
    handle_2019_claim_button,
    handle_2019_universal,
    handle_start_onboarding_from_gift,
    send_new_year_bundle,
)
from handlers.onboarding import OnboardingStepping


class TestNewYearFeature(unittest.IsolatedAsyncioTestCase):
    def test_2019_regex_matching(self):
        pattern = re.compile(r"^\s*2019\s*$")
        self.assertTrue(pattern.match("2019"))
        self.assertTrue(pattern.match(" 2019 "))
        self.assertTrue(pattern.match("\n2019\t"))
        self.assertFalse(pattern.match("2019 free"))
        self.assertFalse(pattern.match("hello 2019"))
        self.assertFalse(pattern.match("2019!"))
        self.assertFalse(pattern.match("20199"))

    def test_captions_and_bridge_texts_not_empty(self):
        am_cap = get_new_year_caption("AM")
        en_cap = get_new_year_caption("EN")
        self.assertIn("2019", am_cap)
        self.assertIn("ህላዌ", am_cap)
        self.assertIn("2019", en_cap)

        am_bridge = get_bridge_text("AM")
        en_bridge = get_bridge_text("EN")
        self.assertIn("8-ሳምንት", am_bridge)
        self.assertIn("8-week", en_bridge)

    def test_gender_adaptive_captions_and_bridge_texts(self):
        # 1. Female conjugation
        fem_cap = get_new_year_caption("AM", "FEMALE")
        self.assertIn("አደረሰሽ", fem_cap)
        self.assertIn("ራስሽን", fem_cap)
        self.assertIn("አንብቢው", fem_cap)
        self.assertNotIn("አለብህ", fem_cap)
        self.assertNotIn("ራስህን", fem_cap)

        fem_bridge = get_bridge_text("AM", "FEMALE")
        self.assertIn("ለአንቺ", fem_bridge)
        self.assertIn("ስትመሪ", fem_bridge)
        self.assertIn("ፕሮግራምሽን", fem_bridge)
        self.assertNotIn("ለአንተ", fem_bridge)
        self.assertNotIn("ፕሮግራምህን", fem_bridge)

        # 2. Male conjugation
        male_cap = get_new_year_caption("AM", "MALE")
        self.assertIn("አደረሰህ", male_cap)
        self.assertIn("ራስህን", male_cap)
        self.assertIn("አንብበው", male_cap)

        male_bridge = get_bridge_text("AM", "MALE")
        self.assertIn("ለአንተ", male_bridge)
        self.assertIn("ስትመራ", male_bridge)
        self.assertIn("ፕሮግራምህን", male_bridge)

        # 3. Unknown gender (respectful formal / gender-neutral)
        neutral_cap = get_new_year_caption("AM", None)
        self.assertIn("አደረሳችሁ", neutral_cap)
        self.assertIn("ራስዎን", neutral_cap)
        self.assertIn("ያንብቡት", neutral_cap)
        self.assertNotIn("አለብህ", neutral_cap)
        self.assertNotIn("ራስህን", neutral_cap)

        neutral_bridge = get_bridge_text("AM", None)
        self.assertIn("ለእርስዎ", neutral_bridge)
        self.assertIn("ፕሮግራምዎን", neutral_bridge)
        self.assertNotIn("ለአንተ", neutral_bridge)
        self.assertNotIn("ለአንቺ", neutral_bridge)

    async def test_send_new_year_bundle_sends_doc_and_bridge(self):
        bot = AsyncMock()
        db = AsyncMock()
        db.get_user = AsyncMock(return_value={"language": "AM", "gender": "FEMALE"})
        db.record_new_year_claim = AsyncMock()
        state = AsyncMock()
        state.get_data.return_value = {}

        user = MagicMock(id=1234567, full_name="Sara Solomon", username="sara")

        with patch("handlers.new_year.PDF_PATH") as mock_path, patch(
            "asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            mock_path.exists.return_value = True

            # Mock send_document returning a document with a file_id
            sent_doc = MagicMock()
            sent_doc.document = MagicMock(file_id="tg_file_id_2019_test")
            bot.send_document.return_value = sent_doc

            await send_new_year_bundle(
                chat_id=1234567,
                user=user,
                bot=bot,
                db=db,
                state=state,
            )

            # Assert claim was recorded in database
            db.record_new_year_claim.assert_awaited_once_with(
                telegram_id=1234567,
                full_name="Sara Solomon",
                username="sara",
            )

            # Assert document was sent with female caption
            bot.send_document.assert_awaited_once()
            doc_call = bot.send_document.call_args[1]
            self.assertIn("አደረሰሽ", doc_call["caption"])
            self.assertIn("ራስሽን", doc_call["caption"])

            # Assert typing action was sent
            bot.send_chat_action.assert_awaited_once()
            # Assert 3.5s sleep was called
            mock_sleep.assert_awaited_once_with(3.5)
            # Assert bridge message was sent with female phrasing
            bot.send_message.assert_awaited_once()
            bridge_call = bot.send_message.call_args[1]
            self.assertIn("ለአንቺ", bridge_call["text"])
            self.assertIn("ፕሮግራምሽን", bridge_call["text"])
            self.assertNotIn("ለአንተ", bridge_call["text"])

    async def test_handle_2019_universal_message(self):
        message = AsyncMock()
        message.chat = MagicMock(id=987654)
        message.from_user = MagicMock(id=987654, full_name="Kebede", username="kebede")
        state = AsyncMock()
        bot = AsyncMock()
        db = AsyncMock()

        with patch("handlers.new_year.send_new_year_bundle", new_callable=AsyncMock) as mock_bundle:
            await handle_2019_universal(message, state, bot, db)
            mock_bundle.assert_awaited_once_with(
                chat_id=987654,
                user=message.from_user,
                bot=bot,
                db=db,
                state=state,
            )

    async def test_handle_start_onboarding_from_gift(self):
        callback = AsyncMock()
        callback.from_user = MagicMock(id=555666)
        callback.message = AsyncMock()
        state = AsyncMock()
        db = AsyncMock()
        db.get_user = AsyncMock(return_value={"language": "AM"})

        await handle_start_onboarding_from_gift(callback, state, db)

        callback.answer.assert_awaited_once()
        state.update_data.assert_awaited_once_with(language="AM")
        callback.message.answer.assert_awaited_once()
        state.set_state.assert_awaited_once_with(OnboardingStepping.gender)


if __name__ == "__main__":
    unittest.main()
