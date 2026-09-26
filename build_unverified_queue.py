import json
import csv
import os
import shutil
from pathlib import Path

export_dir = Path("payments_export")
json_path = export_dir / "scanned_transactions.json"
queue_dir = export_dir / "UNVERIFIED_REVIEW_QUEUE"
csv_path = export_dir / "UNVERIFIED_TRANSACTIONS.csv"

queue_dir.mkdir(parents=True, exist_ok=True)

with open(json_path, "r", encoding="utf-8") as f:
    records = json.load(f)

unverified = [r for r in records if not r.get("is_verified")]
print(f"Found {len(unverified)} unverified transactions.")

# Map filename -> actual file path inside payments_export/
file_map = {}
for root, dirs, files in os.walk(export_dir):
    if "UNVERIFIED_REVIEW_QUEUE" in root:
        continue
    for f in files:
        if f.endswith(".jpg") or f.endswith(".png") or f.endswith(".jpeg"):
            file_map[f] = Path(root) / f

copied_count = 0
unverified_rows = []

for idx, r in enumerate(unverified):
    fname = r.get("screenshot_filename")
    src_path = file_map.get(fname)
    dest_name = f"REVIEW_{idx+1:02d}_{fname}"
    dest_path = queue_dir / dest_name

    if src_path and src_path.exists():
        shutil.copy2(src_path, dest_path)
        copied_count += 1
        rel_link = str(dest_path.relative_to(export_dir.parent))
    else:
        rel_link = "FILE_NOT_FOUND"

    reason = r.get("flagged_reason")
    if not reason:
        if r.get("txn_id") == "Not Detected":
            reason = "OCR could not read transaction ID from image"
        elif "Lag" in str(r.get("bank_status")) or "Timeout" in str(r.get("bank_status")):
            reason = "Bank API gateway timeout (502 / lag)"
        elif r.get("bank_status") == "Unverified":
            reason = "Veritas could not conclusively verify with bank"
        else:
            reason = str(r.get("bank_status", "Manual check required"))

    unverified_rows.append({
        "Review_Num": idx + 1,
        "Payment_ID": r.get("payment_id"),
        "Stream": "Sales" if "sale" in str(r.get("stream")).lower() else "Club",
        "Date": r.get("created_at"),
        "DB_Amount_ETB": r.get("amount_db"),
        "User_Name": r.get("full_name"),
        "Username": r.get("username"),
        "Telegram_ID": r.get("user_id"),
        "Extracted_Txn_ID": r.get("txn_id"),
        "Provider": r.get("provider"),
        "AI_Status": r.get("bank_status"),
        "Review_Reason": reason,
        "Queue_Filename": dest_name,
    })

# Save CSV
fieldnames = [
    "Review_Num", "Payment_ID", "Stream", "Date", "DB_Amount_ETB",
    "User_Name", "Username", "Telegram_ID", "Extracted_Txn_ID",
    "Provider", "AI_Status", "Review_Reason", "Queue_Filename"
]
with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(unverified_rows)

print(f"Copied {copied_count} screenshot(s) to: {queue_dir}")
print(f"Saved Excel review sheet to: {csv_path}")

# Print summary to console
print("\n" + "=" * 80)
print("UNVERIFIED REVIEW QUEUE SUMMARY")
print("=" * 80)
for row in unverified_rows:
    print(f"#{row['Review_Num']:02d} | PID {row['Payment_ID']:<4} | {row['Stream']:<5} | {row['Date']} | {row['DB_Amount_ETB']:>6.2f} ETB | {row['Extracted_Txn_ID']:<14} | {row['Review_Reason']}")
print("=" * 80)
