from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from meal_plan.review import MealReviewState, _send_replacement_review_card, replacement_document, review_action
from meal_plan.review_card import replacement_keyboard, review_keyboard
from meal_plan.review_logic import parse_review_callback
from meal_plan.review_repository import MealPlanReviewRepository


class FakeConnection:
    def __init__(self, fetchrow_map=None, fetchval_map=None, fetch_map=None):
        self.fetchrow_map = fetchrow_map or {}
        self.fetchval_map = fetchval_map or {}
        self.fetch_map = fetch_map or {}
        self.executed_sqls = []

    async def fetchrow(self, query: str, *args):
        for pattern, res in self.fetchrow_map.items():
            if pattern in query:
                if callable(res):
                    return res(query, *args)
                return res
        return None

    async def fetchval(self, query: str, *args):
        for pattern, res in self.fetchval_map.items():
            if pattern in query:
                if callable(res):
                    return res(query, *args)
                return res
        return None

    async def fetch(self, query: str, *args):
        for pattern, res in self.fetch_map.items():
            if pattern in query:
                if callable(res):
                    return res(query, *args)
                return res
        return []

    async def execute(self, query: str, *args):
        self.executed_sqls.append((query.strip(), args))


class FakeTransactionContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        pass


class FakeAcquireContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        pass


class FakePool:
    def __init__(self, conn):
        self.conn = conn
        self.conn.transaction = lambda: FakeTransactionContext(self.conn)

    def acquire(self):
        return FakeAcquireContext(self.conn)


class FakeFSMContext:
    def __init__(self, initial_state=None, initial_data=None):
        self._state = initial_state
        self._data = dict(initial_data or {})

    async def get_state(self):
        return self._state

    async def set_state(self, state):
        self._state = getattr(state, "state", state)

    async def get_data(self):
        return dict(self._data)

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def clear(self):
        self._state = None
        self._data = {}


