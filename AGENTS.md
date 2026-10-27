# Project Agent Guidelines & Operational Rules

## 1. Mandatory Progress Tracking (`session-tracker.md`)
Every session in this repository **MUST** actively maintain and update `session-tracker.md` at the workspace root:

1. **At the Start of Every Session / Task:**
   - Immediately update the **Current Session Dashboard** in `session-tracker.md`.
   - Set **Active Task**, **Session Started** timestamp, **Status** (`IN PROGRESS`), and **Overall Progress** (`10%`).
   - Populate the **Task Breakdown & Milestones** checklist for the user's prompt.

2. **During the Session (Mid-Progress / Before Long Commands):**
   - After each major step or before launching long-running processes (PDF compilation, batch tests, migrations):
     - Check off completed milestones `[x]`.
     - Update **Current In-Flight Step** with the exact active task.
     - Bump **Overall Progress** percentage (e.g. `30%`, `50%`, `75%`).
     - Update **Last Updated** timestamp.

3. **Upon Task Completion:**
   - Mark **Session Status** as `✅ COMPLETED`.
   - Set **Overall Progress** to `100%`.
   - Update **Recent Session Deliverables** with clickable file links.
   - Append a summary entry to the **Historical Session Log**.

---

## 2. Meal Plan Generation Architecture Rules
- All meal plan generators must produce strictly calibrated 15-page client PDFs via headless Chromium (`html_pdf_renderer.py`).
- Caloric bounds for Yohannes / 3,075 kcal profiles must land in `[2,980, 3,075]` kcal with protein in `[135, 155]` g.
- Orthodox fasting rules (Wed/Fri zero animal products) must be 100% strictly enforced.
- Rice cakes (`C020`) must never exceed 4 cakes (35–40 g) per meal to prevent gastric distension.
- Grocery procurement must contain all 41 commodities with standardized retail packaging (`1 carton 10–12 eggs`, `1 bottle 500ml oil`, `1 fresh loaf sourdough`, etc.).
- Never output raw unstyled markdown text dumps for client deliverable requests.
