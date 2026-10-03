from __future__ import annotations

import html
import logging
import shutil
import tempfile
from pathlib import Path

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile

from database.db import Database
from meal_plan.delivery import deliver_approved_plan
from meal_plan.documents.helpers import artifact_basename
from meal_plan.documents.storage import version_output_dir
from meal_plan.repository import ConcurrentUpdate, RecordNotFound
from meal_plan.review_card import approved_keyboard, replacement_keyboard, review_card_text, review_keyboard
from meal_plan.review_files import ReviewFileError, classify_review_filename, validate_review_file
from meal_plan.review_logic import parse_review_callback
from meal_plan.review_repository import MealPlanReviewRepository
from meal_plan.runtime import is_reviewer, review_group_id, review_upload_max_bytes

router = Router(name="meal_plan_review")
logger = logging.getLogger(__name__)


class MealReviewState(StatesGroup):
    awaiting_replacement = State()



def _repo(db: Database) -> MealPlanReviewRepository:
    pool = getattr(db, "_pool", None)
    if pool is None:
        raise RuntimeError("Database pool is not connected")
    return MealPlanReviewRepository(pool)


async def _send_replacement_review_card(bot, repo: MealPlanReviewRepository, replacement_id: int, source_id: int):
    version, artifacts = await repo.get_review_context(replacement_id)
    source = await repo.get_version(source_id)
    group_chat = review_group_id()
    chat_id = group_chat or (source.get("review_chat_id") if source else None)
    if not chat_id:
        raise RuntimeError("MEAL_PLAN_REVIEW_GROUP_ID is not configured")
    card = await bot.send_message(chat_id, "⏳ Preparing replacement review packet…")
    for artifact in artifacts:
        telegram_file_id = artifact.get("telegram_file_id")
        if telegram_file_id:
            await bot.send_document(
                chat_id,
                telegram_file_id,
                caption=f"{artifact['artifact_type']} · replacement V{version['version_number']} · {str(artifact.get('content_sha256') or '')[:12]}",
                reply_to_message_id=card.message_id,
            )
        else:
            path = Path(str(artifact["storage_key"]))
            await bot.send_document(
                chat_id,
                FSInputFile(path, filename=artifact["original_filename"]),
                caption=f"{artifact['artifact_type']} · replacement V{version['version_number']} · {str(artifact.get('content_sha256') or '')[:12]}",
                reply_to_message_id=card.message_id,
            )
    await bot.edit_message_text(
        review_card_text(version),
        chat_id=chat_id,
        message_id=card.message_id,
        parse_mode="HTML",
        reply_markup=review_keyboard(replacement_id),
    )
    await repo.mark_review_handoff(replacement_id, chat_id=chat_id, message_id=card.message_id)
    if source and source.get("review_chat_id") and source.get("review_message_id"):
        try:
            await bot.edit_message_reply_markup(chat_id=source["review_chat_id"], message_id=source["review_message_id"], reply_markup=None)
        except Exception:
            pass
    return card


