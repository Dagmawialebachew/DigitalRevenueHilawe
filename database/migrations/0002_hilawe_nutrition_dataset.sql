-- Phase 6: structured Coach Hilawe Meal Planner OS v1.3 nutrition dataset.
-- Additive only. No legacy workout/payment tables are altered.

CREATE TABLE IF NOT EXISTS nutrition_foods (
    food_id TEXT PRIMARY KEY,
    food_name TEXT NOT NULL,
    local_name TEXT,
    category TEXT,
    fasting_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    fish_item BOOLEAN NOT NULL DEFAULT FALSE,
    availability TEXT,
    budget_level TEXT,
    standard_portion_g NUMERIC(12,3),
    unit TEXT,
    familiar_measure TEXT,
    kcal_per_100g NUMERIC(12,4),
    protein_per_100g NUMERIC(12,4),
    carbs_per_100g NUMERIC(12,4),
    fat_per_100g NUMERIC(12,4),
    fibre_per_100g NUMERIC(12,4),
    exchange_group TEXT,
    allergen_tags TEXT,
    source_method TEXT,
    source_url TEXT,
    data_quality TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    yield_conversion NUMERIC(12,4) NOT NULL DEFAULT 1 CHECK (yield_conversion > 0),
    dataset_version TEXT NOT NULL,
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_nutrition_foods_active_category ON nutrition_foods(active, category);
CREATE INDEX IF NOT EXISTS ix_nutrition_foods_exchange ON nutrition_foods(exchange_group) WHERE active;

CREATE TABLE IF NOT EXISTS nutrition_recipes (
    recipe_id TEXT PRIMARY KEY,
    recipe_name TEXT NOT NULL,
    local_name TEXT,
    fasting BOOLEAN NOT NULL DEFAULT FALSE,
    fish BOOLEAN NOT NULL DEFAULT FALSE,
    meal_role TEXT,
    yield_g NUMERIC(12,3) NOT NULL CHECK (yield_g > 0),
    serving_g NUMERIC(12,3),
    kcal_per_serving NUMERIC(12,4),
    protein_g NUMERIC(12,4),
    carbs_g NUMERIC(12,4),
    fat_g NUMERIC(12,4),
    fibre_g NUMERIC(12,4),
    ingredients_summary TEXT,
    method TEXT,
    allergens TEXT,
    source_method TEXT,
    calibration_status TEXT,
    recipe_version TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    dataset_version TEXT NOT NULL,
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_nutrition_recipes_calibration ON nutrition_recipes(calibration_status) WHERE active;

CREATE TABLE IF NOT EXISTS nutrition_recipe_ingredients (
    recipe_id TEXT NOT NULL REFERENCES nutrition_recipes(recipe_id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    food_id TEXT NOT NULL REFERENCES nutrition_foods(food_id) ON DELETE RESTRICT,
    ingredient_name TEXT NOT NULL,
    weight_g NUMERIC(12,3) NOT NULL CHECK (weight_g >= 0),
    prep_note TEXT,
    dataset_version TEXT NOT NULL,
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (recipe_id, line_number)
);
CREATE INDEX IF NOT EXISTS ix_nutrition_recipe_ingredients_food ON nutrition_recipe_ingredients(food_id);

CREATE TABLE IF NOT EXISTS nutrition_templates (
    template_id TEXT PRIMARY KEY,
    meal_name TEXT NOT NULL,
    fasting BOOLEAN NOT NULL DEFAULT FALSE,
    fish_required BOOLEAN NOT NULL DEFAULT FALSE,
    meal_slot TEXT NOT NULL CHECK (meal_slot IN ('Breakfast','Lunch','Dinner','Snack')),
    cuisine TEXT,
    availability TEXT,
    budget TEXT,
    kcal NUMERIC(12,4),
    protein_g NUMERIC(12,4),
    carbs_g NUMERIC(12,4),
    fat_g NUMERIC(12,4),
    fibre_g NUMERIC(12,4),
    main_allergens TEXT,
    tags TEXT,
    rotation_group TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    dataset_version TEXT NOT NULL,
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_nutrition_templates_select ON nutrition_templates(active, fasting, meal_slot);

CREATE TABLE IF NOT EXISTS nutrition_template_components (
    template_id TEXT NOT NULL REFERENCES nutrition_templates(template_id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    item_type TEXT NOT NULL CHECK (item_type IN ('Food','Recipe')),
    item_id TEXT NOT NULL,
    item_name TEXT,
    servings NUMERIC(12,4),
    portion_g NUMERIC(12,3) NOT NULL CHECK (portion_g >= 0),
    kcal NUMERIC(12,4),
    protein_g NUMERIC(12,4),
    carbs_g NUMERIC(12,4),
    fat_g NUMERIC(12,4),
    fibre_g NUMERIC(12,4),
    exact_instruction TEXT,
    familiar_portion TEXT,
    exchange_note TEXT,
    allergens TEXT,
    optional BOOLEAN NOT NULL DEFAULT FALSE,
    dataset_version TEXT NOT NULL,
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (template_id, line_number)
);
CREATE INDEX IF NOT EXISTS ix_nutrition_template_components_item ON nutrition_template_components(item_type, item_id);

CREATE TABLE IF NOT EXISTS nutrition_exchange_groups (
    exchange_group TEXT NOT NULL,
    food_id TEXT NOT NULL REFERENCES nutrition_foods(food_id) ON DELETE CASCADE,
    exchange_weight_g NUMERIC(12,3) NOT NULL CHECK (exchange_weight_g > 0),
    kcal NUMERIC(12,4),
    protein_g NUMERIC(12,4),
    carbs_g NUMERIC(12,4),
    fat_g NUMERIC(12,4),
    fibre_g NUMERIC(12,4),
    fasting_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    fish_item BOOLEAN NOT NULL DEFAULT FALSE,
    familiar_guidance TEXT,
    coach_note TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    dataset_version TEXT NOT NULL,
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (exchange_group, food_id)
);

CREATE TABLE IF NOT EXISTS nutrition_fasting_calendar (
    rule_id TEXT PRIMARY KEY,
    fast_name TEXT NOT NULL,
    rule_type TEXT,
    weekday TEXT,
    start_date DATE,
    end_date DATE,
    fish_default BOOLEAN NOT NULL DEFAULT FALSE,
    client_override_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    verified_for_year TEXT,
    verification_status TEXT,
    notes TEXT,
    dataset_version TEXT NOT NULL,
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS nutrition_engine_settings (
    setting_key TEXT PRIMARY KEY,
    category TEXT,
    setting_name TEXT,
    value_json JSONB NOT NULL,
    unit TEXT,
    status TEXT,
    owner TEXT,
    notes TEXT,
    dataset_version TEXT NOT NULL,
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
