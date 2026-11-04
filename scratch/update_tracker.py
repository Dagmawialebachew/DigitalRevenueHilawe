import re

with open('session-tracker.md', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\r\n', '\n')

old_part = """| Metric | Status / Value |
| --- | --- |
| **Active Task / Request** | Phase 6 Execution: Verification Suite, PDF Tooling & Production Launch |
| **Session Status** | ✅ **COMPLETED** |
| **Overall Progress** | [████████████████████] 100% |
| **Session Started** | 2026-11-02 12:15:00 (EAT) |
| **Last Updated** | 2026-11-02 14:42:00 (EAT) |
| **Current In-Flight Step** | All buttons trimmed to punchy, compact mobile-friendly labels for both user and admin |"""

new_part = """| Metric | Status / Value |
| --- | --- |
| **Active Task / Request** | Onboarding Drop-off & Incomplete User Statistics Analysis |
| **Session Status** | 🔄 **IN PROGRESS** |
| **Overall Progress** | [██░░░░░░░░░░░░░░░░░░] 10% |
| **Session Started** | 2026-11-03 13:30:00 (EAT) |
| **Last Updated** | 2026-11-03 13:30:00 (EAT) |
| **Current In-Flight Step** | Investigating database models and onboarding states |"""

new_milestones = """### Current Session Tasks

- [ ] **Milestone 1: Database & Onboarding Architecture Inspection** — Identify User models, onboarding steps, state tracking, and DB connection.
- [ ] **Milestone 2: Data Extraction & Funnel Drop-off Querying** — Query the database for total users, onboarding status breakdown, and drop-off points.
- [ ] **Milestone 3: In-Depth Statistics & Cohort Analysis** — Group users by drop-off step, date cohorts, activity, and identify patterns.
- [ ] **Milestone 4: Formulate Human-Friendly Report & Insights** — Present clean, intuitive statistics and actionable recommendations in simple, clear language ("Stay Easy Bro")."""

content = content.replace(old_part, new_part)

milestones_pattern = r'### Current Session Tasks\n\n- \[x\] \*\*Milestone 1: Decoupling Audit.*?(?=\n---\n\n## 📦 Recent Session Deliverables)'
content = re.sub(milestones_pattern, new_milestones, content, flags=re.DOTALL)

with open('session-tracker.md', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print("session-tracker.md updated successfully")

