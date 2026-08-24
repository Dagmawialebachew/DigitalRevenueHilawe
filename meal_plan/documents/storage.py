from __future__ import annotations

import os
from pathlib import Path


def artifact_root() -> Path:
    configured = os.getenv("MEAL_PLAN_ARTIFACT_ROOT", "artifacts/meal_plans")
    return Path(configured).expanduser().resolve()


def version_output_dir(plan_public_id: str, version_number: int, root: str | Path | None = None) -> Path:
    base = Path(root).expanduser().resolve() if root else artifact_root()
    path = base / str(plan_public_id) / f"v{int(version_number)}"
    path.mkdir(parents=True, exist_ok=True)
    return path
