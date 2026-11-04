"""
audit_pending_health_reviews.py
───────────────────────────────
Analyzes the 44 pending meal plan health reviews:
1. Totals and flag distribution
2. Identifies critical clinical red-flags (Kidney/Liver, Pregnancy/Lactating, Under 18, Anaphylaxis, Diabetes, Eating Disorders)
3. Prepares the exact card format for group forwarding to -5592866261
"""

import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
import asyncpg

CRITICAL_RED_FLAGS = {
    "KIDNEY_LIVER_DISEASE": "🔴 Kidney / Liver Disease (Severe metabolic/filtration contraindication)",
    "PREGNANCY_POSTPARTUM_LACTATING": "🔴 Pregnancy / Postpartum / Lactating (High-risk maternal/infant nutrition)",
    "UNDER_18": "🔴 Under 18 (Pediatric client - legal/developmental restriction)",
    "ANAPHYLACTIC_FOOD_ALLERGY": "🔴 Anaphylactic Food Allergy (Life-threatening acute allergy risk)",
    "DIABETES_GLUCOSE_MEDICATION": "🔴 Diabetes / Glucose Medication (Insulin/hypoglycemia clinical risk)",
    "CLINICIAN_PRESCRIBED_DIET": "🔴 Clinician-Prescribed Diet (Active medical prescription conflict)",
}

MANAGEABLE_OR_DIETARY_FLAGS = {
    "EATING_DISORDER_CONCERN": "⚠️ Eating-Disorder Concern (Requires psychological screening / gentle coaching)",
    "SEVERE_GI_CONDITION": "⚠️ Severe GI Symptoms / Disease (IBS/GERD/gastritis tailoring needed)",
    "UNEXPLAINED_WEIGHT_CHANGE": "⚠️ Unexplained Weight Change (Needs baseline calibration)",
    "OTHER_HEALTH_CHANGE": "⚠️ Other Health Change (General lifestyle/medication note)",
}

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    
    rows = await conn.fetch("""
        SELECT hr.id as review_id, hr.intake_id, hr.status, hr.flags, hr.summary, hr.requested_at,
               mi.public_id, mi.user_id, mi.language, mi.answers,
               u.full_name, u.username
        FROM meal_health_reviews hr
        JOIN meal_intakes mi ON mi.id = hr.intake_id
        LEFT JOIN users u ON u.telegram_id = mi.user_id
        WHERE hr.status = 'PENDING'
        ORDER BY hr.requested_at ASC
    """)
    
    print(f"Total Pending Health Reviews: {len(rows)}")
    print("=" * 60)
    
    critical_cases = []
    moderate_cases = []
    
    all_flags_counter = Counter()
    
    for r in rows:
        raw_flags = r["flags"]
        flags = json.loads(raw_flags) if isinstance(raw_flags, str) else (raw_flags or [])
        answers = json.loads(r["answers"]) if isinstance(r["answers"], str) else (r["answers"] or {})
        
        has_critical = any(f in CRITICAL_RED_FLAGS for f in flags)
        
        crit_list = [CRITICAL_RED_FLAGS[f] for f in flags if f in CRITICAL_RED_FLAGS]
        mod_list = [MANAGEABLE_OR_DIETARY_FLAGS[f] for f in flags if f in MANAGEABLE_OR_DIETARY_FLAGS]
        
        case_info = {
            "review_id": r["review_id"],
            "intake_id": r["intake_id"],
            "public_id": r["public_id"],
            "user_id": r["user_id"],
            "full_name": r["full_name"] or "Unknown",
            "username": r["username"] or "",
            "requested_at": r["requested_at"].strftime("%Y-%m-%d %H:%M") if r["requested_at"] else "",
            "flags": flags,
            "critical_flags": crit_list,
            "moderate_flags": mod_list,
            "age": answers.get("age"),
            "gender": answers.get("gender"),
            "weight_kg": answers.get("weight_kg"),
            "height_cm": answers.get("height_cm"),
            "goal": answers.get("primary_goal"),
        }
        
        for f in flags:
            all_flags_counter[f] += 1
            
        if has_critical:
            critical_cases.append(case_info)
        else:
            moderate_cases.append(case_info)
            
    print(f"\nCRITICAL RED FLAGS COUNT : {len(critical_cases)} clients")
    print(f"MODERATE / DIETARY CASES : {len(moderate_cases)} clients")
    print("-" * 60)
    
    print("\nOverall Flag Frequency across the 44 pending reviews:")
    for f, count in all_flags_counter.most_common():
        marker = "🔴 CRITICAL" if f in CRITICAL_RED_FLAGS else "⚠️ MODERATE"
        print(f"  [{marker}] {f:32} : {count} occurrences")
        
    print("\n" + "=" * 60)
    print("DETAIL OF THE CRITICAL RED-FLAG CLIENTS:")
    print("=" * 60)
    for idx, c in enumerate(critical_cases, 1):
        uname = f"@{c['username']}" if c['username'] else "No username"
        print(f"{idx}. {c['full_name']} ({uname}) | Intake #{c['intake_id']} | Requested: {c['requested_at']}")
        print(f"   Age: {c['age']} | Gender: {c['gender']} | Goal: {c['goal']}")
        for cf in c['critical_flags']:
            print(f"   -> {cf}")
        if c['moderate_flags']:
            for mf in c['moderate_flags']:
                print(f"      {mf}")
        print()
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())

