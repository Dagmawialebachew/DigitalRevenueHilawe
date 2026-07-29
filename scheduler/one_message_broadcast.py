import asyncio
import logging
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import Database
from config import settings

logger = logging.getLogger(__name__)
router = Router(name="admin_broadcast")

class BroadcastStates(StatesGroup):
    waiting_for_message = State()

# ─────────────────────────────────────────
# STEP 1: INITIATE BROADCAST COMMAND
# ─────────────────────────────────────────
@router.message(Command("broadcast_unpaid"), F.from_user.id.in_(settings.ADMIN_IDS))
async def start_unpaid_broadcast(message: types.Message, state: FSMContext, db: Database):
    unpaid_users = await db.fetch_unpaid_users()
    total_count = len(unpaid_users)
    
    if total_count == 0:
        await message.reply("❌ No unpaid users found in the database.")
        return

    await state.update_data(target_users=[dict(u) for u in unpaid_users])
    await state.set_state(BroadcastStates.waiting_for_message)
    
    await message.reply(
        f"🎯 <b>Unpaid Broadcast Target:</b> {total_count} users.\n\n"
        f"Please reply with the exact text or copy you want to broadcast to these unpaid users.\n"
        f"<i>(Send /cancel to abort)</i>",
        parse_mode="HTML"
    )

# ─────────────────────────────────────────
# CANCEL HANDLER
# ─────────────────────────────────────────
@router.message(Command("cancel"), BroadcastStates.waiting_for_message)
async def cancel_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("🚫 Broadcast process cancelled.")

# ─────────────────────────────────────────
# STEP 2: RECEIVE MESSAGE & EXECUTE BROADCAST
# ─────────────────────────────────────────
@router.message(BroadcastStates.waiting_for_message, F.from_user.id.in_(settings.ADMIN_IDS))
async def execute_unpaid_broadcast(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_users = data.get("target_users", [])
    await state.clear()

    total = len(target_users)
    sent_count = 0
    failed_count = 0

    status_msg = await message.reply(f"🚀 Starting broadcast to {total} unpaid users...")

    for index, user in enumerate(target_users, start=1):
        uid = user["telegram_id"]
        try:
            # Send copy of your typed message directly to the target user
            await message.copy_to(chat_id=uid)
            sent_count += 1
        except Exception as e:
            failed_count += 1
            logger.warning(f"Failed broadcast to user {uid}: {e}")

        # Rate-limiting: Telegram limits bots to ~30 messages/sec.
        # Sleeping 0.05s between sends prevents API flood limits (429 Too Many Requests).
        await asyncio.sleep(0.05)

        # Optional: Update admin every 50 users for live progress tracking
        if index % 50 == 0:
            try:
                await status_msg.edit_text(
                    f"⏳ <b>Broadcast in progress...</b>\n"
                    f"Progress: {index}/{total}\n"
                    f"✅ Delivered: {sent_count}\n"
                    f"❌ Failed/Blocked: {failed_count}",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    # Final summary update
    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"👥 Total Target: {total}\n"
        f"✉️ Successfully Sent: {sent_count}\n"
        f"🚫 Blocked/Failed: {failed_count}",
        parse_mode="HTML"
    )