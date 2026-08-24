from __future__ import annotations

from typing import Any

from meal_plan.generation.dataset import HilaweDataset


_TABLES: tuple[tuple[str, str], ...] = (
    ("foods", "nutrition_foods ORDER BY food_id"),
    ("recipes", "nutrition_recipes ORDER BY recipe_id"),
    ("recipe_ingredients", "nutrition_recipe_ingredients ORDER BY recipe_id, line_number"),
    ("templates", "nutrition_templates ORDER BY template_id"),
    ("template_components", "nutrition_template_components ORDER BY template_id, line_number"),
    ("exchange_groups", "nutrition_exchange_groups ORDER BY exchange_group, food_id"),
    ("fasting_calendar", "nutrition_fasting_calendar ORDER BY rule_id"),
    ("settings", "nutrition_engine_settings ORDER BY setting_key"),
)


async def load_dataset_from_db(conn: Any) -> HilaweDataset:
    """Load the exact imported Hilawe source rows from PostgreSQL.

    Phase 6 stores every workbook row in `source_payload` JSONB. The engine can
    therefore use the same field names/rules whether it is running from the
    bundled, versioned snapshot during local tests or from the imported database
    in production. No lossy reverse-mapping from SQL column names is required.
    """
    sections: dict[str, tuple[dict[str, Any], ...]] = {}
    versions: set[str] = set()
    for key, table_sql in _TABLES:
        records = await conn.fetch(f"SELECT source_payload, dataset_version FROM {table_sql}")
        rows: list[dict[str, Any]] = []
        for record in records:
            payload = record["source_payload"]
            rows.append(dict(payload or {}))
            if record["dataset_version"]:
                versions.add(str(record["dataset_version"]))
        sections[key] = tuple(rows)

    if not sections["foods"] or not sections["templates"]:
        raise ValueError("Hilawe nutrition dataset is not imported into PostgreSQL")
    if len(versions) != 1:
        raise ValueError(f"Nutrition dataset version mismatch in PostgreSQL: {sorted(versions)}")
    version = next(iter(versions))
    coverage = await conn.fetch(
        """
        SELECT calendar_year FROM nutrition_fasting_calendar_coverage
        WHERE status='VERIFIED_COMPLETE'
        ORDER BY calendar_year
        """
    )

    return HilaweDataset(
        meta={
            "dataset_version": version,
            "source": "postgresql_imported_hilawe_dataset",
            "counts": {key: len(rows) for key, rows in sections.items()},
            "verified_fasting_calendar_years": [int(row["calendar_year"]) for row in coverage],
        },
        foods=sections["foods"],
        recipes=sections["recipes"],
        recipe_ingredients=sections["recipe_ingredients"],
        templates=sections["templates"],
        template_components=sections["template_components"],
        exchange_groups=sections["exchange_groups"],
        fasting_calendar=sections["fasting_calendar"],
        settings_rows=sections["settings"],
    )
