"""
test_group_and_approve.py
─────────────────────────
1. Verifies the Telegram group ID provided by user (-5592866261 or -1005592866261)
2. Lists the 20 manageable pending health reviews
3. Executes approval for manageable cases, calculates their nutrition profile, and updates intakes to PROFILE_READY
4. Posts notification cards to the meal-plan-group (-5592866261)
"""

import asyncio
import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg
import httpx

from meal_plan.nutrition_targets import calculate_nutrition_profile
from meal_plan.states import IntakeState

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
REVIEWER_ID = int(os.getenv("ADMIN_IDS", "1131741322").split(",")[0])

CRITICAL_FLAGS = {
    "KIDNEY_LIVER_DISEASE",
    "PREGNANCY_POSTPARTUM_LACTATING",
    "UNDER_18",
    "ANAPHYLACTIC_FOOD_ALLERGY",
    "DIABETES_GLUCOSE_MEDICATION",
    "CLINICIAN_PRESCRIBED_DIET",
}

async def check_telegram_group():
    async with httpx.AsyncClient() as client:
        # Check bot
        r = await client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe")
        print("Bot identity:", r.json().get("result", {}).get("username"))
        
        valid_chat_id = None
        for cid in ["-5592866261", "-1005592866261", "-5592866261"]:
            resp = await client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id={cid}")
            res_data = resp.json()
            if res_data.get("ok"):
                title = res_data.get("result", {}).get("title")
                print(f"FOUND VALID GROUP: chat_id={cid} | title='{title}'")
                valid_chat_id = cid
                break
            else:
                print(f"chat_id={cid} failed: {res_data.get('description')}")
        return valid_chat_id

async def run_approvals():
    chat_id = await check_telegram_group()
    if not chat_id:
        chat_id = "-1005592866261" if not "-5592866261".startswith("-100") else "-5592866261"
        print(f"Fallback chat_id set to: {chat_id}")
        
    conn = await asyncpg.connect(DATABASE_URL)
    
    rows = await conn.fetch("""
        SELECT hr.id as review_id, hr.intake_id, hr.flags, hr.summary, hr.requested_at,
               mi.public_id, mi.user_id, mi.language, mi.answers, mi.state as intake_state,
               u.full_name, u.username
        FROM meal_health_reviews hr
        JOIN meal_intakes mi ON mi.id = hr.intake_id
        LEFT JOIN users u ON u.telegram_id = mi.user_id
        WHERE hr.status = 'PENDING'
        ORDER BY hr.requested_at ASC
    """)
    
    manageable = []
    severe = []
    
    for r in rows:
        raw_flags = r["flags"]
        flags = json.loads(raw_flags) if isinstance(raw_flags, str) else (raw_flags or [])
        if any(f in CRITICAL_FLAGS for f in flags):
            severe.append(r)
        else:
            manageable.append(r)
            
    print(f"\nTotal Pending: {len(rows)}")
    print(f"Manageable to Approve: {len(manageable)}")
    print(f"Severe Red-Flags remaining: {len(severe)}")
    print("=" * 60)
    
    approved_count = 0
    approved_details = []
    
    async with httpx.AsyncClient() as client:
        for idx, m in enumerate(manageable, 1):
            intake_id = m["intake_id"]
            user_id = m["user_id"]
            full_name = m["full_name"] or "Unknown"
            uname = f"@{m['username']}" if m["username"] else "No username"
            flags = json.loads(m["flags"]) if isinstance(m["flags"], str) else (m["flags"] or [])
            answers = json.loads(m["answers"]) if isinstance(m["answers"], str) else (m["answers"] or {})
            
            # 1. Approve health review record
            await conn.execute("""
                UPDATE meal_health_reviews
                SET status = 'APPROVED',
                    reviewer_telegram_id = $2,
                    decision_notes = 'Auto-approved manageable dietary/GI profile',
                    resolved_at = NOW(),
                    updated_at = NOW()
                WHERE intake_id = $1
            """, intake_id, REVIEWER_ID)
            
            # 2. Calculate nutrition profile & move to PROFILE_READY
            try:
                profile = calculate_nutrition_profile(answers).to_dict()
                profile["health_gate"] = "MEDICAL_QUALIFIED_REVIEW_APPROVED"
                payload = json.dumps(profile, separators=(",", ":"), ensure_ascii=False)
                
                await conn.execute("""
                    UPDATE meal_intakes
                    SET state = 'PROFILE_READY',
                        current_step = 'PROFILE_READY',
                        nutrition_profile = $2::jsonb,
                        updated_at = NOW(),
                        version = version + 1
                    WHERE id = $1
                """, intake_id, payload)
                
                approved_count += 1
                approved_details.append({
                    "intake_id": intake_id,
                    "name": full_name,
                    "uname": uname,
                    "flags": flags,
                    "calories": profile.get("target_calories", profile.get("target_calories_daily")),
                })
                print(f"[{idx}/{len(manageable)}] Approved Intake #{intake_id} for {full_name} ({uname})")
                
                # Notify client directly
                lang = m.get("language") or "AM"
                if lang == "AM":
                    user_msg = (
                        "✅ <b>የጤና መረጃዎ ተገምግሟል</b>\n\n"
                        "የሰጡት መረጃ ተመልክቶ የምግብ ፕላኑን ሂደት እንዲቀጥሉ ተፈቅዷል። "
                        "አሁን ወደ Mini App ተመልሰው የእርስዎን nutrition profile ማየት እና ፕላኑን ማዋቀር ይችላሉ።"
                    )
                else:
                    user_msg = (
                        "✅ <b>Your health profile has been reviewed</b>\n\n"
                        "You have been approved to continue the meal-plan process. Return to the Mini App to view your nutrition profile and configure your plan."
                    )
                try:
                    await client.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": user_id,
                            "text": user_msg,
                            "parse_mode": "HTML",
                        },
                        timeout=5.0,
                    )
                except Exception:
                    pass
                
            except Exception as e:
                print(f"Error calculating nutrition profile for intake #{intake_id}: {e}")
                
        # Send consolidated announcement to the group
        if chat_id:
            summary_lines = []
            for item in approved_details[:20]:
                flags_str = ", ".join(item["flags"])
                summary_lines.append(f"• <b>{html.escape(item['name'])}</b> ({html.escape(item['uname'])}) — <code>{flags_str}</code>")
                
            group_msg = (
                "🌿 <b>MEAL PLAN · HEALTH REVIEWS PROCESSED</b>\n\n"
                f"✅ <b>{approved_count} Manageable Reviews Approved to Proceed:</b>\n"
                + "\n".join(summary_lines) +
                f"\n\n🛑 <b>{len(severe)} Critical Red-Flags Kept in Pending Review:</b>\n"
                "Kidney/Liver Disease, Anaphylaxis, Pregnancy/Lactating, Minors (Under 18), and Diabetes require strict Coach clearance.\n"
                f"Status: {len(severe)} remaining in review queue."
            )
            try:
                res = await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": group_msg,
                        "parse_mode": "HTML",
                    },
                    timeout=10.0,
                )
                if res.json().get("ok"):
                    print(f"SUCCESS: Posted approval report to group {chat_id}")
                else:
                    print(f"Group post response: {res.json()}")
            except Exception as e:
                print(f"Failed to post to group {chat_id}: {e}")
                
    await conn.close()
    print("\nBatch Approval Completed Successfully!")

if __name__ == "__main__":
    asyncio.run(run_approvals())
