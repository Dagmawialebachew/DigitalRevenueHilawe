import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

with open('session-tracker.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_header = """# ⏱️ Active Session & Progress Tracker

> **Notice:** This document is automatically maintained and updated during every working session. If a session is long or multi-phased, inspect this file at any time to see the exact current step, completed milestones, and remaining work.

---

## 📊 Current Session Dashboard

| Metric | Status / Value |
| --- | --- |
| **Active Task / Request** | Investigating & Resolving Stuck Meal Plan (Order #72 Approved by Dagmaros) |
| **Session Status** | ✅ **COMPLETED** |
| **Overall Progress** | [████████████████████] 100% |
| **Session Started** | 2026-11-04 21:31:00 (EAT) |
| **Last Updated** | 2026-11-04 22:37:00 (EAT) |
| **Current In-Flight Step** | Order #72 15-page PDF compiled, verified, delivered to Coach Review Group (-5592866261), order state = REVIEW_PENDING |

---

## 🎯 Task Breakdown & Milestones

### Current Session Tasks

- [x] **Milestone 1: Order #72 Forensics** — Identified PostgreSQL check constraint failure (`CheckViolationError` on stage `AI_COACH_REVIEW`).
- [x] **Milestone 2: Database Schema Fix** — Altered `meal_generation_jobs_stage_check` on Neon PostgreSQL to include `AI_COACH_REVIEW` and `FAILED`.
- [x] **Milestone 3: End-to-End Pipeline Execution** — Executed full 9-step generation pipeline (food matching, 7-day schedule, quality check, AI Coach review, grocery list, and 15-page PDF rendering via Chromium).
- [x] **Milestone 4: Deliverables & Handoff** — Stored artifacts in DB, uploaded certified PDF and DOCX to Telegram, dispatched review card to Coach Review Group (`-5592866261`), moved order state to `REVIEW_PENDING`.

---
"""

# Find where "## 📦 Recent Session Deliverables" starts
split_idx = -1
for i, line in enumerate(lines):
    if "Recent Session Deliverables" in line:
        split_idx = i
        break

if split_idx != -1:
    rest = "".join(lines[split_idx:])
    final_content = new_header + "\n## 📦 " + rest
    with open('session-tracker.md', 'w', encoding='utf-8') as f:
        f.write(final_content)
    print("session-tracker.md updated successfully!")

