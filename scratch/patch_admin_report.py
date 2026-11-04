import re

with open("scheduler/retarget_incomplete_onboarding.py", "r", encoding="utf-8") as f:
    code = f.read()

old_finish = """    print("=" * 60)
    print("🏁 BROADCAST FINISHED")
    print(f"Total Targets: {total}")
    print(f"✅ Delivered: {sent}")
    print(f"🚫 Blocked: {blocked}")
    print(f"❌ Failed: {failed}")
    print("=" * 60)"""

new_finish = """    print("=" * 60)
    print("🏁 BROADCAST FINISHED")
    print(f"Total Targets: {total}")
    print(f"✅ Delivered: {sent}")
    print(f"🚫 Blocked: {blocked}")
    print(f"❌ Failed: {failed}")
    print("=" * 60)

    # Send Execution Report to Admin Telegram
    admin_ids = settings.ADMIN_IDS or [1131741322]
    delivery_rate = (sent / total * 100) if total > 0 else 0
    blocked_rate = (blocked / total * 100) if total > 0 else 0

    report_text = (
        f"📢 <b>ONBOARDING RETARGETING REPORT</b>\\n"
        f"━━━━━━━━━━━━━━━━━━━━━\\n"
        f"🎯 <b>Audience:</b> Incomplete Onboarding Users\\n"
        f"👥 <b>Total Targets:</b> {total}\\n"
        f"✅ <b>Successfully Delivered:</b> {sent} ({delivery_rate:.1f}%)\\n"
        f"🚫 <b>Blocked Bot:</b> {blocked} ({blocked_rate:.1f}%)\\n"
        f"❌ <b>Other Failed:</b> {failed}\\n"
        f"━━━━━━━━━━━━━━━━━━━━━\\n"
        f"⚡️ <b>Campaign Hook:</b> 380k community + 1,700+ buyers proof\\n"
        f"🎯 <b>Action:</b> 1-Tap Onboarding Resume (Full-Price 949 ETB Funnel)\\n"
        f"🕒 <b>Delivered At:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\\n"
    )

    for aid in admin_ids:
        try:
            await bot.send_message(chat_id=aid, text=report_text, parse_mode="HTML")
            logger.info(f"Report delivered to Admin {aid} on Telegram.")
        except Exception as e:
            logger.error(f"Failed to send report to Admin {aid}: {e}")"""

code = code.replace(old_finish, new_finish)

with open("scheduler/retarget_incomplete_onboarding.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated scheduler/retarget_incomplete_onboarding.py with admin report delivery!")

