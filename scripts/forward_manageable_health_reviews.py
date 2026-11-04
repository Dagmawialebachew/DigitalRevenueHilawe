"""
forward_manageable_health_reviews.py
────────────────────────────────────
Reverts the 20 manageable intakes to HEALTH_REVIEW_REQUIRED / PENDING state
and forwards the exact triggering message with the normal inline buttons:
  [✅ Approve to proceed]  [⛔ Outside scope]
to the Meal Plan Group (-5592866261).
"""

import asyncio
import html
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TARGET_CHAT_ID = "-5592866261"

FLAG_LABELS = {
    "UNDER_18": "Under 18",
    "PREGNANCY_POSTPARTUM_LACTATING": "Pregnant / postpartum / lactating",
    "EATING_DISORDER_CONCERN": "Eating-disorder concern",
    "KIDNEY_LIVER_DISEASE": "Kidney / liver disease",
    "DIABETES_GLUCOSE_MEDICATION": "Diabetes / glucose medication",
    "CLINICIAN_PRESCRIBED_DIET": "Clinician-prescribed diet",
    "SEVERE_GI_CONDITION": "Severe GI symptoms / disease",
    "ANAPHYLACTIC_FOOD_ALLERGY": "Anaphylactic food allergy",
    "UNEXPLAINED_WEIGHT_CHANGE": "Unexplained weight change",
    "OTHER_HEALTH_CHANGE": "Other important health change",
}

CRITICAL_FLAGS = {
    "KIDNEY_LIVER_DISEASE",
    "PREGNANCY_POSTPARTUM_LACTATING",
    "UNDER_18",
    "ANAPHYLACTIC_FOOD_ALLERGY",
    "DIABETES_GLUCOSE_MEDICATION",
    "CLINICIAN_PRESCRIBED_DIET",
}

# The 20 manageable intake IDs
MANAGEABLE_INTAKE_IDS = [
    129, 145, 291, 353, 356, 357, 358, 384, 396, 404,
    412, 448, 95, 483, 491, 492, 506, 514, 522, 540
]

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    
    print(f"Reverting {len(MANAGEABLE_INTAKE_IDS)} manageable intakes to HEALTH_REVIEW_REQUIRED / PENDING...")
    await conn.execute("""
        UPDATE meal_intakes
        SET state = 'HEALTH_REVIEW_REQUIRED',
            current_step = 'HEALTH_REVIEW_REQUIRED',
            updated_at = NOW()
        WHERE id = ANY($1::int[])
    """, MANAGEABLE_INTAKE_IDS)
    
    await conn.execute("""
        UPDATE meal_health_reviews
        SET status = 'PENDING',
            reviewer_telegram_id = NULL,
            decision_notes = NULL,
            resolved_at = NULL,
            updated_at = NOW()
        WHERE intake_id = ANY($1::int[])
    """, MANAGEABLE_INTAKE_IDS)
    
    # Query details for forwarding
    rows = await conn.fetch("""
        SELECT hr.id as review_id, hr.intake_id, hr.flags, mi.public_id, mi.user_id,
               u.full_name, u.username
        FROM meal_health_reviews hr
        JOIN meal_intakes mi ON mi.id = hr.intake_id
        LEFT JOIN users u ON u.telegram_id = mi.user_id
        WHERE hr.intake_id = ANY($1::int[])
        ORDER BY hr.intake_id ASC
    """, MANAGEABLE_INTAKE_IDS)
    
    await conn.close()
    
    print(f"Forwarding {len(rows)} exact triggering messages with buttons to {TARGET_CHAT_ID}...")
    
    sent_count = 0
    async with httpx.AsyncClient() as client:
        for idx, r in enumerate(rows, 1):
            intake_id = r["intake_id"]
            public_id = r["public_id"]
            first_name = r["full_name"] or "Client"
            username = f"@{html.escape(r['username'])}" if r["username"] else "No public username"
            
            raw_flags = r["flags"]
            flags = json.loads(raw_flags) if isinstance(raw_flags, str) else (raw_flags or [])
            
            flag_lines = "\n".join(f"• {FLAG_LABELS.get(f, f)}" for f in flags)
            
            text = (
                "⚕️ <b>MEAL PLAN · HEALTH REVIEW</b>\n\n"
                f"Client: <b>{html.escape(first_name)}</b>\n"
                f"Telegram: {username}\n"
                f"Intake: <code>{html.escape(str(public_id))}</code>\n\n"
                "<b>Hilawe safety gate flags</b>\n"
                f"{flag_lines}\n\n"
                "No payment has been collected. Approve only if this client may proceed with the meal-plan service."
            )
            
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Approve to proceed", "callback_data": f"meal_health:approve:{intake_id}"},
                        {"text": "⛔ Outside scope", "callback_data": f"meal_health:decline:{intake_id}"}
                    ]
                ]
            }
            
            payload = {
                "chat_id": TARGET_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": reply_markup
            }
            
            try:
                res = await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json=payload,
                    timeout=10.0
                )
                data = res.json()
                if data.get("ok"):
                    msg_id = data["result"]["message_id"]
                    sent_count += 1
                    print(f"[{idx}/{len(rows)}] Sent card for Intake #{intake_id} ({first_name}) -> Msg #{msg_id}")
                else:
                    print(f"[{idx}/{len(rows)}] FAILED Intake #{intake_id}: {data.get('description')}")
            except Exception as e:
                print(f"[{idx}/{len(rows)}] Error Intake #{intake_id}: {e}")
                
            await asyncio.sleep(0.35)  # Pace to avoid Telegram 429 rate limit
            
    print(f"\nCompleted! Successfully forwarded {sent_count}/{len(rows)} review cards with buttons.")

if __name__ == "__main__":
    asyncio.run(main())
