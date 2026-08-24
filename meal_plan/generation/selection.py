from __future__ import annotations

from collections import defaultdict
from typing import Any

from meal_plan.generation.dataset import HilaweDataset
from meal_plan.generation.safety import preference_score, template_is_safe


BUDGET_RANK = {"Value": 1, "Standard": 2, "Premium": 3}
BUDGET_MAP = {"SAVE": "Value", "BALANCED": "Standard", "FLEXIBLE": "Premium"}


def budget_allowed(template_budget: Any, answers: dict[str, Any]) -> bool:
    client = BUDGET_MAP.get(str(answers.get("grocery_budget") or "BALANCED").upper(), "Standard")
    # Preserve Hilawe v1.3 adjacent-tier behavior: Value never receives Premium.
    return BUDGET_RANK.get(str(template_budget), 1) <= min(3, BUDGET_RANK[client] + 1)


def availability_allowed(availability: Any, region: str, country_name: str | None = None) -> bool:
    a = str(availability or "").lower()
    if "global" in a:
        return True
    if region == "ETHIOPIA":
        return "ethiopia" in a
    # US/Europe/UAE/Other are treated as diaspora contexts; this is the source
    # Hilawe heuristic, not a verified local-price/stock promise.
    return "diaspora" in a or "ethiopia + diaspora" in a


class TemplateSelector:
    def __init__(self, dataset: HilaweDataset, answers: dict[str, Any], *, region: str, country_name: str | None = None):
        self.dataset = dataset
        self.answers = answers
        self.region = region
        self.country_name = country_name
        self.usage: dict[tuple[bool, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.last_day: dict[str, int] = {}

    def candidates(self, *, fasting: bool, source_slot: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for template in self.dataset.active_templates:
            if str(template.get("Fasting")) != ("Yes" if fasting else "No"):
                continue
            if str(template.get("Meal Slot")) != source_slot:
                continue
            if not budget_allowed(template.get("Budget"), self.answers):
                continue
            if not availability_allowed(template.get("Availability"), self.region, self.country_name):
                continue
            safe, _ = template_is_safe(template, self.dataset, self.answers, fasting=fasting)
            if safe:
                rows.append(template)
        return rows

    def choose(
        self,
        *,
        fasting: bool,
        source_slot: str,
        day_index: int,
        exclude_today: set[str] | None = None,
        prefer_fish: bool = False,
        avoid_fish: bool = False,
        whole_food_first: bool = False,
    ) -> dict[str, Any]:
        candidates = self.candidates(fasting=fasting, source_slot=source_slot)
        exclude_today = exclude_today or set()
        candidates = [t for t in candidates if str(t.get("Template ID")) not in exclude_today]
        # The recovered non-fasting v1.3 library has no vegetarian lunch pool.
        # For a lacto-ovo vegetarian on a non-religious-fast day, safely fall
        # back to the source plant/fasting template library rather than offer
        # meat or invent a meal. Vegan days already use the plant library as
        # their primary mode from engine.py.
        if not candidates and not fasting and str(self.answers.get("dietary_pattern") or "").upper() == "VEGETARIAN":
            candidates = self.candidates(fasting=True, source_slot=source_slot)
            candidates = [t for t in candidates if str(t.get("Template ID")) not in exclude_today]
        if not candidates:
            raise ValueError(f"No safe {'fasting ' if fasting else ''}{source_slot} template matches this client")

        if prefer_fish:
            fish = [t for t in candidates if str(t.get("Fish Required")) == "Yes"]
            if fish:
                candidates = fish
        elif avoid_fish:
            plant = [t for t in candidates if str(t.get("Fish Required")) != "Yes"]
            if plant:
                candidates = plant

        if whole_food_first:
            whole = [t for t in candidates if not any(
                phrase in (str(t.get("Meal Name") or "") + " " + str(t.get("Tags") or "")).lower()
                for phrase in ("soy chunks", "soy tibs", "protein powder")
            )]
            if whole:
                candidates = whole

        key = (fasting, source_slot)
        # Prefer unused templates. For 5-meal plans the snack pool can be smaller
        # than 14 selections/week, so after exhausting it we rotate from the least-used
        # safe templates rather than inventing or repeating the same snack on one day.
        def rank(t: dict[str, Any]) -> tuple[float, float, float, str]:
            tid = str(t.get("Template ID"))
            uses = self.usage[key][tid]
            recent_penalty = 1.0 if self.last_day.get(tid) == day_index - 1 else 0.0
            pref = preference_score(t, self.dataset, self.answers)
            return (float(uses), recent_penalty, -pref, tid)

        chosen = sorted(candidates, key=rank)[0]
        tid = str(chosen.get("Template ID"))
        self.usage[key][tid] += 1
        self.last_day[tid] = day_index
        return chosen
