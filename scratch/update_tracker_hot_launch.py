with open('session-tracker.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '| **Active Task / Request** | High-Converting Hot Leads (743 Users) Recovery Engine in Coach Hilawe Native Addis Voice |',
    '| **Active Task / Request** | Live Dispatch: 743 Hot Unpaid Leads Recovery & Admin Telegram Report |'
)
text = text.replace(
    '| **Session Status** | ✅ **COMPLETED** |',
    '| **Session Status** | 🔄 **IN PROGRESS** |'
)
text = text.replace(
    '| **Overall Progress** | [████████████████████] 100% |',
    '| **Overall Progress** | [██████████░░░░░░░░░░] 50% |'
)
text = text.replace(
    '| **Last Updated** | 2026-11-03 14:39:00 (EAT) |',
    '| **Last Updated** | 2026-11-03 14:41:00 (EAT) |'
)
text = text.replace(
    '| **Current In-Flight Step** | Hyper-personalized 743-lead recovery engine built, tested via dry-run, and verified |',
    '| **Current In-Flight Step** | Launching live broadcast dispatch to all 743 hot leads and delivering Telegram admin report |'
)

new_milestones = """### Current Session Tasks

- [x] **Milestone 1: 743 Hot Leads Engine Build & Data Verification** — Built dynamic 1-on-1 personalization injecting name, gender, days, goal, and obstacle.
- [x] **Milestone 2: HTML Escaping & Fallback Hardening** — Fortified delivery with HTML entity escaping and auto-fallback retry to guarantee zero formatting dropped packets.
- [ ] **Milestone 3: Live Broadcast Dispatch to 743 Leads** — Execute concurrent live send (Semaphore=20, 0.06s pacing).
- [ ] **Milestone 4: Telegram Admin Report Delivery** — Deliver live execution summary report directly to admin chat (`1131741322`)."""

import re
pattern = r'### Current Session Tasks.*?(?=\n---\n\n## 📦 Recent Session Deliverables)'
text = re.sub(pattern, new_milestones, text, flags=re.DOTALL)

with open('session-tracker.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated session-tracker.md for hot leads launch!")