@router.callback_query(F.data.startswith("mealreview:"))
async def review_action(callback: types.CallbackQuery, db: Database, state: FSMContext):
    if not is_reviewer(callback.from_user.id):
        return await callback.answer("Not authorized for Meal Plan review.", show_alert=True)
    try:
        action, plan_version_id = parse_review_callback(callback.data or "")
    except ValueError as exc:
        return await callback.answer(str(exc), show_alert=True)

    repo = _repo(db)
    try:
        if action == "client":
            version, _ = await repo.get_review_context(plan_version_id)
            name = str(version.get("full_name") or "Member")
            username = f"@{version['username']}" if version.get("username") else "No public username"
            await callback.answer(f"{name}\n{username}\nTelegram ID: {version['user_id']}", show_alert=True)
            return

        if action == "replace":
            version = await repo.get_version(plan_version_id)
            if not version or version["status"] not in {"REVIEW_PENDING", "CHANGES_REQUESTED"}:
                raise ConcurrentUpdate("This version is no longer awaiting file replacement")
            draft = await repo.get_or_create_replacement_draft(plan_version_id, callback.from_user.id)
            _, draft_artifacts = await repo.get_review_context(draft["id"])
            has_docx = any(a["artifact_type"] == "DOCX" for a in draft_artifacts)
            has_pdf = any(a["artifact_type"] == "PDF" for a in draft_artifacts)

            docx_status = "✅ Word Document (.docx) uploaded" if has_docx else "⬜ Word Document (.docx)"
            pdf_status = "✅ PDF Document (.pdf) uploaded" if has_pdf else "⬜ PDF Document (.pdf)"

            await state.set_state(MealReviewState.awaiting_replacement)
            card_msg_id = callback.message.message_id if callback.message else None
            card_chat_id = callback.message.chat.id if callback.message else None
            await state.update_data(
                active_source_version_id=plan_version_id,
                active_replacement_id=draft["id"],
                review_card_message_id=card_msg_id,
                review_chat_id=card_chat_id,
            )

            await callback.answer("Replacement session active. Send the corrected files.", show_alert=False)
            client_name = html.escape(str(version.get("full_name") or "Member"))
            order_id = html.escape(str(version.get("order_public_id") or version["order_id"]))
            prompt_text = (
                f"📎 <b>Replace Files · Session Active</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>{client_name}</b> · Order <code>{order_id}</code>\n"
                f"📄 Replacing <b>V{version['version_number']}</b> → Creating <b>V{draft['version_number']}</b>\n\n"
                f"<b>Upload Checklist:</b>\n"
                f"• {docx_status}\n"
                f"• {pdf_status}\n\n"
                f"📤 Send or drag-and-drop the files now (direct send or reply both work).\n"
                f"Both files must be uploaded before the new version can be approved."
            )
            prompt_msg = await callback.message.reply(
                prompt_text,
                parse_mode="HTML",
                reply_markup=replacement_keyboard(plan_version_id),
            )
            await state.update_data(prompt_message_id=prompt_msg.message_id)
            return

        if action == "cancel_replace":
            data = await state.get_data()
            source_id = data.get("active_source_version_id") or plan_version_id
            replacement_id = data.get("active_replacement_id")
            await repo.cancel_replacement_draft(source_id, replacement_id, reviewer_id=callback.from_user.id)
            await state.clear()
            await callback.answer("File replacement cancelled.", show_alert=True)
            source_ver = await repo.get_version(source_id)
            v_num = source_ver["version_number"] if source_ver else plan_version_id
            try:
                await callback.message.edit_text(
                    f"❌ <b>Replacement Cancelled</b>\n\n"
                    f"Version <b>V{v_num}</b> remains active in review. You can approve it or regenerate at any time.",
                    parse_mode="HTML",
                    reply_markup=None,
                )
            except Exception:
                pass
            return

        if action == "regen":
            await state.clear()
            version, order, job = await repo.queue_regeneration(plan_version_id, callback.from_user.id)
            await callback.answer("New generation queued")
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
                await callback.message.reply(
                    f"🔁 <b>Generate Again</b> queued by {html.escape(callback.from_user.full_name)} · job <code>#{job['id']}</code>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
            return

        if action in {"approve", "deliver"}:
            await state.clear()
            if action == "approve":
                try:
                    version, order = await repo.approve_version(plan_version_id, callback.from_user.id)
                except ValueError as exc:
                    await callback.answer(str(exc)[:200], show_alert=True)
                    try:
                        await callback.message.reply(
                            f"⚠️ <b>Approval Blocked:</b>\n{html.escape(str(exc))}\n\n"
                            "To proceed:\n"
                            "• Click <b>🔁 Generate Again</b> to regenerate\n"
                            "• Click <b>📎 Replace Files</b> to upload corrected .docx and .pdf\n",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
                    return

                await callback.answer("Approved. Delivering to client…")
                try:
                    await callback.message.edit_reply_markup(reply_markup=approved_keyboard(plan_version_id))
                    await callback.message.reply(
                        f"✅ Approved by {html.escape(callback.from_user.full_name)} · V{version['version_number']} is now the authoritative client version.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            else:
                await callback.answer("Checking delivery…")

            try:
                result = await deliver_approved_plan(callback.bot, db, repo, plan_version_id)
                active_order = result["order"]
                try:
                    await callback.message.reply(
                        f"📤 <b>Client delivery complete.</b> Order is now <code>{html.escape(str(active_order['state']))}</code>.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            except Exception as exc:
                logger.exception("Approved Meal Plan delivery failed")
                try:
                    await callback.message.reply(
                        "⚠️ <b>Approval is saved, but delivery did not complete.</b>\n"
                        f"Reason: <code>{html.escape(type(exc).__name__)}</code>\n"
                        "Use <b>Retry / Check Delivery</b> after fixing the storage/bot issue. Approval will not be duplicated.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            return
    except (RecordNotFound, ConcurrentUpdate, ValueError) as exc:
        return await callback.answer(str(exc), show_alert=True)
    except Exception as exc:
        logger.exception("Meal Plan review callback failed")
        return await callback.answer(f"Review action failed: {type(exc).__name__}", show_alert=True)


@router.message(F.document)
async def replacement_document(message: types.Message, db: Database, state: FSMContext):
    """Accept manual Coach replacements via active FSM session or direct reply."""
    if not message.from_user or not is_reviewer(message.from_user.id):
        return

    group_id = review_group_id()
    is_group = bool(group_id and message.chat.id == group_id)
    is_private = message.chat.type == "private"
    if not (is_group or is_private):
        return

    repo = _repo(db)
    source = None
    data = await state.get_data()
    current_state = await state.get_state()

    # Priority 1: Reviewer is actively in replacement session
    if current_state == MealReviewState.awaiting_replacement.state:
        source_id = data.get("active_source_version_id")
        if source_id:
            source = await repo.get_version(source_id)

    # Priority 2: Message is a reply to the original review card
    if not source and message.reply_to_message:
        source = await repo.get_version_by_review_message(message.chat.id, message.reply_to_message.message_id)

    # Priority 3: Message is a reply to the replacement prompt message
    if not source and message.reply_to_message and data.get("prompt_message_id") == message.reply_to_message.message_id:
        source_id = data.get("active_source_version_id")
        if source_id:
            source = await repo.get_version(source_id)

    if not source:
        if is_private:
            await message.reply(
                "ℹ️ <b>Meal Plan Replacement</b>\n\n"
                "To replace documents for a meal plan, please click <b>📎 Replace Files</b> on the review card in the Coach Review group, or reply directly to the review card.",
                parse_mode="HTML",
            )
        return

    if source["status"] not in {"REVIEW_PENDING", "CHANGES_REQUESTED"}:
        return await message.reply("This meal plan version is no longer accepting replacement files.")

    document = message.document
    filename = document.file_name or "replacement"
    try:
        artifact_type = classify_review_filename(filename, document.mime_type)
    except ReviewFileError as exc:
        return await message.reply(f"❌ {html.escape(str(exc))}")

    suffix = ".pdf" if artifact_type == "PDF" else ".docx"
    temp_dir = Path(tempfile.mkdtemp(prefix="hilawe-review-"))
    temp_path = temp_dir / f"upload{suffix}"
    try:
        await message.bot.download(document.file_id, destination=temp_path)
        checked = validate_review_file(
            temp_path,
            filename=filename,
            mime_type=document.mime_type,
            max_bytes=review_upload_max_bytes(),
        )
        replacement = await repo.get_or_create_replacement_draft(source["id"], message.from_user.id)
        version_ctx, _ = await repo.get_review_context(replacement["id"])
        out_dir = version_output_dir(f"MP-{version_ctx['order_id']:06d}", replacement["version_number"])
        basename = artifact_basename(f"MP-{version_ctx['order_id']:06d}", str(version_ctx.get("full_name") or "Client"), replacement["version_number"])
        final_path = out_dir / f"{basename}{suffix}"
        shutil.copy2(checked.path, final_path)
        await repo.store_artifact(
            replacement["id"],
            artifact_type=artifact_type,
            storage_key=str(final_path.resolve()),
            original_filename=final_path.name,
            content_sha256=checked.sha256,
            byte_size=checked.byte_size,
            telegram_file_id=document.file_id,
            created_by=message.from_user.id,
        )
        ready = await repo.replacement_ready(replacement["id"])
        if not ready:
            other = "PDF (.pdf)" if artifact_type == "DOCX" else "Word (.docx)"
            received_icon = "📄" if artifact_type == "DOCX" else "📕"
            waiting_icon = "📕" if artifact_type == "DOCX" else "📄"
            await state.set_state(MealReviewState.awaiting_replacement)
            await state.update_data(
                active_source_version_id=source["id"],
                active_replacement_id=replacement["id"],
            )
            return await message.reply(
                f"✅ <b>File 1/2 Saved:</b> {received_icon} <b>{artifact_type}</b> (<code>{html.escape(filename)}</code>)\n"
                f"Draft: <b>V{replacement['version_number']}</b>\n\n"
                f"⏳ <b>Still needed:</b> {waiting_icon} <b>{other}</b>\n\n"
                "Please send the remaining file now to complete the replacement.",
                parse_mode="HTML",
                reply_markup=replacement_keyboard(source["id"]),
            )

        await repo.promote_replacement_for_review(replacement["id"], source_version_id=source["id"])
        await _send_replacement_review_card(message.bot, repo, replacement["id"], source["id"])
        await state.clear()

        target_group = review_group_id()
        location_note = "in the Coach Review group" if (is_private and target_group) else "above"
        await message.reply(
            f"🎉 <b>Replacement Complete!</b>\n\n"
            f"Both corrected <b>.docx</b> and <b>.pdf</b> files have been saved as <b>V{replacement['version_number']}</b>.\n"
            f"The new review card is now live {location_note} with full action buttons.",
            parse_mode="HTML",
        )
    except (ReviewFileError, ConcurrentUpdate, RecordNotFound) as exc:
        await message.reply(f"❌ {html.escape(str(exc))}")
    except Exception as exc:
        logger.exception("Manual Meal Plan replacement failed")
        await message.reply(f"❌ Replacement failed: {html.escape(type(exc).__name__)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

