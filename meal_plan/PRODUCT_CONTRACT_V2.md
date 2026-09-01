# Coach Hilawe Meal Plan V2 Product Contract

**Status:** Draft for product-owner approval  
**Purpose:** This document is the source of truth for the next meal-plan release. Code, pricing, database migrations, tests, review workflow, Mini App copy, and client PDFs must conform to it.

## 1. Product promise

Coach Hilawe sells a personalized, coach-reviewed nutrition programme. It is not a generic recipe list and it must not claim more variety, precision, language support, or clinical certainty than it actually delivers.

Every client receives:

- a dated plan for the purchased duration;
- food portions and practical household measures where they are supported by calibrated data;
- substitutions that preserve the intended nutrition structure;
- a document in the language selected by the client;
- a plan that has passed the applicable automated and coach-review gates.

## 2. Non-negotiable delivery rules

1. A client must never receive a draft, engine metadata, dataset metadata, calibration warning, internal review note, or unapproved artifact.
2. Internal review evidence and the client PDF are separate artifacts. Approving a plan authorizes generating a clean client artifact; it does not authorize forwarding the internal draft.
3. A plan with a blocking nutrition or data-quality failure cannot be approved or delivered. An explicit coach override, if later allowed, must record the reason and reviewer.
4. The delivered filename is client-readable: `{ClientName}_Meal_Plan_{Duration}_Days_V{Version}.pdf`.
5. A plan must state the selected language and contain that language consistently. Mixing English labels and Amharic labels is a defect unless the term is intentionally retained in the approved glossary.

## 3. Duration product contract

| Product | Client promise | Required generated output |
|---|---|---|
| 7-day Meal Plan | Seven individually dated daily menus | Seven daily schedules, a seven-day grocery list, and approved swaps |
| 14-day Meal Plan | Fourteen individually dated daily menus | Fourteen daily schedules and two weekly grocery lists |
| 30-day Meal Plan | A full, date-specific thirty-day programme | Thirty daily schedules, four or five weekly grocery lists, progress/check-in guidance where purchased, and an explicit calendar |

### Repetition policy

Normal meal repetition is allowed when it is intentional, practical, and disclosed. A 30-day plan may reuse foods or recipes, but it must not be represented as a 30-day product when it contains only a seven-day menu with an unexplained loop.

The generator must create a dated schedule for every purchased day. The Mini App and PDF must describe the product as a **full 30-day programme**, never as a "7-day core" to a client.

## 4. Nutrition quality contract

### Automated hard gates

- Daily calorie and protein outcomes must meet the approved tolerance for the client goal.
- Each generated profile supplies a target and a minimum acceptable outcome. The engine must meet both; it must not silently lower the standard for fasting, vegetarian, vegan, or budget-conscious clients.
- Energy is evaluated against the calculated daily target using the approved profile tolerance. Protein is evaluated against both the daily protein target and the profile's minimum acceptable protein floor. Any shortfall outside the profile tolerance is blocking.
- A primary recipe may not appear twice on the same day unless a future approved recipe explicitly marks that use as intentional.
- A seven-day programme may not contain an identical full day twice. Fourteen- and thirty-day programmes may reuse practical foods, but must preserve a documented minimum variety pattern across each week.
- The plan must obey dietary pattern, allergy, disliked-food, fasting, and food-safety constraints.
- Fasting plans must use fasting-safe recipes and must have verified annual fasting-calendar coverage before checkout and generation.
- The generator must apply a digestibility guard: do not stack excessive high-legume/high-fibre meals on the same day without an approved lower-fibre alternative.

### Alternative-specific planning policy

- **Omnivore:** animal-protein recipes are eligible only when they meet the client's selected diet, fasting, health, and preference rules.
- **Vegetarian and vegan:** plant-protein combinations are planned to the same profile standard, not accepted at a lower protein outcome merely because they are plant-based.
- **Fasting, no fish:** use fasting-safe plant recipes with deliberate protein and fibre balancing.
- **Fasting, fish selected:** fish is eligible only when the client explicitly selected it and the applicable fasting rule permits it; it is never assumed by default.
- **Protein powder:** it is an optional ingredient only after the client explicitly states that it is acceptable and available. It is never inserted as a surprise fix for a weak plan.
- **Budget or availability constraints:** alter the eligible food set and portion strategy, not the truthfulness of the macro result. If the target cannot be met practically, the plan remains in review instead of pretending it succeeded.

### Coach-review gates

