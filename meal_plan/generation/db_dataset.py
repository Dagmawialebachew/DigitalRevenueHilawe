from __future__ import annotations

from decimal import Decimal
from typing import Any

from meal_plan.generation.dataset import HilaweDataset


_CUSTOM_QUERIES: dict[str, str] = {
    "template_components": """
        SELECT 
            template_id AS "Template ID",
            line_number AS "Line",
            item_type AS "Item Type",
            item_id AS "Item ID",
            item_name AS "Item Name",
            portion_g AS "Portion g",
            servings AS "Servings",
            kcal AS "kcal",
            protein_g AS "Protein g",
            carbs_g AS "Carbs g",
            fat_g AS "Fat g",
            fibre_g AS "Fibre g",
            exact_instruction AS "Exact Instruction",
            familiar_portion AS "Familiar Portion",
            exchange_note AS "Exchange Note",
            allergens AS "Allergens",
            optional AS "Optional",
            source_payload,
            dataset_version
        FROM nutrition_template_components
        ORDER BY template_id, line_number
    """,
    "recipe_ingredients": """
        SELECT 
            recipe_id AS "Recipe ID",
            line_number AS "Line",
            food_id AS "Food ID",
            ingredient_name AS "Ingredient",
            weight_g AS "Weight g",
            prep_note AS "Prep Note",
            source_payload,
            dataset_version
        FROM nutrition_recipe_ingredients
        ORDER BY recipe_id, line_number
    """,
    "exchange_groups": """
        SELECT 
            exchange_group AS "Exchange Group",
            food_id AS "Food ID",
            exchange_weight_g AS "Exchange Weight g",
            kcal AS "kcal",
            protein_g AS "Protein g",
            carbs_g AS "Carbs g",
            fat_g AS "Fat g",
            fibre_g AS "Fibre g",
            CASE WHEN fasting_allowed THEN 'Yes' ELSE 'No' END AS "Fasting Allowed",
            CASE WHEN fish_item THEN 'Yes' ELSE 'No' END AS "Fish Item",
            familiar_guidance AS "Familiar Guidance",
            coach_note AS "Coach Note",
            CASE WHEN active THEN 'Yes' ELSE 'No' END AS "Active",
            source_payload,
            dataset_version
        FROM nutrition_exchange_groups
        ORDER BY exchange_group, food_id
    """,
}

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


def _to_clean_value(val: Any) -> Any:
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, str) and "ፋል" in val:
        return val.replace("የጾም ፋል", "የጾም ፉል").replace("ፋል", "ፉል")
    return val


async def load_dataset_from_db(conn: Any) -> HilaweDataset:
    """Load the exact imported Hilawe source rows from PostgreSQL.

    Reads table columns with aliases matching Hilawe workbook keys, while
    falling back to or merging any non-empty `source_payload` JSONB when present.
    """
    sections: dict[str, tuple[dict[str, Any], ...]] = {}
    versions: set[str] = set()
    for key, table_sql in _TABLES:
        query = _CUSTOM_QUERIES.get(key, f"SELECT source_payload, dataset_version FROM {table_sql}")
        records = await conn.fetch(query)
        rows: list[dict[str, Any]] = []
        for record in records:
            rec_dict = dict(record)
            payload = rec_dict.pop("source_payload", None)
            ver = rec_dict.pop("dataset_version", None)
            if ver:
                versions.add(str(ver))

            if isinstance(payload, str) and payload.strip():
                try:
                    import json
                    payload = json.loads(payload)
                except Exception:
                    pass

            if isinstance(payload, dict) and payload:
                row = {str(k): _to_clean_value(v) for k, v in payload.items()}
                # Ensure column-backed ID fields are present as strings if missing in payload
                for col_k in ("Template ID", "Recipe ID", "Food ID"):
                    if col_k in rec_dict and rec_dict[col_k] is not None and col_k not in row:
                        row[col_k] = str(rec_dict[col_k])
            else:
                row = {str(k): _to_clean_value(v) for k, v in rec_dict.items()}
                for col_k in ("Template ID", "Recipe ID", "Food ID"):
                    if col_k in row and row[col_k] is not None:
                        row[col_k] = str(row[col_k])

            rows.append(row)
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
