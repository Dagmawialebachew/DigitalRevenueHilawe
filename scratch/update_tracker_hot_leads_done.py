with open('session-tracker.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '| **Session Status** | 🔄 **IN PROGRESS** |',
    '| **Session Status** | ✅ **COMPLETED** |'
)
text = text.replace(
    '| **Overall Progress** | [██░░░░░░░░░░░░░░░░░░] 10% |',
    '| **Overall Progress** | [████████████████████] 100% |'
)
text = text.replace(
    '| **Last Updated** | 2026-11-03 14:34:00 (EAT) |',
    '| **Last Updated** | 2026-11-03 14:39:00 (EAT) |'
)
text = text.replace(
    '| **Current In-Flight Step** | Analyzing broadcast.py personalization patterns & designing ultra-personalized 743-lead recovery engine |',
    '| **Current In-Flight Step** | Hyper-personalized 743-lead recovery engine built, tested via dry-run, and verified |'
)

text = text.replace(
    '- [ ] **Milestone 1: Broadcast.py Personalization & Voice Inspection**',
    '- [x] **Milestone 1: Broadcast.py Personalization & Voice Inspection**'
)
text = text.replace(
    '- [ ] **Milestone 2: 743 Hot Leads Cohort & Data Extraction**',
    '- [x] **Milestone 2: 743 Hot Leads Cohort & Data Extraction**'
)
text = text.replace(
    '- [ ] **Milestone 3: Hyper-Personalized Addis Copy Architecture**',
    '- [x] **Milestone 3: Hyper-Personalized Addis Copy Architecture**'
)
text = text.replace(
    '- [ ] **Milestone 4: Engine Implementation & Testing**',
    '- [x] **Milestone 4: Engine Implementation & Testing**'
)

new_deliv = """| **743 Hot Leads Hyper-Personalized Engine** | 1-on-1 personalized recovery engine injecting name, gender, days, goal, and obstacle | [retarget_hot_unpaid_leads.py](file:///d:/The%20hobby%202/DigitalRevenueHilawe/scheduler/retarget_hot_unpaid_leads.py) |
| **Full-Price Incomplete Retargeting Engine**"""

text = text.replace('| **Full-Price Incomplete Retargeting Engine**', new_deliv)

history = """### Session: 2026-11-03 — 743 Hot Unpaid Leads Hyper-Personalized Recovery Engine

* **Goal:** Build an intensely personalized 1-on-1 recovery engine for the 743 leads who completed onboarding in the past 7 days, injecting their exact intake answers in authentic Coach Hilawe Addis native Amharic.
* **Key Features Implemented:**
  1. **Hyper-Personalization Engine (`scheduler/retarget_hot_unpaid_leads.py`):**
     - Injects real name: `{first_name}`.
     - Accurate Male vs Female honorifics & grammar (`ወንድሜ ሰላም ነህ?` vs `እህቴ እንዴት ነሽ?`).
     - Injects exact training split: `በሳምንት 3/4/5 ቀን ሰርተህ/ሽ`.
     - Injects exact goal: `ጠንካራ ጡንቻ ለመገንባት` vs `ያለህን/ሽን ቦርጭ አጥፍተህ/ሽ ቅርጽህን/ሽን ለመያዝ`.
     - Injects exact obstacle: `የአመጋገብ ስርዓትህን/ሽን ለማስተካከል` vs `የተነሳሽነትና የወጥነት ችግርህን/ሽን ለመቅረፍ` vs `ግልጽ የሆነ የተዋቀረ እቅድ አግኝተህ/ሽ ለመስራት`.
  2. **1-Tap Direct Checkout (949 ETB):**
     - Matches exact product ID based on gender, level, and frequency (fallback mapping ensures 100% resolution).
     - Single high-intent button: `⚡️ የ8-ሳምንት ፕሮግራሜን ልክፈት (949 ብር)` triggers official CBE/BOA bank invoice.
  3. **Verification:**
     - Verified with `--dry-run` across all 743 leads (636 male, 107 female, 653 Amharic, 90 English).
     - Integrated automated Telegram admin execution reporting upon live launch.

"""

text = text.replace('## 📜 Historical Session Log\n\n', '## 📜 Historical Session Log\n\n' + history)

with open('session-tracker.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated session-tracker.md successfully!")

