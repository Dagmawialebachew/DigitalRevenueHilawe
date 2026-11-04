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
| **Session Status** | 🟡 **IN PROGRESS** |
| **Overall Progress** | [██░░░░░░░░░░░░░░░░░░] 10% |
| **Session Started** | 2026-11-04 21:31:00 (EAT) |
| **Last Updated** | 2026-11-04 21:34:00 (EAT) |
| **Current In-Flight Step** | Querying Order #72 intake, payment status, and generation job state in DB |

---

## 🎯 Task Breakdown & Milestones

### Current Session Tasks

- [ ] **Milestone 1: Order #72 Forensics** — Query DB for Order #72, intake profile, payment status, and meal_generation_jobs row.
- [ ] **Milestone 2: Root Cause Identification** — Pinpoint why generation is stalled at 0% (worker offline, constraint unsolvability, or payload lock).
- [ ] **Milestone 3: Execution & Generation** — Trigger generation pipeline, compile 15-page PDF via Chromium, run quality checks.
- [ ] **Milestone 4: Verification & Delivery** — Deliver meal plan / update order status to review/ready, notify user.

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
else:
    print("Could not find Recent Session Deliverables")

