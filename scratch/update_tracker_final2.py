with open('session-tracker.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '| **Session Status** | 🔄 **IN PROGRESS** |',
    '| **Session Status** | ✅ **COMPLETED** |'
)
text = text.replace(
    '| **Overall Progress** | [████████████░░░░░░░░] 60% |',
    '| **Overall Progress** | [████████████████████] 100% |'
)
text = text.replace(
    '| **Last Updated** | 2026-11-03 14:08:00 (EAT) |',
    '| **Last Updated** | 2026-11-03 14:11:00 (EAT) |'
)
text = text.replace(
    '| **Current In-Flight Step** | Revising retargeting copy: multi-gender respectful, 380k community, 1700+ buyers, pure onboarding completion |',
    '| **Current In-Flight Step** | Revised retargeting engine verified and ready for launch |'
)

with open('session-tracker.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated session-tracker.md successfully!")

