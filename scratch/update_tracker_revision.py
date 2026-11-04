with open('session-tracker.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '| **Session Status** | ✅ **COMPLETED** |',
    '| **Session Status** | 🔄 **IN PROGRESS** |'
)
text = text.replace(
    '| **Overall Progress** | [████████████████████] 100% |',
    '| **Overall Progress** | [████████████░░░░░░░░] 60% |'
)
text = text.replace(
    '| **Last Updated** | 2026-11-03 14:00:00 (EAT) |',
    '| **Last Updated** | 2026-11-03 14:08:00 (EAT) |'
)
text = text.replace(
    '| **Current In-Flight Step** | Retargeting engine implemented, verified via dry-run, and wired into onboarding handlers |',
    '| **Current In-Flight Step** | Revising retargeting copy: multi-gender respectful, 380k community, 1700+ buyers, pure onboarding completion |'
)

with open('session-tracker.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated session-tracker.md")

