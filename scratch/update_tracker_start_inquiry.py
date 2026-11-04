with open('session-tracker.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '| **Last Updated** | 2026-11-03 14:21:00 (EAT) |',
    '| **Last Updated** | 2026-11-03 14:23:00 (EAT) |'
)
text = text.replace(
    '| **Current In-Flight Step** | Broadcast dispatched to 440 targets (338 delivered) & Telegram execution report sent to admin |',
    '| **Current In-Flight Step** | Answered inquiry on zero-click /start drop-offs and database persistence boundary |'
)

history = """### Session: 2026-11-03 — Pre-Language /start Drop-off Investigation

* **Question:** Can we get the exact count of users who pressed `/start` but bounced before even tapping English/Amharic?
* **Finding:** In `handlers/onboarding.py`, `cmd_start` only dispatches the welcome photo in-memory. Database insertion occurs strictly on callback `process_language`. Users who never tapped a language button left no database footprint in PostgreSQL, making historical pre-click counts untrackable without an earlier telemetry hook.

"""

text = text.replace('## 📜 Historical Session Log\n\n', '## 📜 Historical Session Log\n\n' + history)

with open('session-tracker.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated session-tracker.md successfully!")