def _create_minimal_docx(path: Path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<document/>")


def _create_minimal_pdf(path: Path):
    path.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\n0 1\n0000000000 65535 f \ntrailer<</Size 1>>\nstartxref\n9\n%%EOF")


class MealPlanReviewReplacementTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_review_callback_accepts_cancel_replace(self):
        action, ver_id = parse_review_callback("mealreview:cancel_replace:42")
        self.assertEqual(action, "cancel_replace")
        self.assertEqual(ver_id, 42)

    def test_replacement_keyboard_renders_cancel_button(self):
        kb = replacement_keyboard(15)
        self.assertEqual(len(kb.inline_keyboard), 1)
        btn = kb.inline_keyboard[0][0]
        self.assertIn("Cancel", btn.text)
        self.assertEqual(btn.callback_data, "mealreview:cancel_replace:15")

    async def test_cancel_replacement_draft_repo(self):
        conn = FakeConnection(
            fetchrow_map={
                "FROM meal_plan_versions WHERE id=$1 FOR UPDATE": {
                    "id": 10,
                    "status": "CHANGES_REQUESTED",
                    "order_id": 5,
                }
            }
        )
        pool = FakePool(conn)
        repo = MealPlanReviewRepository(pool)
        await repo.cancel_replacement_draft(source_version_id=10, replacement_version_id=11, reviewer_id=999)

        executed_sql_texts = [sql for sql, _ in conn.executed_sqls]
        self.assertTrue(any("UPDATE meal_plan_versions SET status='REVIEW_PENDING'" in s for s in executed_sql_texts))
        self.assertTrue(any("DELETE FROM meal_plan_artifacts WHERE plan_version_id=$1" in s for s in executed_sql_texts))
        self.assertTrue(any("DELETE FROM meal_plan_versions WHERE id=$1 AND status='DRAFT'" in s for s in executed_sql_texts))
        self.assertTrue(any("INSERT INTO meal_plan_reviews" in s for s in executed_sql_texts))

    async def test_review_action_replace_activates_fsm_session_and_sends_checklist(self):
        state = FakeFSMContext()
        callback = MagicMock()
        callback.from_user.id = 123
        callback.data = "mealreview:replace:10"
        callback.answer = AsyncMock()
        callback.message = MagicMock()
        callback.message.message_id = 501
        callback.message.chat.id = -1001
        reply_msg = MagicMock()
        reply_msg.message_id = 502
        callback.message.reply = AsyncMock(return_value=reply_msg)

        db = MagicMock()
        repo_mock = MagicMock()
        repo_mock.get_version = AsyncMock(return_value={
            "id": 10,
            "version_number": 1,
            "status": "REVIEW_PENDING",
            "order_id": 5,
            "order_public_id": "ORD-5",
            "full_name": "Abebe B.",
        })
        repo_mock.get_or_create_replacement_draft = AsyncMock(return_value={
            "id": 11,
            "version_number": 2,
            "status": "DRAFT",
        })
        repo_mock.get_review_context = AsyncMock(return_value=(
            {"id": 11, "version_number": 2},
            [],  # No artifacts uploaded yet
        ))

        with patch("meal_plan.review.is_reviewer", return_value=True), \
             patch("meal_plan.review._repo", return_value=repo_mock):
            await review_action(callback, db, state)

        self.assertEqual(await state.get_state(), MealReviewState.awaiting_replacement.state)
        data = await state.get_data()
        self.assertEqual(data["active_source_version_id"], 10)
        self.assertEqual(data["active_replacement_id"], 11)
        self.assertEqual(data["prompt_message_id"], 502)

        callback.message.reply.assert_awaited_once()
        call_args, call_kwargs = callback.message.reply.call_args
        self.assertIn("Replace Files · Session Active", call_args[0])
        self.assertIn("Word Document (.docx)", call_args[0])
        self.assertIn("PDF Document (.pdf)", call_args[0])
        self.assertIn("V1", call_args[0])
        self.assertIn("V2", call_args[0])
        self.assertIsNotNone(call_kwargs.get("reply_markup"))

    async def test_review_action_cancel_replace_clears_fsm_and_edits_message(self):
        state = FakeFSMContext(
            initial_state=MealReviewState.awaiting_replacement.state,
            initial_data={"active_source_version_id": 10, "active_replacement_id": 11},
        )
        callback = MagicMock()
        callback.from_user.id = 123
        callback.data = "mealreview:cancel_replace:10"
        callback.answer = AsyncMock()
        callback.message = MagicMock()
        callback.message.edit_text = AsyncMock()

        db = MagicMock()
        repo_mock = MagicMock()
        repo_mock.cancel_replacement_draft = AsyncMock()
        repo_mock.get_version = AsyncMock(return_value={"id": 10, "version_number": 1})

        with patch("meal_plan.review.is_reviewer", return_value=True), \
             patch("meal_plan.review._repo", return_value=repo_mock):
            await review_action(callback, db, state)

        repo_mock.cancel_replacement_draft.assert_awaited_once_with(10, 11, reviewer_id=123)
        self.assertIsNone(await state.get_state())
        callback.message.edit_text.assert_awaited_once()
        self.assertIn("Replacement Cancelled", callback.message.edit_text.call_args[0][0])

    async def test_replacement_document_non_reviewer_silently_ignored(self):
        state = FakeFSMContext()
        message = MagicMock()
        message.from_user.id = 999
        message.chat.id = -1001
        db = MagicMock()

        with patch("meal_plan.review.is_reviewer", return_value=False):
            await replacement_document(message, db, state)

        message.reply.assert_not_called()

    async def test_replacement_document_private_dm_without_session_sends_guidance(self):
        state = FakeFSMContext()
        message = MagicMock()
        message.from_user.id = 123
        message.chat.type = "private"
        message.chat.id = 123
        message.reply_to_message = None
        message.reply = AsyncMock()
        db = MagicMock()
        repo_mock = MagicMock()

        with patch("meal_plan.review.is_reviewer", return_value=True), \
             patch("meal_plan.review._repo", return_value=repo_mock):
            await replacement_document(message, db, state)

        message.reply.assert_awaited_once()
        self.assertIn("Meal Plan Replacement", message.reply.call_args[0][0])

    async def test_replacement_document_first_file_docx_updates_checklist_progress(self):
        state = FakeFSMContext(
            initial_state=MealReviewState.awaiting_replacement.state,
            initial_data={"active_source_version_id": 10, "active_replacement_id": 11},
        )
        with tempfile.TemporaryDirectory() as td:
            local_docx = Path(td) / "plan.docx"
            _create_minimal_docx(local_docx)

            message = MagicMock()
            message.from_user.id = 123
            message.chat.id = -1001
            message.chat.type = "supergroup"
            message.document.file_name = "custom_plan.docx"
            message.document.mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            message.document.file_id = "doc_file_123"
            message.reply = AsyncMock()

            # Mock download to write the real docx
            async def fake_download(file_id, destination):
                _create_minimal_docx(Path(destination))
            message.bot.download = AsyncMock(side_effect=fake_download)

            db = MagicMock()
            repo_mock = MagicMock()
            repo_mock.get_version = AsyncMock(return_value={"id": 10, "status": "CHANGES_REQUESTED", "version_number": 1})
            repo_mock.get_or_create_replacement_draft = AsyncMock(return_value={"id": 11, "version_number": 2})
            repo_mock.get_review_context = AsyncMock(return_value=(
                {"id": 11, "order_id": 5, "version_number": 2, "full_name": "Abebe"},
                [],
            ))
            repo_mock.store_artifact = AsyncMock()
            repo_mock.replacement_ready = AsyncMock(return_value=False)  # only 1 file so far!

            with patch("meal_plan.review.is_reviewer", return_value=True), \
                 patch("meal_plan.review.review_group_id", return_value=-1001), \
                 patch("meal_plan.review._repo", return_value=repo_mock), \
                 patch("meal_plan.review.version_output_dir", return_value=Path(td)):
                await replacement_document(message, db, state)

            repo_mock.store_artifact.assert_awaited_once()
            message.reply.assert_awaited_once()
            call_text = message.reply.call_args[0][0]
            self.assertIn("File 1/2 Saved", call_text)
            self.assertIn("DOCX", call_text)
            self.assertIn("Still needed", call_text)
            self.assertIn("PDF", call_text)
            # FSM state should still be active
            self.assertEqual(await state.get_state(), MealReviewState.awaiting_replacement.state)

    async def test_replacement_document_second_file_pdf_promotes_and_posts_new_card(self):
        state = FakeFSMContext(
            initial_state=MealReviewState.awaiting_replacement.state,
            initial_data={"active_source_version_id": 10, "active_replacement_id": 11},
        )
        with tempfile.TemporaryDirectory() as td:
            message = MagicMock()
            message.from_user.id = 123
            message.chat.id = -1001
            message.chat.type = "supergroup"
            message.document.file_name = "custom_plan.pdf"
            message.document.mime_type = "application/pdf"
            message.document.file_id = "pdf_file_456"
            message.reply = AsyncMock()

            async def fake_download(file_id, destination):
                _create_minimal_pdf(Path(destination))
            message.bot.download = AsyncMock(side_effect=fake_download)

            db = MagicMock()
            repo_mock = MagicMock()
            repo_mock.get_version = AsyncMock(return_value={"id": 10, "status": "CHANGES_REQUESTED", "version_number": 1})
            repo_mock.get_or_create_replacement_draft = AsyncMock(return_value={"id": 11, "version_number": 2})
            repo_mock.get_review_context = AsyncMock(return_value=(
                {"id": 11, "order_id": 5, "version_number": 2, "full_name": "Abebe"},
                [],
            ))
            repo_mock.store_artifact = AsyncMock()
            repo_mock.replacement_ready = AsyncMock(return_value=True)  # Both files now ready!
            repo_mock.promote_replacement_for_review = AsyncMock()

            with patch("meal_plan.review.is_reviewer", return_value=True), \
                 patch("meal_plan.review.review_group_id", return_value=-1001), \
                 patch("meal_plan.review._repo", return_value=repo_mock), \
                 patch("meal_plan.review.version_output_dir", return_value=Path(td)), \
                 patch("meal_plan.review._send_replacement_review_card", AsyncMock()) as send_card_mock:
                await replacement_document(message, db, state)

            repo_mock.promote_replacement_for_review.assert_awaited_once_with(11, source_version_id=10)
            send_card_mock.assert_awaited_once_with(message.bot, repo_mock, 11, 10)
            # FSM state should now be cleared
            self.assertIsNone(await state.get_state())
            message.reply.assert_awaited_once()
            self.assertIn("Replacement Complete", message.reply.call_args[0][0])
            self.assertIn("V2", message.reply.call_args[0][0])

    def test_replacement_keyboard_renders_check_status_button(self):
        kb = replacement_keyboard(15)
        self.assertEqual(len(kb.inline_keyboard), 1)
        buttons = kb.inline_keyboard[0]
        self.assertEqual(len(buttons), 2)
        self.assertIn("Cancel", buttons[0].text)
        self.assertIn("Check Status", buttons[1].text)
        self.assertEqual(buttons[1].callback_data, "mealreview:check_replace:15")

    async def test_replacement_document_uses_db_fallback_when_fsm_is_lost(self):
        state = FakeFSMContext(initial_state=None, initial_data={})  # Lost FSM state!
        with tempfile.TemporaryDirectory() as td:
            message = MagicMock()
            message.from_user.id = 123
            message.chat.id = -1001
            message.chat.type = "supergroup"
            message.reply_to_message = None  # No reply!
            message.document.file_name = "custom_plan.docx"
            message.document.mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            message.document.file_id = "doc_file_123"
            message.reply = AsyncMock()

            async def fake_download(file_id, destination):
                _create_minimal_docx(Path(destination))
            message.bot.download = AsyncMock(side_effect=fake_download)

            db = MagicMock()
            repo_mock = MagicMock()
            # DB fallback resolves the source version
            repo_mock.find_active_replacement_source = AsyncMock(return_value={"id": 10, "status": "CHANGES_REQUESTED", "version_number": 1})
            repo_mock.get_or_create_replacement_draft = AsyncMock(return_value={"id": 11, "version_number": 2})
            repo_mock.get_review_context = AsyncMock(return_value=(
                {"id": 11, "order_id": 5, "version_number": 2, "full_name": "Abebe"},
                [],
            ))
            repo_mock.store_artifact = AsyncMock()
            repo_mock.replacement_ready = AsyncMock(return_value=False)

            with patch("meal_plan.review.is_reviewer", return_value=True), \
                 patch("meal_plan.review.review_group_id", return_value=-1001), \
                 patch("meal_plan.review._repo", return_value=repo_mock), \
                 patch("meal_plan.review.version_output_dir", return_value=Path(td)):
                await replacement_document(message, db, state)

            repo_mock.find_active_replacement_source.assert_awaited_once_with(
                reviewer_id=123,
                reply_message_id=None,
                chat_id=-1001,
            )
            repo_mock.store_artifact.assert_awaited_once()
            message.reply.assert_awaited_once()
            self.assertIn("File 1/2 Saved", message.reply.call_args[0][0])

    async def test_promote_replacement_for_review_updates_replacement_to_review_pending(self):
        executed_sqls = []

        async def fake_fetchrow(query, *args):
            executed_sqls.append((query.strip(), args))
            if "SELECT * FROM meal_plan_versions WHERE id=$1 FOR UPDATE" in query:
                return {"id": 11, "order_id": 5, "status": "DRAFT", "version_number": 2}
            if "UPDATE meal_plan_versions SET status='REVIEW_PENDING'" in query:
                return {"id": 11, "order_id": 5, "status": "REVIEW_PENDING", "version_number": 2}
            return None

        async def fake_fetchval(query, *args):
            executed_sqls.append((query.strip(), args))
            if "SELECT COUNT(*)" in query:
                return 2
            return None

        async def fake_execute(query, *args):
            executed_sqls.append((query.strip(), args))

        conn = FakeConnection()
        conn.fetchrow = fake_fetchrow
        conn.fetchval = fake_fetchval
        conn.execute = fake_execute

        pool = FakePool(conn)
        repo = MealPlanReviewRepository(pool)
        promoted = await repo.promote_replacement_for_review(11, source_version_id=10)

        self.assertEqual(promoted["status"], "REVIEW_PENDING")
        update_repl_sqls = [q for q, _ in executed_sqls if "UPDATE meal_plan_versions SET status='REVIEW_PENDING'" in q]
        self.assertTrue(len(update_repl_sqls) >= 1)
        update_order_sqls = [q for q, _ in executed_sqls if "UPDATE meal_orders SET state='REVIEW_PENDING'" in q]
        self.assertTrue(len(update_order_sqls) >= 1)


if __name__ == "__main__":
    unittest.main()