- recipe calibration status;
- practical portion sizes;
- food availability and budget fit;
- cultural appropriateness;
- special fasting, health, or training constraints;
- any explicit client preference that cannot be solved automatically.

## 5. Recipe and food-data governance

No production nutrition values are changed by ad-hoc SQL edits.

Each recipe requires a versioned calibration record containing:

- ingredients and raw/cooked weights;
- cooking oil and other calorie-bearing additions;
- cooked yield and standard serving size;
- kcal, protein, carbohydrate, fat, fibre, and sodium where available;
- source, owner, verification date, and approval status.

Recipes marked `CALIBRATION_REQUIRED` remain internal review material. They do not become client-ready merely because a PDF rendered successfully.

## 6. Language and content contract

The selected language controls all client-visible content:

- product names and explanations;
- meal and recipe names;
- ingredients, portions, swaps, grocery categories, and instructions;
- Mini App steps, payment copy, notifications, and PDFs.

English is clear international English. Amharic is native client-facing Amharic, reviewed as editorial content rather than literal machine translation.

The data model will provide an approved English and Amharic value for every client-facing food, recipe, template, instruction, and category. A controlled bilingual glossary defines terms intentionally retained in English, such as `kcal` where appropriate.

## 7. Client-document contract

The client PDF is a working daily tool, not a technical report.

Required sections:

1. Cover: client name, programme duration, goal, start/end dates, and coach identity.
2. Quick start: how to use portions, swaps, and fasting instructions.
3. Date-by-date plan: each purchased day has its meals, portions, substitutions, and daily total.
4. Weekly shopping: clear quantities and household-friendly purchase guidance.
5. Progress guidance: only where it is part of the purchased service.

Forbidden sections:

- draft banners;
- database/engine/dataset identifiers;
- internal calibration warnings;
- internal approval status or reviewer notes;
- pages that exist only to expose implementation details.

Design principles: one task at a time, strong daily hierarchy, generous but purposeful whitespace, no orphaned content page, readable on a phone, and useful while shopping or cooking.

## 8. Pricing and Mini App contract

The duration choice must explain the delivered value before payment:

- **7 days:** one full personalised week.
- **14 days:** two dated personalised weeks with more variety.
- **30 days:** a complete dated month, weekly shopping structure, and the selected follow-up service where purchased.

Price cards must not describe the 14- or 30-day product as a rotation of a seven-day core. The checkout summary repeats the number of dated daily menus included.

## 9. Required acceptance scenarios

Before release, the system must prove the following:

1. A 30-day client receives 30 dated daily schedules; a 7-day client receives seven.
2. A protein-deficient fasting day blocks approval and exposes the reason only to the reviewer.
3. A day cannot use the same primary recipe for breakfast and dinner without an explicit approved exception.
4. An Amharic client receives no accidental English recipe, ingredient, or instruction copy.
5. An English client receives no accidental Amharic-only copy.
6. The delivered PDF contains neither `DRAFT` nor engine/dataset/calibration metadata.
7. The filename follows the client-readable naming rule.
8. A 30-day grocery plan is clearly organized by weekly purchase period.

## 10. Product-owner decisions required before implementation

1. **Nutrition tolerances:** configured as part of the reviewed nutrition profile, not as one global shortcut. Fasting, vegetarian, vegan, and budget plans keep their declared target and minimum floor.
2. **Supplements and fish:** powder is opt-in; fish is opt-in and calendar/policy constrained.
3. **Variety:** no same-day primary-recipe duplication; no identical full day in a seven-day programme; a weekly variety rule applies to longer programmes.
4. **Coach override:** permitted only for practical-review issues and requires a reason plus reviewer identity. It may never override allergies, dietary/fasting violations, missing fasting-calendar coverage, or an incomplete intake.
5. **Amharic ownership:** Coach Hilawe is accountable for final language approval. A fluent native Amharic reviewer approves the glossary and each client-visible content batch before release.
6. **Product naming/inclusions:** retain the 7-, 14-, and 30-day products, with the duration promises defined in section 3.

## 11. Phase 1 implementation boundary

Phase 1 implements only the delivery hotfix and contract-enforcement foundation:

- separate internal review and client artifacts;
- approved-only client PDF delivery;
- client-readable filenames;
- removal of internal last/review page and draft language from client PDFs;
- blocking handling for existing practical and recipe-calibration warnings;
- contract tests for those rules.

It does not recalibrate recipes, rewrite all translations, or claim a true 30-day schedule. Those are Phase 2 and Phase 3 work after the product-owner decisions above are approved.
