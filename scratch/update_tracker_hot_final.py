with open('session-tracker.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '| **Session Status** | 🔄 **IN PROGRESS** |',
    '| **Session Status** | ✅ **COMPLETED** |'
)
text = text.replace(
    '| **Overall Progress** | [██████████░░░░░░░░░░] 50% |',
    '| **Overall Progress** | [████████████████████] 100% |'
)
text = text.replace(
    '| **Last Updated** | 2026-11-03 14:41:00 (EAT) |',
    '| **Last Updated** | 2026-11-03 14:44:00 (EAT) |'
)
text = text.replace(
    '| **Current In-Flight Step** | Launching live broadcast dispatch to all 743 hot leads and delivering Telegram admin report |',
    '| **Current In-Flight Step** | Dispatched to 743 hot leads (640 delivered, 0 failures) & Telegram report sent to admin |'
)

text = text.replace(
    '- [ ] **Milestone 3: Live Broadcast Dispatch to 743 Leads**',
    '- [x] **Milestone 3: Live Broadcast Dispatch to 743 Leads**'
)
text = text.replace(
    '- [ ] **Milestone 4: Telegram Admin Report Delivery**',
    '- [x] **Milestone 4: Telegram Admin Report Delivery**'
)

history = """### Session: 2026-11-03 — Live Dispatch: 743 Hot Unpaid Leads Recovery & Admin Report

* **Goal:** Broadcast the hyper-personalized Coach Hilawe 1-on-1 recovery message to the 743 fresh unpaid leads from the past 7 days, injecting their exact intake parameters, and send the delivery report to Admin `1131741322` on Telegram.
* **Execution Results:**
  1. **Total Queue:** 743 users.
  2. **Delivered:** **640 users** (86.1% live delivery rate).
  3. **Blocked:** 103 users.
  4. **Failed:** **0 users** (100% fault-tolerant delivery with zero entity parse drop-offs).
  5. **Admin Telegram Report:** Successfully sent live execution report to Coach / Admin ID `1131741322`.
  6. **Cumulative Day Impact:** 978 active clients (338 incomplete + 640 hot leads) now have direct 1-tap full-price 949 ETB checkout & assessment prompts active in their Telegram chats.

"""

text = text.replace('## 📜 Historical Session Log\n\n', '## 📜 Historical Session Log\n\n' + history)

with open('session-tracker.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated session-tracker.md to completed!")

