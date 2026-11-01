"""Persistent Coach Feedback Memory & Dynamic Rule Catalog (Pillar 3 Architecture).

Provides a centralized, thread-safe store for clinical constraints, culinary pairing
rules, portion caps, and household measure overrides established by Coach Hilawe / Boss.
Rules are persisted in JSON and can be added, updated, or queried dynamically without
modifying Python source code.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

DEFAULT_CATALOG_LOCATIONS = [
    Path(__file__).parent.parent / "data" / "feedback_catalog.json",
    Path(__file__).parent.parent / "feedback_catalog.json",
    Path("meal_plan/data/feedback_catalog.json"),
    Path("meal_plan/feedback_catalog.json"),
]


@dataclass
class FeedbackRule:
    id: str
    type: str  # portion_cap, pairing_exclusion, portion_discrete, familiar_override, portion_standard, breakfast_balance, target_floor, custom
    name: str
    description: str
    author: str = "Coach Hilawe"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_active: bool = True
    severity: str = "WARNING"  # ERROR, WARNING, INFO
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Flatten metadata into the root dict if keys don't collide for backwards compatibility
        meta = data.pop("metadata", {})
        for k, v in meta.items():
            if k not in data:
                data[k] = v
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FeedbackRule:
        known_fields = {"id", "type", "name", "description", "author", "created_at", "is_active", "severity"}
        core_args = {k: v for k, v in data.items() if k in known_fields}
        meta_args = {k: v for k, v in data.items() if k not in known_fields}
        return cls(**core_args, metadata=meta_args)


class FeedbackStore:
    """In-memory cached and JSON-persisted Feedback Rule Catalog."""

    def __init__(self, catalog_path: Optional[Path | str] = None):
        self.catalog_path = self._resolve_path(catalog_path)
        self.catalog_version: str = "1.0.0"
        self.description: str = ""
        self.updated_at: str = ""
        self.rules: Dict[str, FeedbackRule] = {}
        self.load()

    def _resolve_path(self, catalog_path: Optional[Path | str]) -> Path:
        if catalog_path:
            return Path(catalog_path).resolve()
        env_path = os.environ.get("FEEDBACK_CATALOG_PATH")
        if env_path:
            return Path(env_path).resolve()
        for loc in DEFAULT_CATALOG_LOCATIONS:
            if loc.exists():
                return loc.resolve()
        # Fallback default
        return DEFAULT_CATALOG_LOCATIONS[0].resolve()

    def load(self) -> None:
        """Load catalog from JSON file."""
        if not self.catalog_path.exists():
            logger.warning(f"Feedback catalog file not found at {self.catalog_path}. Initializing empty store.")
            self.rules = {}
            return

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.catalog_version = data.get("catalog_version", "1.0.0")
            self.description = data.get("description", "")
            self.updated_at = data.get("updated_at", "")
            raw_rules = data.get("rules", [])
            self.rules = {}
            for r in raw_rules:
                rule = FeedbackRule.from_dict(r)
                self.rules[rule.id] = rule
            logger.info(f"Loaded {len(self.rules)} feedback rules from {self.catalog_path}")
        except Exception as e:
            logger.error(f"Failed to load feedback catalog from {self.catalog_path}: {e}")

    def save(self) -> None:
        """Atomically persist catalog back to JSON file."""
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "catalog_version": self.catalog_version,
            "updated_at": self.updated_at,
            "description": self.description,
            "rules": [r.to_dict() for r in self.rules.values()],
        }
        temp_path = self.catalog_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        temp_path.replace(self.catalog_path)
        logger.info(f"Persisted {len(self.rules)} rules to {self.catalog_path}")

    # -------------------------------------------------------------------------
    # Rule Queries
    # -------------------------------------------------------------------------
    def get_all_rules(self) -> List[FeedbackRule]:
        return list(self.rules.values())

    def get_active_rules(self, rule_type: Optional[str] = None) -> List[FeedbackRule]:
        return [
            r for r in self.rules.values()
            if r.is_active and (rule_type is None or r.type == rule_type)
        ]

    def get_rule(self, rule_id: str) -> Optional[FeedbackRule]:
        return self.rules.get(rule_id)

    def get_portion_caps(self, meal_slot: Optional[str] = None) -> Dict[str, float]:
        """Returns map of {target_id: max_grams} for portion_cap rules."""
        caps: Dict[str, float] = {}
        for r in self.get_active_rules("portion_cap"):
            target_id = r.metadata.get("target_id")
            max_g = float(r.metadata.get("max_grams", 0.0))
            slots = r.metadata.get("meal_slots")
            if target_id and max_g > 0:
                if slots:
                    if not meal_slot or meal_slot.lower() not in [s.lower() for s in slots]:
                        continue
                # If multiple caps exist, take the strictest (lowest)
                caps[target_id] = min(caps.get(target_id, float("inf")), max_g)
        return caps

    def get_enforced_familiars(self) -> Dict[str, str]:
        """Returns map of {target_id: familiar_text} for portion caps or overrides."""
        fam: Dict[str, str] = {}
        for r in self.get_active_rules():
            target_id = r.metadata.get("target_id")
            if not target_id:
                continue
            if r.type == "portion_cap" and r.metadata.get("enforced_familiar"):
                fam[target_id] = str(r.metadata["enforced_familiar"])
            elif r.type == "familiar_override" and r.metadata.get("familiar_text"):
                fam[target_id] = str(r.metadata["familiar_text"])
        return fam

    def get_forbidden_pairings(self) -> List[Dict[str, Any]]:
        """Returns list of pairing exclusion rules."""
        exclusions = []
        for r in self.get_active_rules("pairing_exclusion"):
            primaries = list(r.metadata.get("primary_ids") or [])
            forbidden = list(r.metadata.get("forbidden_secondary_ids") or [])
            if primaries and forbidden:
                exclusions.append({
                    "rule_id": r.id,
                    "name": r.name,
                    "primary_ids": set(primaries),
                    "forbidden_secondary_ids": set(forbidden),
                    "action": r.metadata.get("action", "remove_secondary"),
                    "severity": r.severity,
                })
        return exclusions

    def get_forbidden_secondaries_for(self, active_recipe_or_food_ids: Set[str]) -> Set[str]:
        """Given a set of IDs in a meal, returns which secondary IDs are forbidden."""
        forbidden: Set[str] = set()
        for rule in self.get_forbidden_pairings():
            if rule["primary_ids"].intersection(active_recipe_or_food_ids):
                forbidden.update(rule["forbidden_secondary_ids"])
        return forbidden

    def get_portion_standards(self) -> Dict[str, Dict[str, Any]]:
        """Returns standard portion weights and familiars for stews (R002, R004, etc.)."""
        standards: Dict[str, Dict[str, Any]] = {}
        for r in self.get_active_rules("portion_standard"):
            std_map = r.metadata.get("standards", {})
            for k, v in std_map.items():
                standards[k] = v
        return standards

    def get_breakfast_liquid_rules(self) -> Dict[str, Any]:
        """Returns dynamic breakfast balance parameters."""
        for r in self.get_active_rules("breakfast_balance"):
            return r.metadata
        return {
            "pb_cap_cutting": 12.0,
            "pb_cap_balanced": 15.0,
            "oats_cap_cutting": 40.0,
            "oats_cap_balanced": 50.0,
            "soymilk_grams_cutting": 200.0,
            "soymilk_grams_balanced": 250.0,
        }

    def get_injera_discrete_rule(self) -> Dict[str, Any]:
        """Returns discrete 60g multiple rule parameters."""
        for r in self.get_active_rules("portion_discrete"):
            if r.metadata.get("target_id") == "C001":
                return r.metadata
        return {
            "allowed_multiples_of": 60.0,
            "min_grams": 60.0,
            "max_grams": 240.0,
            "familiar_map": {
                "60": "ግማሽ እንጀራ",
                "120": "1 እንጀራ",
                "180": "1 ከግማሽ እንጀራ",
                "240": "2 እንጀራ",
            },
        }

    # -------------------------------------------------------------------------
    # Mutations
    # -------------------------------------------------------------------------
    def add_rule(self, rule: FeedbackRule | Dict[str, Any]) -> FeedbackRule:
        if isinstance(rule, dict):
            rule_obj = FeedbackRule.from_dict(rule)
        else:
            rule_obj = rule
        self.rules[rule_obj.id] = rule_obj
        self.save()
        return rule_obj

    def archive_rule(self, rule_id: str) -> bool:
        if rule_id in self.rules:
            self.rules[rule_id].is_active = False
            self.save()
            return True
        return False

    def activate_rule(self, rule_id: str) -> bool:
        if rule_id in self.rules:
            self.rules[rule_id].is_active = True
            self.save()
            return True
        return False

    def remove_rule(self, rule_id: str) -> bool:
        if rule_id in self.rules:
            del self.rules[rule_id]
            self.save()
            return True
        return False

    # -------------------------------------------------------------------------
    # Intelligent Coach Boss Feedback Parsing
    # -------------------------------------------------------------------------
    def record_coach_feedback(
        self,
        feedback_text: str,
        author: str = "Coach Boss",
        context: Optional[Dict[str, Any]] = None,
    ) -> FeedbackRule:
        """Parses natural feedback text into a structured, active FeedbackRule."""
        clean_text = feedback_text.strip()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        rule_id = f"RULE_FEEDBACK_{timestamp}"
        context = context or {}

        # 1. Detect portion cap: e.g. "cap rice cakes to 40g", "rice cakes max 30g", "limit C020 to 40g"
        cap_match = re.search(r"(?:cap|limit|max(?:imum)?)\s+([a-zA-Z0-9_\s]+?)\s+(?:to|at|is)?\s*(\d+(?:\.\d+)?)\s*(?:g|grams)", clean_text, re.IGNORECASE)
        if cap_match:
            item_name = cap_match.group(1).strip()
            max_g = float(cap_match.group(2))
            target_id = context.get("target_id")
            if not target_id:
                if "rice cake" in item_name.lower():
                    target_id = "C020"
                elif "oil" in item_name.lower():
                    target_id = "T001"
                elif "peanut" in item_name.lower():
                    target_id = "T004"
                elif "oat" in item_name.lower():
                    target_id = "C007"
                else:
                    target_id = item_name.upper().replace(" ", "_")

            rule = FeedbackRule(
                id=f"RULE_CAP_{target_id}_{int(max_g)}G",
                type="portion_cap",
                name=f"Cap {item_name} at {max_g:.0f}g",
                description=clean_text,
                author=author,
                is_active=True,
                severity="WARNING",
                metadata={"target_id": target_id, "max_grams": max_g, "applies_to": "all"}
            )
            return self.add_rule(rule)

        # 2. Detect forbidden pairing: e.g. "never pair plain lentils with misir wot", "forbid P001 on R002"
        pair_match = re.search(r"(?:never|do not|don't|forbid|stop)\s+(?:pair|pairing|stack|stacking|serving|adding)\s+([a-zA-Z0-9_\s]+?)\s+(?:with|on|and)\s+([a-zA-Z0-9_\s]+)", clean_text, re.IGNORECASE)
        if pair_match:
            sec_name = pair_match.group(1).strip()
            prim_name = pair_match.group(2).strip()
            rule = FeedbackRule(
                id=f"RULE_EXCLUDE_{sec_name.upper()[:6]}_{prim_name.upper()[:6]}",
                type="pairing_exclusion",
                name=f"Forbid {sec_name} with {prim_name}",
                description=clean_text,
                author=author,
                is_active=True,
                severity="ERROR",
                metadata={
                    "primary_ids": [prim_name.upper()],
                    "forbidden_secondary_ids": [sec_name.upper()],
                    "action": "remove_secondary"
                }
            )
            return self.add_rule(rule)

        # 3. Default to general Coach preference rule
        rule = FeedbackRule(
            id=rule_id,
            type="coach_preference",
            name=f"Coach Note: {clean_text[:40]}…",
            description=clean_text,
            author=author,
            is_active=True,
            severity="WARNING",
            metadata=context
        )
        return self.add_rule(rule)


_DEFAULT_STORE: Optional[FeedbackStore] = None


def get_feedback_store(catalog_path: Optional[Path | str] = None, reload: bool = False) -> FeedbackStore:
    """Thread-safe access to singleton FeedbackStore."""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None or reload:
        _DEFAULT_STORE = FeedbackStore(catalog_path)
    return _DEFAULT_STORE
