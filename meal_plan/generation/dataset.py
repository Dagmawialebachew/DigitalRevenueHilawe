from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATASET_PATH = Path(__file__).resolve().parents[1] / "data" / "hilawe_v1_3_dataset.json"


def _active(row: dict[str, Any]) -> bool:
    return str(row.get("Active") or "").strip().lower() == "yes"


@dataclass(frozen=True)
class HilaweDataset:
    meta: dict[str, Any]
    foods: tuple[dict[str, Any], ...]
    recipes: tuple[dict[str, Any], ...]
    recipe_ingredients: tuple[dict[str, Any], ...]
    templates: tuple[dict[str, Any], ...]
    template_components: tuple[dict[str, Any], ...]
    exchange_groups: tuple[dict[str, Any], ...]
    fasting_calendar: tuple[dict[str, Any], ...]
    settings_rows: tuple[dict[str, Any], ...]

    @property
    def version(self) -> str:
        return str(self.meta["dataset_version"])

    @property
    def food_by_id(self) -> dict[str, dict[str, Any]]:
        return {str(x.get("Food ID")): x for x in self.foods if x.get("Food ID")}

    @property
    def recipe_by_id(self) -> dict[str, dict[str, Any]]:
        return {str(x.get("Recipe ID")): x for x in self.recipes if x.get("Recipe ID")}

    @property
    def ingredients_by_recipe(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for row in self.recipe_ingredients:
            rid = str(row.get("Recipe ID") or "")
            if rid:
                out.setdefault(rid, []).append(row)
        for values in out.values():
            values.sort(key=lambda r: int(r.get("Line") or 0))
        return out

    @property
    def components_by_template(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for row in self.template_components:
            tid = str(row.get("Template ID") or "")
            if tid:
                out.setdefault(tid, []).append(row)
        for values in out.values():
            values.sort(key=lambda r: int(r.get("Line") or 0))
        return out

    @property
    def active_templates(self) -> tuple[dict[str, Any], ...]:
        return tuple(x for x in self.templates if _active(x))

    @property
    def active_exchanges(self) -> tuple[dict[str, Any], ...]:
        return tuple(x for x in self.exchange_groups if _active(x))

    @property
    def settings(self) -> dict[str, Any]:
        return {
            str(x.get("System Key")): x.get("Current Value")
            for x in self.settings_rows
            if x.get("System Key")
        }


def load_dataset(path: str | Path | None = None, *, apply_calibration: bool = False) -> HilaweDataset:
    source = Path(path) if path else DATASET_PATH
    raw = json.loads(source.read_text(encoding="utf-8"))
    required = {
        "meta", "foods", "recipes", "recipe_ingredients", "templates",
        "template_components", "exchange_groups", "fasting_calendar", "settings",
    }
    missing = required.difference(raw)
    if missing:
        raise ValueError(f"Hilawe dataset is missing sections: {sorted(missing)}")
    expected = raw["meta"].get("counts", {})
    for key in ("foods", "recipes", "recipe_ingredients", "templates", "template_components", "exchange_groups"):
        if key in expected and int(expected[key]) != len(raw[key]):
            raise ValueError(f"Hilawe dataset count mismatch for {key}")

    if not apply_calibration:
        return HilaweDataset(
            meta=raw["meta"],
            foods=tuple(raw["foods"]),
            recipes=tuple(raw["recipes"]),
            recipe_ingredients=tuple(raw["recipe_ingredients"]),
            templates=tuple(raw["templates"]),
            template_components=tuple(raw["template_components"]),
            exchange_groups=tuple(raw["exchange_groups"]),
            fasting_calendar=tuple(raw["fasting_calendar"]),
            settings_rows=tuple(raw["settings"]),
        )

    from meal_plan.calibration import RECIPE_CALIBRATIONS
    from meal_plan.glossary import FOOD_GLOSSARY, RECIPE_GLOSSARY

    enriched_foods = []
    for f in raw["foods"]:
        fid = str(f.get("Food ID") or "")
        if fid in FOOD_GLOSSARY:
            en, am = FOOD_GLOSSARY[fid]
            row = dict(f)
            row["Food Name"] = en
            row["Local / Amharic"] = am
            enriched_foods.append(row)
        else:
            enriched_foods.append(f)

    enriched_recipes = []
    for r in raw["recipes"]:
        rid = str(r.get("Recipe ID") or "")
        row = dict(r)
        if rid in RECIPE_GLOSSARY:
            en, am = RECIPE_GLOSSARY[rid]
            row["Recipe Name"] = en
            row["Local Name"] = am
        if rid in RECIPE_CALIBRATIONS:
            cal = RECIPE_CALIBRATIONS[rid]
            row["Calibration Status"] = cal.get("calibration_status", "CALIBRATED")
            row["Source / Method"] = cal.get("source_method", "HILAWE_KITCHEN_CALIBRATION_V2")
            row["Version"] = cal.get("recipe_version", "2.0")
        enriched_recipes.append(row)

    return HilaweDataset(
        meta=raw["meta"],
        foods=tuple(enriched_foods),
        recipes=tuple(enriched_recipes),
        recipe_ingredients=tuple(raw["recipe_ingredients"]),
        templates=tuple(raw["templates"]),
        template_components=tuple(raw["template_components"]),
        exchange_groups=tuple(raw["exchange_groups"]),
        fasting_calendar=tuple(raw["fasting_calendar"]),
        settings_rows=tuple(raw["settings"]),
    )
