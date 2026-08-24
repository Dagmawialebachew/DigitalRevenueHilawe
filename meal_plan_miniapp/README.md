# Hilawe Meal Plan Mini App

React + TypeScript Telegram Mini App frontend.

Current local implementation: **Phase 4**.

Implemented:
- Telegram initData bootstrap/auth contract
- AM/EN language switch
- country fallback gate
- premium guided Phase 3 assessment with server autosave/resume
- Phase 4 health-review hold state
- nutrition-profile presentation
- 3/4/5 meals/day configuration
- earliest-tomorrow start date
- 7/14/30 duration selection
- 30-day Meal Plan + Follow-Up selection
- DB/manual pricing preview

Not implemented yet:
- payment/proof submission
- meal generation
- final DOCX/PDF
- final review/delivery
- weekly follow-up engine

## Local build

```powershell
npm install
npm run build
```

Set `VITE_MEAL_API_BASE_URL` in a local frontend environment file to the public HTTPS tunnel/API used by the demo bot. Do not commit real secrets; Telegram bot secrets never belong in this frontend.

## Phase 5 payment demo

The Mini App can now create an isolated Meal Plan order and payment attempt. Payment instructions use the existing CBE and Bank of Abyssinia environment values. Receipt screenshots are submitted in the Telegram bot and routed through the existing verification helpers without touching legacy workout-payment rows.

For USD-priced regions, `MEAL_PLAN_USD_SETTLEMENT_MODE=USD` keeps the settlement in USD. If the business intentionally wants ETB settlement, set it to `ETB` and configure `MEAL_PLAN_USD_TO_ETB_RATE`; no exchange rate is invented by the code.
