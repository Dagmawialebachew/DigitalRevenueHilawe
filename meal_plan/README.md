# `meal_plan/`

This package is the isolated backend domain for Coach Hilawe's personalized meal-plan product.

## Phase 0 rule

Nothing in this package is wired into `bot.py`, the existing workout-plan handlers, payment tables, or startup lifecycle yet. `MEAL_PLAN_ENABLED` defaults to `false`.

That is deliberate: Phase 0 establishes names, boundaries, documentation, and migration tooling without changing production behavior for the existing 5k+ user system.

## Planned module boundaries

Later phases will add focused modules beneath this package for:

- Telegram entry/country gate and Mini App authentication;
- intake/autosave and health review;
- pricing/orders/payments;
- Hilawe dataset import and deterministic generation;
- DOCX/PDF rendering;
- Telegram review/approval/manual replacement;
- follow-up, check-ins, revisions, and renewal;
- background generation/document jobs.

Do not move existing workout-plan code into this package. Shared services may be extracted only when a phase explicitly tests the existing workout flow for regressions.
