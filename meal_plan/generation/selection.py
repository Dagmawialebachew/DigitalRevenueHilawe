from __future__ import annotations

from collections import defaultdict
from typing import Any

from meal_plan.generation.dataset import HilaweDataset
from meal_plan.generation.safety import preference_score, template_is_safe


BUDGET_RANK = {"Value": 1, "Standard": 2, "Premium": 3}
BUDGET_MAP = {"SAVE": "Value", "BALANCED": "Standard", "FLEXIBLE": "Premium"}


def budget_allowed(template_budget: Any, answers: dict[str, Any]) -> bool:
    client_budget = str(answers.get("grocery_budget") or "BALANCED").upper()
    client = BUDGET_MAP.get(client_budget, "Standard")
    tmpl_rank = BUDGET_RANK.get(str(template_budget), 1)

    # Save / Value tier cannot exceed tier 1
    if client == "Value":
        return tmpl_rank <= 1
    if client == "Standard":
        return tmpl_rank <= 2
    return True


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
        self.slot_history: dict[str, list[str]] = defaultdict(list)
        self.day_template_history: dict[int, set[str]] = defaultdict(set)
        self.day_egg_breakfast: dict[int, bool] = {}
        self.weekly_dinner_egg_count: int = 0
        self.slot_day_template: dict[tuple[int, str], str] = {}

    def candidates(self, *, fasting: bool, source_slot: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        dietary = str(self.answers.get("dietary_pattern") or "OMNIVORE").upper()

        for template in self.dataset.active_templates:
            t_slot = str(template.get("Meal Slot"))
            tid = str(template.get("Template ID"))
            if t_slot != source_slot:
                # Allow Minchet Abish (MN-D02) for both Lunch and Dinner
                if source_slot == "Lunch" and tid == "MN-D02":
                    pass
                else:
                    continue

            is_tmpl_fasting = str(template.get("Fasting")) == "Yes"
            if fasting:
                if not is_tmpl_fasting:
                    continue
            allow_for_omnivore = False
            if not fasting and is_tmpl_fasting:
                if dietary == "OMNIVORE" and source_slot in ("Lunch", "Dinner") and tid in ("MF-L01", "MF-L02", "MF-L03", "MF-L07", "MF-D01", "MF-D04", "MF-D07"):
                    allow_for_omnivore = True
                elif dietary == "OMNIVORE" and source_slot == "Breakfast" and tid in ("MF-B01", "MF-B02", "MF-B07"):
                    allow_for_omnivore = True
                elif dietary in ("VEGETARIAN", "PESCATARIAN"):
                    allow_for_omnivore = True
                else:
                    continue

            if not budget_allowed(template.get("Budget"), self.answers):
                continue
            if not availability_allowed(template.get("Availability"), self.region, self.country_name):
                continue
            safe, _ = template_is_safe(template, self.dataset, self.answers, fasting=fasting, allow_fasting_for_omnivore=allow_for_omnivore)
            if safe:
                rows.append(template)

        is_hardgainer = float(self.answers.get("current_weight_kg") or 0) < 55.0 and str(self.answers.get("primary_goal") or "").upper() == "MUSCLE_GAIN"
        if source_slot == "Snack" and is_hardgainer:
            rows.append({
                "Template ID": "MN-S-SHAKE",
                "Meal Name": "High-calorie strength shake",
                "Local / Amharic": "የጥንካሬ ሼክ / ፈጣን መክሰስ",
                "Fasting": "No",
                "Fish Required": "No",
                "Meal Slot": "Snack",
                "Cuisine": "Ethiopian",
                "Availability": "Global",
                "Budget": "Value",
                "Plan Formats": "Exact grams + familiar portions + exchanges",
                "kcal": 450.0,
                "Protein g": 22.0,
                "Carbs g": 65.0,
                "Fat g": 18.0,
                "Fibre g": 5.0,
                "Main Allergens": "Dairy; peanut",
                "Tags": "shake; strength; hardgainer",
                "Rotation Group": "Snack",
                "Active": "Yes",
            })

        return rows

    def choose(
        self,
        *,
        fasting: bool,
        source_slot: str,
        day_index: int,
        exclude_today: set[str] | None = None,
        exclude_recipes: set[str] | None = None,
        prefer_fish: bool = False,
        avoid_fish: bool = False,
        whole_food_first: bool = False,
    ) -> dict[str, Any]:
        candidates = self.candidates(fasting=fasting, source_slot=source_slot)
        if source_slot != "Snack":
            exclude_today = (exclude_today or set()).union(self.day_template_history[day_index])
            candidates = [t for t in candidates if str(t.get("Template ID")) not in exclude_today]
        else:
            # For snack, allow MN-S-SHAKE even if used previously
            non_snack_exclude = {x for x in (exclude_today or set()) if x != "MN-S-SHAKE"}
            candidates = [t for t in candidates if str(t.get("Template ID")) not in non_snack_exclude]
        dietary = str(self.answers.get("dietary_pattern") or "OMNIVORE").upper()
        is_save_budget = str(self.answers.get("grocery_budget") or "").upper() in ("SAVE", "VALUE", "ቆጣቢ / ዝቅተኛ")

        # The recovered non-fasting v1.3 library has no vegetarian lunch pool.
        # For a lacto-ovo vegetarian on a non-religious-fast day, safely fall
        # back to the source plant/fasting template library rather than offer
        # meat or invent a meal.
        if not candidates and not fasting and dietary in {"VEGETARIAN", "PESCATARIAN"}:
            candidates = self.candidates(fasting=True, source_slot=source_slot)
            candidates = [t for t in candidates if str(t.get("Template ID")) not in exclude_today]
        if not candidates:
            raise ValueError(f"No safe {'fasting ' if fasting else ''}{source_slot} template matches this client")

        if exclude_recipes and source_slot != "Snack":
            non_duplicate = []
            for t in candidates:
                tid = str(t.get("Template ID") or "")
                comps = self.dataset.components_by_template.get(tid, [])
                recipe_ids = {str(c.get("Item ID")) for c in comps if str(c.get("Item Type")) == "Recipe"}
                if not recipe_ids.intersection(exclude_recipes):
                    non_duplicate.append(t)
            if non_duplicate:
                candidates = non_duplicate

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

        def template_has_egg(tmpl: dict[str, Any]) -> bool:
            tmpl_id = str(tmpl.get("Template ID") or "")
            comps = self.dataset.components_by_template.get(tmpl_id, [])
            for c in comps:
                item_id = str(c.get("Item ID") or "")
                item_name = str(c.get("Item Name") or "").lower()
                if item_id in ("A011", "A012", "R021") or "egg" in item_name or "እንቁላል" in item_name:
                    return True
            m_name = (str(tmpl.get("Meal Name") or "") + " " + str(tmpl.get("Tags") or "")).lower()
            return "egg" in m_name or "እንቁላል" in m_name or "firfir" in m_name

        def score_template(tmpl: dict[str, Any]) -> float:
            tid = str(tmpl.get("Template ID"))
            if source_slot == "Snack" and tid == "MN-S-SHAKE":
                return 1000.0

            base = float(preference_score(tmpl, self.dataset, self.answers))
            score = base

            # Strict recent-history penalty (prevent repeat within 3-4 days)
            slot_hist = self.slot_history[source_slot]
            if slot_hist:
                if tid in slot_hist[-2:]:
                    score -= 100.0
                elif tid in slot_hist[-4:]:
                    score -= 40.0

            # Usage frequency penalty
            uses = self.usage[key][tid]
            score -= float(uses) * 30.0

            # Step 1: Breakfast diversity and rotation (Break monopoly, max 2 uses per 7-day period)
            if source_slot == "Breakfast":
                # Check usage in current 7-day window
                window_start = (day_index // 7) * 7
                recent_window_uses = sum(
                    1 for d in range(window_start, day_index)
                    if self.slot_day_template.get((d, "Breakfast")) == tid
                )
                if recent_window_uses >= 2:
                    score -= 200.0  # Strict cap: no single breakfast template appears > 2 times in a 7-day period
                elif recent_window_uses == 1:
                    score -= 25.0

                if dietary == "OMNIVORE":
                    comps = self.dataset.components_by_template.get(tid, [])
                    recipe_ids = {str(c.get("Item ID")) for c in comps if str(c.get("Item Type")) == "Recipe"}
                    food_ids = {str(c.get("Item ID")) for c in comps if str(c.get("Item Type")) == "Food"}
                    # Target 7-day natural omnivore breakfast rotation:
                    # 2-3 days: Egg-based (Boiled eggs with whole wheat bread/injera, or Egg Firfir R021/B001/MN-B01/MN-B04/MN-B07)
                    # 2 days: Oatmeal / fruit bowl or Kinche (R025 / MN-B02 / MF-B07 / MF-B02 / MF-B01)
                    # 2 days: Ayib and fruit bowl (R024 / MN-B06)
                    breakfast_target_map = {
                        0: ("MN-B01", "A011"),  # Eggs, injera and tomato
                        1: ("MN-B02", "MF-B07", "R025", "C007"),  # Oatmeal / fruit bowl
                        2: ("MN-B06", "A018"),  # Ayib, injera and papaya
                        3: ("MN-B04", "A011"),  # Boiled eggs, whole-wheat bread and orange
                        4: ("MF-B07", "MF-B02", "MN-B02", "R025", "C007"),  # Peanut banana oats
                        5: ("MN-B06", "A018"),  # Ayib, injera and papaya
                        6: ("MN-B07", "R021", "A011"),  # Egg firfir and cucumber
                    }
                    b_targets = breakfast_target_map.get(day_index % 7, ())
                    if tid == "MN-B02" and day_index % 7 == 1:
                        score += 130.0
                    elif tid in b_targets or any(r in recipe_ids for r in b_targets) or any(f in food_ids for f in b_targets):
                        score += 85.0

            # Step 3: Prevent Breakfast + Dinner Double-Egg Monotony
            if source_slot == "Dinner":
                is_egg_dinner = template_has_egg(tmpl) or tid == "MN-D04"
                if is_egg_dinner:
                    # If user had eggs for breakfast today, heavily downrank dinner egg firfir
                    if self.day_egg_breakfast.get(day_index):
                        score -= 150.0
                    # Allow R021 (Egg Firfir) at dinner at most 2 times per week
                    if self.weekly_dinner_egg_count >= 2:
                        score -= 150.0

                # For Dinner, prioritize varied Ethiopian stews & fish:
                # R024 (Ayib be Gomen), R014/R015 (Fish Tibs / Grilled Tilapia), R001 (Shiro), R002 (Misir)
                comps = self.dataset.components_by_template.get(tid, [])
                recipe_ids = {str(c.get("Item ID")) for c in comps if str(c.get("Item Type")) == "Recipe"}
                if "R024" in recipe_ids or tid == "MN-D05":
                    score += 45.0
                elif any(r in recipe_ids for r in ("R014", "R015")) or tid in ("MN-D01", "MF-D05"):
                    score += 40.0
                elif "R001" in recipe_ids or tid == "MF-D04":
                    score += 35.0
                elif "R002" in recipe_ids or tid == "MF-D07":
                    score += 30.0

            # Step 2: Ensure omnivore lunches actively alternate across the week:
            # Day 1: ቀይ ወጥ (Beef Key Wot - R023 / MN-L07)
            # Day 2: የበሬ ስጋ ጥብስ (Beef Tibs - R018 / MN-L02)
            # Day 3: ሽሮ ወጥ ከእንጀራ ጋር (Shiro Wot - R001 / MF-L02)
            # Day 4: ምንቸት አብሽ (Minchet Abish - R020 / MN-D02)
            # Day 5: ምስር ወጥ (Misir Wot - R002 / MF-L01)
            # Day 6: ክክ አልጫ (Kik Alicha - R003 / MF-L03)
            # Day 7: ቀይ ወጥ (Beef Key Wot - R023 / MN-L07)
            if source_slot == "Lunch" and dietary == "OMNIVORE":
                comps = self.dataset.components_by_template.get(tid, [])
                recipe_ids = {str(c.get("Item ID")) for c in comps if str(c.get("Item Type")) == "Recipe"}
                if is_save_budget:
                    target_map = {
                        0: ("R023", "MN-L07"),
                        1: ("R018", "MN-L02"),
                        2: ("R001", "MF-L02"),
                        3: ("R020", "MN-D02"),
                        4: ("R002", "MF-L01"),
                        5: ("R003", "MF-L03"),
                        6: ("R023", "MN-L07"),
                    }
                else:
                    target_map = {
                        0: ("R023", "MN-L07"),
                        1: ("R018", "MN-L02"),
                        2: ("R001", "MF-L02"),
                        3: ("R020", "MN-D02"),
                        4: ("R019", "R016", "MN-L06", "MN-L04"),
                        5: ("R002", "R014", "MF-L01", "MF-L07"),
                        6: ("R023", "MN-L07"),
                    }
                day_targets = target_map.get(day_index % 7, ())
                if tid in day_targets or any(r in recipe_ids for r in day_targets):
                    score += 70.0

            return score

        candidates.sort(key=score_template, reverse=True)
        chosen = candidates[0]
        tid = str(chosen.get("Template ID"))

        self.usage[key][tid] += 1
        self.last_day[tid] = day_index
        self.slot_history[source_slot].append(tid)
        self.day_template_history[day_index].add(tid)
        self.slot_day_template[(day_index, source_slot)] = tid

        if source_slot == "Breakfast":
            if template_has_egg(chosen):
                self.day_egg_breakfast[day_index] = True
        elif source_slot == "Dinner":
            if template_has_egg(chosen) or tid == "MN-D04":
                self.weekly_dinner_egg_count += 1

        return chosen
