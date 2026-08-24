# Database migrations

Coach Hilawe Core still runs its legacy `SCHEMA_SQL` during startup. The meal-plan
domain uses separate, immutable, versioned SQL migrations in this directory.

## Applied design

- `0001_meal_plan_core.sql` — isolated order/intake/payment/review/version lifecycle.
- `0002_hilawe_nutrition_dataset.sql` — isolated Hilawe food/recipe/template/exchange/fasting/settings tables.

Both migrations are additive. They do not alter or delete legacy `users`,
`products`, workout `payments`, club, testimonial or financial data.

The runner:

- records versions and SHA-256 checksums in `schema_migrations`;
- uses a PostgreSQL advisory lock to prevent concurrent deploy races;
- runs each migration transactionally;
- refuses to continue if an already-applied migration file is later modified.

Emergency escape hatch: `MEAL_PLAN_RUN_MIGRATIONS=false` skips pending meal
migrations. Never edit an applied migration; add the next numbered file.

After `0002` exists, the dataset rows are loaded separately and idempotently with:

```powershell
python -m scripts.import_hilawe_dataset
```

The importer preserves every original workbook row in `source_payload` JSONB and
records the dataset version so engine output remains auditable.
