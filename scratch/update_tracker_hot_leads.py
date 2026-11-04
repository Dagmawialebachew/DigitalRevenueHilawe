import re

with open('session-tracker.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '| **Active Task / Request** | Live Onboarding Completion Broadcast & Telegram Admin Report Dispatch |',
    '| **Active Task / Request** | High-Converting Hot Leads (743 Users) Recovery Engine in Coach Hilawe Native Addis Voice |'
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
    '| **Last Updated** | 2026-11-03 14:21:00 (EAT) |',
    '| **Last Updated** | 2026-11-03 14:34:00 (EAT) |'
)
text = text.replace(
    '| **Current In-Flight Step** | Answered inquiry on zero-click /start drop-offs and database persistence boundary |',
    '| **Current In-Flight Step** | Analyzing broadcast.py personalization patterns & designing ultra-personalized 743-lead recovery engine |'
)

new_milestones = """### Current Session Tasks

- [ ] **Milestone 1: Broadcast.py Personalization & Voice Inspection** — Study `scheduler/broadcast.py` for exact Addis phrasing, psychological triggers, and profile card hooks.
- [ ] **Milestone 2: 743 Hot Leads Cohort & Data Extraction** — Query the 743 users for goal, level, gender, frequency, obstacle, and product mapping.
- [ ] **Milestone 3: Hyper-Personalized Addis Copy Architecture** — Build dynamic message renderer injecting name, exact training split, goal, and obstacle in authentic Coach Hilawe voice.
- [ ] **Milestone 4: Engine Implementation & Testing** — Build `scheduler/retarget_hot_unpaid_leads.py` with dry-run, admin preview test, and live dispatch."""

pattern = r'### Current Session Tasks.*?(?=\n---\n\n## 📦 Recent Session Deliverables)'
text = re.sub(pattern, new_milestones, text, flags=re.DOTALL)

with open('session-tracker.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated session-tracker.md for 743 hot leads recovery successfully!")

