with open('session-tracker.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '| **Active Task / Request** | Native Addis Amharic Personalized Retargeting for Incomplete Users (Full Price) |',
    '| **Active Task / Request** | Live Onboarding Completion Broadcast & Telegram Admin Report Dispatch |'
)
text = text.replace(
    '| **Session Status** | ✅ **COMPLETED** |',
    '| **Session Status** | 🔄 **IN PROGRESS** |'
)
text = text.replace(
    '| **Overall Progress** | [████████████████████] 100% |',
    '| **Overall Progress** | [██░░░░░░░░░░░░░░░░░░] 10% |'
)
text = text.replace(
    '| **Last Updated** | 2026-11-03 14:11:00 (EAT) |',
    '| **Last Updated** | 2026-11-03 14:19:00 (EAT) |'
)
text = text.replace(
    '| **Current In-Flight Step** | Revised retargeting engine verified and ready for launch |',
    '| **Current In-Flight Step** | Enhancing broadcast script to send Telegram admin report and executing live dispatch |'
)

new_milestones = """### Current Session Tasks

- [ ] **Milestone 1: Admin Telegram Reporting Integration** — Wire automated post-broadcast report delivery to `ADMIN_IDS` in `scheduler/retarget_incomplete_onboarding.py`.
- [ ] **Milestone 2: Live Broadcast Execution** — Run the live broadcast across all 440 incomplete users with paced concurrency & error handling.
- [ ] **Milestone 3: Verification & Admin Confirmation** — Confirm all deliveries, record statistics, and verify report received in admin's Telegram chat."""

import re
pattern = r'### Current Session Tasks.*?(?=\n---\n\n## 📦 Recent Session Deliverables)'
text = re.sub(pattern, new_milestones, text, flags=re.DOTALL)

with open('session-tracker.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated session-tracker.md for broadcast launch")

