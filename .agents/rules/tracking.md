# Session Progress Tracking Rule

Every agent session in this repository must maintain `session-tracker.md` at the workspace root (`d:\The hobby 2\DigitalRevenueHilawe\session-tracker.md`).

### Protocol:
1. **Initialize on First Tool Call:** On receiving a user prompt, update `session-tracker.md` with the active task, timestamp, checklist of steps, and `IN PROGRESS` status.
2. **Intermediate Updates:** Update `session-tracker.md` after completing each sub-task or before launching any command that runs for >1 minute, adjusting progress percentage and checking off milestones.
3. **Completion:** Mark `session-tracker.md` as `COMPLETED` at 100% with direct clickable links to all generated files and artifacts.
