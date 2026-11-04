with open('session-tracker.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '| **Session Status** | 🔄 **IN PROGRESS** |',
    '| **Session Status** | ✅ **COMPLETED** |'
)
text = text.replace(
    '| **Overall Progress** | [██████████████░░░░░░] 70% |',
    '| **Overall Progress** | [████████████████████] 100% |'
)
text = text.replace(
    '| **Last Updated** | 2026-11-03 14:19:00 (EAT) |',
    '| **Last Updated** | 2026-11-03 14:21:00 (EAT) |'
)
text = text.replace(
    '| **Current In-Flight Step** | Executing live broadcast dispatch to all 440 incomplete users & sending Telegram report to admin |',
    '| **Current In-Flight Step** | Broadcast dispatched to 440 targets (338 delivered) & Telegram execution report sent to admin |'
)

text = text.replace(
    '- [ ] **Milestone 2: Live Broadcast Execution**',
    '- [x] **Milestone 2: Live Broadcast Execution**'
)
text = text.replace(
    '- [ ] **Milestone 3: Verification & Admin Confirmation**',
    '- [x] **Milestone 3: Verification & Admin Confirmation**'
)

history = """### Session: 2026-11-03 — Live Onboarding Completion Broadcast & Telegram Admin Report

* **Goal:** Broadcast the revised multi-gender Coach Hilawe onboarding recovery message to all 440 incomplete users and deliver the full completion report to Admin `1131741322` in Telegram.
* **Execution Results:**
  1. **Total Targets:** 440 users.
  2. **Successfully Delivered:** 338 users (76.8% delivery rate).
  3. **Blocked Bot:** 101 users (handled gracefully without interruption).
  4. **Failed / Bad Format:** 1 user.
  5. **Admin Telegram Report:** Successfully delivered live summary card to Coach / Admin ID `1131741322`.
  6. **Interactive Action:** All 338 delivered users now have the active inline button `🎯 የሰውነት ምዘናዎን ይጨርሱ` waiting in their Telegram chat.

"""

text = text.replace('## 📜 Historical Session Log\n\n', '## 📜 Historical Session Log\n\n' + history)

with open('session-tracker.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated session-tracker.md to completed!")

