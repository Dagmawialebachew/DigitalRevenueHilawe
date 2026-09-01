-- Migration 0004: Bilingual Content and Recipe Calibration Foundation
-- Additive only. Supports verified English + Amharic content and recipe calibration metadata.

ALTER TABLE nutrition_foods ADD COLUMN IF NOT EXISTS food_name_en TEXT;
ALTER TABLE nutrition_foods ADD COLUMN IF NOT EXISTS food_name_am TEXT;
ALTER TABLE nutrition_foods ADD COLUMN IF NOT EXISTS category_am TEXT;

ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS recipe_name_en TEXT;
ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS recipe_name_am TEXT;
ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS method_am TEXT;
ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS ingredients_summary_am TEXT;
ALTER TABLE nutrition_recipes ADD COLUMN IF NOT EXISTS calibration_data JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE nutrition_recipe_ingredients ADD COLUMN IF NOT EXISTS ingredient_name_am TEXT;
ALTER TABLE nutrition_recipe_ingredients ADD COLUMN IF NOT EXISTS prep_note_am TEXT;

ALTER TABLE nutrition_templates ADD COLUMN IF NOT EXISTS meal_name_am TEXT;
