"""Database objects owned by the meal-plan domain."""

REQUIRED_TABLES: tuple[str, ...] = (
    "meal_intakes",
    "meal_health_reviews",
    "meal_pricing",
    "meal_quotes",
    "meal_orders",
    "meal_payments",
    "meal_plan_versions",
    "meal_generation_jobs",
    "meal_plan_artifacts",
    "meal_plan_reviews",
    "meal_deliveries",
    "meal_checkins",
    "meal_revision_requests",
    "meal_audit_events",
)

# Tables intentionally NOT created in Phase 1. Their schema must be derived from
# the Hilawe dataset during Phase 6 rather than guessed early.
PHASE_6_DATASET_TABLES: tuple[str, ...] = (
    "nutrition_foods",
    "nutrition_recipes",
    "nutrition_recipe_ingredients",
    "nutrition_templates",
    "nutrition_template_components",
    "nutrition_exchange_groups",
    "nutrition_fasting_calendar",
    "nutrition_engine_settings",
)
