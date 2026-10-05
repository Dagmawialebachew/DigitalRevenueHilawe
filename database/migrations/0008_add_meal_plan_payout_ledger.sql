-- Migration 0008: Add Meal Plan revenue stream and 100k milestone ledger columns to payout_history
-- Stream C Agreement:
--   • Initial Stage (< 100,000 ETB cumulative gross): 60% Coach Hilawe / 40% Dagmawi
--   • Mature Stage (>= 100,000 ETB cumulative gross): 65% Coach Hilawe / 35% Dagmawi

ALTER TABLE payout_history
ADD COLUMN IF NOT EXISTS meal_plan_gross NUMERIC(12, 2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS meal_plan_stage VARCHAR(50) DEFAULT 'initial_40_60',
ADD COLUMN IF NOT EXISTS meal_plan_cumulative_at_payout NUMERIC(12, 2) DEFAULT 0;
