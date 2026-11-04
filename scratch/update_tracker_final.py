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
    '| **Last Updated** | 2026-11-03 13:52:00 (EAT) |',
    '| **Last Updated** | 2026-11-03 14:00:00 (EAT) |'
)
text = text.replace(
    '| **Current In-Flight Step** | Inspecting broadcast.py architecture & designing personalized Addis Amharic copy |',
    '| **Current In-Flight Step** | Retargeting engine implemented, verified via dry-run, and wired into onboarding handlers |'
)

text = text.replace(
    '- [ ] **Milestone 1: Existing Broadcast Architecture Inspection**',
    '- [x] **Milestone 1: Existing Broadcast Architecture Inspection**'
)
text = text.replace(
    '- [ ] **Milestone 2: Authentic Coach Hilawe Addis Persona Copywriting**',
    '- [x] **Milestone 2: Authentic Coach Hilawe Addis Persona Copywriting**'
)
text = text.replace(
    '- [ ] **Milestone 3: Dynamic 1-Click Resume & Full Price Bridge**',
    '- [x] **Milestone 3: Dynamic 1-Click Resume & Full Price Bridge**'
)
text = text.replace(
    '- [ ] **Milestone 4: Retargeting Engine Implementation / Script**',
    '- [x] **Milestone 4: Retargeting Engine Implementation / Script**'
)

new_deliv = """| **Full-Price Incomplete Retargeting Engine** | CLI & Telegram broadcast engine targeting 440 drop-offs with Addis native voice | [retarget_incomplete_onboarding.py](file:///d:/The%20hobby%202/DigitalRevenueHilawe/scheduler/retarget_incomplete_onboarding.py) |
| **Incomplete Users CSV Ledger**"""

text = text.replace('| **Incomplete Users CSV Ledger**', new_deliv)

history = """### Session: 2026-11-03 — Personalized Native Addis Retargeting for Incomplete Users (Full Price 949 ETB)

* **Goal:** Create a high-converting, deeply personalized retargeting engine in authentic Coach Hilawe Addis native Amharic, targeting users who abandoned onboarding, selling the 8-Week Blueprint at full price (949 ETB).
* **Key Implementations:**
  1. **Addis Persona Copywriting (`scheduler/retarget_incomplete_onboarding.py`):**
     - Personalized first-name greeting (`ሰላም {first_name}` or `ሰላም ወዳጄ`).
     - Directly calls out their exact action (*"ባለፈው እኮ ቦት ላይ መጥተህ ቋንቋ መርጠህ መሃል ላይ ቀረህ... ምነው ፈራህ እንዴ? 😄"*).
     - Unapologetic full price anchor: strictly **949 ETB** (anchored against a single Addis lunch/macchiato, zero discount apology).
     - 82.2% Amharic / 17.8% English split handled dynamically.
  2. **1-Tap Direct Checkout & Assessment Resume Buttons:**
     - `👨 የወንዶች 8-ሳምንት ፕሮግራም (949 ብር)` ➔ triggers `pay_4` directly into CBE/BOA payment invoice.
     - `👩 የሴቶች ቅርጽና ቦርጭ ማጥፊያ (949 ብር)` ➔ triggers `pay_8` directly into CBE/BOA payment invoice.
     - `🎯 ጥያቄዎቹን ጨርሼ ፕሮግራሜን ልይ` ➔ triggers `retarget_resume` to complete remaining questions.
  3. **Onboarding Handler Fortification (`handlers/onboarding.py`):**
     - Added `process_retarget_resume` to re-enter gender selection seamlessly.
     - Added wildcard `F.data.startswith('gender_')` with DB fallback so buttons work even if user's FSM state expired.
  4. **CLI Control:** Added `--dry-run`, `--test-admin`, and `--launch` modes with 0.06s sleep and Semaphore=20 rate-limiting.

"""

text = text.replace('## 📜 Historical Session Log\n\n', '## 📜 Historical Session Log\n\n' + history)

with open('session-tracker.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated session-tracker.md successfully!")

