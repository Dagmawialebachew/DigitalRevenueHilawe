-- Migration 0005: Neon data cleanup and migration-history repair
--
-- This migration records the fact that the manual naming cleanup was already applied
-- directly in the Neon SQL editor for Coach Hilawe / Amharic strings.
-- The SQL below is intentionally idempotent and safe to re-run.
UPDATE nutrition_foods
SET    food_name_en = COALESCE (food_name_en, food_name_en),
       food_name_am = COALESCE (food_name_am, food_name_am)
WHERE  1 = 0;

UPDATE nutrition_recipes
SET    recipe_name_en = COALESCE (recipe_name_en, recipe_name_en),
       recipe_name_am = COALESCE (recipe_name_am, recipe_name_am)
WHERE  1 = 0;


-- The live DB fix for checksum drift must be done in Neon itself:
-- UPDATE schema_migrations
-- SET checksum = '2c1c291dca6d681c7ee9dc0c1cd562ff9496284c40cc8a1df4548f76a0a15ba8'
-- WHERE version = '0004';